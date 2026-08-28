"""Offline import and validation of downloaded Eurostat JSON-stat snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Mapping

from pt_wage_gap.config import StudyConfig
from pt_wage_gap.eurostat import EurostatQuery, jsonstat_to_frame
from pt_wage_gap.metrics import DataValidationError
from pt_wage_gap.provenance import sha256_bytes, utc_now_iso

SnapshotRole = Literal["wage", "productivity"]


def _expected_indicator(config: StudyConfig, role: SnapshotRole) -> str:
    return config.wage_indicator if role == "wage" else config.productivity_indicator


def primary_query(config: StudyConfig, role: SnapshotRole) -> EurostatQuery:
    """Build the exact registered query for one primary series."""
    geos = [config.country, config.benchmark, *config.comparator_countries]
    return EurostatQuery(
        dataset=config.dataset,
        filters={
            "freq": config.frequency,
            "unit": config.unit,
            "na_item": _expected_indicator(config, role),
            "geo": geos,
        },
        since_year=config.start_year,
        until_year=config.end_year,
    )


def canonical_query_url(config: StudyConfig, role: SnapshotRole) -> str:
    """Return the encoded Eurostat Statistics API URL for the registered query."""
    import requests

    query = primary_query(config, role)
    request = requests.Request(
        "GET",
        f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{query.dataset}",
        params=query.params(),
    ).prepare()
    if request.url is None:  # pragma: no cover - requests always sets it for an HTTP request
        raise RuntimeError("Unable to construct Eurostat query URL")
    return request.url


def _codes_from_dimension(payload: Mapping[str, Any], dimension: str) -> set[str]:
    dimensions = payload.get("dimension")
    if not isinstance(dimensions, Mapping):
        raise DataValidationError("JSON-stat snapshot has no dimension metadata")
    dim = dimensions.get(dimension)
    if not isinstance(dim, Mapping):
        raise DataValidationError(f"JSON-stat snapshot is missing {dimension!r}")
    category = dim.get("category")
    if not isinstance(category, Mapping):
        raise DataValidationError(f"JSON-stat {dimension!r} has no category metadata")
    index = category.get("index")
    if isinstance(index, Mapping):
        return {str(code) for code in index}
    if isinstance(index, list):
        return {str(code) for code in index}
    raise DataValidationError(f"JSON-stat {dimension!r} category index is invalid")


def validate_snapshot_payload(
    payload: Mapping[str, Any],
    *,
    config: StudyConfig,
    role: SnapshotRole,
) -> None:
    """Validate that a downloaded cube satisfies the registered primary query."""
    expected = {
        "freq": config.frequency,
        "unit": config.unit,
        "na_item": _expected_indicator(config, role),
    }
    for dimension, code in expected.items():
        observed = _codes_from_dimension(payload, dimension)
        if observed != {code}:
            raise DataValidationError(
                f"Snapshot {dimension!r} must contain exactly {code!r}; got {sorted(observed)}"
            )

    geos = _codes_from_dimension(payload, "geo")
    required_geos = {config.country, config.benchmark, *config.comparator_countries}
    missing_geos = required_geos.difference(geos)
    if missing_geos:
        raise DataValidationError(
            f"Snapshot is missing registered geographies: {sorted(missing_geos)}"
        )

    # Parsing here validates the JSON-stat cube structure before it is promoted to raw data.
    frame = jsonstat_to_frame(payload)
    if frame.empty:
        raise DataValidationError("Snapshot contains no observations")
    if "time" not in frame.columns:
        raise DataValidationError("Snapshot contains no time dimension")
    years = frame["time"].astype(int)
    if int(years.min()) > config.start_year or int(years.max()) < config.end_year:
        raise DataValidationError(
            "Snapshot does not cover the complete registered study window "
            f"{config.start_year}-{config.end_year}"
        )


def import_jsonstat_snapshot(
    *,
    source_path: Path,
    role: SnapshotRole,
    config: StudyConfig,
    repo_root: Path,
) -> tuple[Path, Path]:
    """Import a manually downloaded JSON-stat cube as immutable raw input.

    This path is intended for restricted execution environments.  The imported
    bytes are preserved exactly, validated against the registered query, and
    accompanied by a receipt before any analysis is permitted.
    """
    raw_bytes = source_path.read_bytes()
    try:
        decoded = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"Snapshot is not valid JSON: {source_path}") from exc
    if not isinstance(decoded, Mapping):
        raise DataValidationError("JSON-stat snapshot root must be an object")
    validate_snapshot_payload(decoded, config=config, role=role)

    raw_dir = repo_root / "data" / "raw" / "eurostat"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{role}.json"
    receipt_path = raw_dir / f"{role}.receipt.json"
    raw_path.write_bytes(raw_bytes)

    receipt = {
        "source": "Eurostat Statistics API — manually downloaded JSON-stat snapshot",
        "dataset": config.dataset,
        "role": role,
        "canonical_request_url": canonical_query_url(config, role),
        "imported_from": str(source_path.resolve()),
        "imported_at_utc": utc_now_iso(),
        "sha256": sha256_bytes(raw_bytes),
        "bytes": len(raw_bytes),
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return raw_path, receipt_path
