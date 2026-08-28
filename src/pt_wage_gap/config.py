"""Typed configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from pt_wage_gap.source_contract import PrimarySourceContract, SourceContractError


class ConfigError(ValueError):
    """Raised when the study configuration is invalid."""


@dataclass(frozen=True)
class StudyConfig:
    """Validated subset of the study configuration used by the pipeline."""

    study_id: str
    country: str
    benchmark: str
    start_year: int
    end_year: int
    latest_year_primary: int
    bootstrap_replications: int
    bootstrap_seed: int
    dataset: str
    frequency: str
    unit: str
    wage_indicator: str
    productivity_indicator: str
    comparator_countries: tuple[str, ...]
    minimum_comparator_countries_per_year: int

    def __post_init__(self) -> None:
        """Validate cross-field invariants and the registered source contract."""
        if not self.study_id.strip():
            raise ConfigError("study.id must be non-empty")
        if self.start_year > self.end_year:
            raise ConfigError("study.start_year must not exceed study.end_year")
        if not self.start_year <= self.latest_year_primary <= self.end_year:
            raise ConfigError("latest_year_primary must lie inside the study window")
        if self.bootstrap_replications < 1:
            raise ConfigError("bootstrap_replications must be positive")
        if self.country in self.comparator_countries:
            raise ConfigError("Portugal/target country must not appear in comparator_countries")
        if len(set(self.comparator_countries)) != len(self.comparator_countries):
            raise ConfigError("comparator_countries must be unique")
        if self.minimum_comparator_countries_per_year < 3:
            raise ConfigError("minimum comparator count must be at least three")
        if self.minimum_comparator_countries_per_year > len(self.comparator_countries):
            raise ConfigError("minimum comparator count exceeds comparator universe")

        try:
            PrimarySourceContract().validate(
                dataset=self.dataset,
                frequency=self.frequency,
                unit=self.unit,
                wage_indicator=self.wage_indicator,
                productivity_indicator=self.productivity_indicator,
                benchmark=self.benchmark,
            )
        except SourceContractError as exc:
            raise ConfigError(str(exc)) from exc


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Return a mapping or raise a configuration-specific error."""
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be a mapping")
    return value


def _require_string(mapping: Mapping[str, Any], key: str, section: str) -> str:
    """Read one required non-empty string without implicit type coercion."""
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{section}.{key} must be a non-empty string")
    return value


def _require_int(mapping: Mapping[str, Any], key: str, section: str) -> int:
    """Read one required integer and reject booleans or string coercion."""
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{section}.{key} must be an integer")
    return value


def load_config(path: Path) -> StudyConfig:
    """Load and validate a YAML study configuration.

    Parameters
    ----------
    path:
        Path to the YAML file.

    Returns
    -------
    StudyConfig
        Immutable validated configuration.
    """
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    root = _require_mapping(payload, "root")
    study = _require_mapping(root.get("study"), "study")
    primary = _require_mapping(root.get("primary_levels"), "primary_levels")
    comparators = _require_mapping(root.get("comparators"), "comparators")
    analysis = _require_mapping(root.get("analysis"), "analysis")

    countries_raw = comparators.get("countries")
    if not isinstance(countries_raw, list) or not all(isinstance(x, str) for x in countries_raw):
        raise ConfigError("comparators.countries must be a list of strings")

    return StudyConfig(
        study_id=_require_string(study, "id", "study"),
        country=_require_string(study, "country", "study"),
        benchmark=_require_string(study, "benchmark", "study"),
        start_year=_require_int(study, "start_year", "study"),
        end_year=_require_int(study, "end_year", "study"),
        latest_year_primary=_require_int(study, "latest_year_primary", "study"),
        bootstrap_replications=_require_int(study, "bootstrap_replications", "study"),
        bootstrap_seed=_require_int(study, "bootstrap_seed", "study"),
        dataset=_require_string(primary, "dataset", "primary_levels"),
        frequency=_require_string(primary, "frequency", "primary_levels"),
        unit=_require_string(primary, "unit", "primary_levels"),
        wage_indicator=_require_string(primary, "wage_indicator", "primary_levels"),
        productivity_indicator=_require_string(
            primary, "productivity_indicator", "primary_levels"
        ),
        comparator_countries=tuple(countries_raw),
        minimum_comparator_countries_per_year=_require_int(
            analysis, "minimum_comparator_countries_per_year", "analysis"
        ),
    )
