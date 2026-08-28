from pathlib import Path

import pytest
import yaml

from pt_wage_gap.config import ConfigError, load_config
from pt_wage_gap.source_contract import (
    COMPENSATION_PER_EMPLOYEE,
    EU27_PPS_CURRENT_PRICE_INDEX,
    NOMINAL_PRODUCTIVITY_PER_PERSON,
)


def test_repository_config_loads_with_registered_source_contract() -> None:
    config = load_config(Path("configs/study.yml"))
    assert config.country == "PT"
    assert config.benchmark == "EU27_2020"
    assert config.frequency == "A"
    assert config.unit == EU27_PPS_CURRENT_PRICE_INDEX
    assert config.wage_indicator == COMPENSATION_PER_EMPLOYEE
    assert config.productivity_indicator == NOMINAL_PRODUCTIVITY_PER_PERSON
    assert config.latest_year_primary == 2024
    assert "DE" in config.comparator_countries
    assert "PT" not in config.comparator_countries


def test_total_economy_productivity_identifier_is_nlpr_emp() -> None:
    """Pin the Eurostat total-economy namespace independently of YAML configuration."""
    assert NOMINAL_PRODUCTIVITY_PER_PERSON == "NLPR_EMP"


def test_obsolete_v01_unit_code_is_rejected(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("configs/study.yml").read_text(encoding="utf-8"))
    payload["primary_levels"]["unit"] = "CP_MPPS"
    config_path = tmp_path / "study.yml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ConfigError, match="source contract mismatch"):
        load_config(config_path)


def test_regional_nlpr_per_code_is_rejected_for_total_economy_contract(
    tmp_path: Path,
) -> None:
    payload = yaml.safe_load(Path("configs/study.yml").read_text(encoding="utf-8"))
    payload["primary_levels"]["productivity_indicator"] = "NLPR_PER"
    config_path = tmp_path / "study.yml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ConfigError, match="source contract mismatch"):
        load_config(config_path)


def test_missing_required_source_field_has_config_error(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("configs/study.yml").read_text(encoding="utf-8"))
    del payload["primary_levels"]["frequency"]
    config_path = tmp_path / "study.yml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ConfigError, match=r"primary_levels\.frequency"):
        load_config(config_path)


def test_integer_fields_reject_string_coercion(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("configs/study.yml").read_text(encoding="utf-8"))
    payload["study"]["start_year"] = "2000"
    config_path = tmp_path / "study.yml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ConfigError, match=r"study\.start_year must be an integer"):
        load_config(config_path)
