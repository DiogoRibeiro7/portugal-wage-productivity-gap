import json
from pathlib import Path

import pytest

from pt_wage_gap.config import StudyConfig
from pt_wage_gap.metrics import DataValidationError
from pt_wage_gap.snapshots import (
    canonical_query_url,
    import_jsonstat_snapshot,
    validate_snapshot_payload,
)
from pt_wage_gap.source_contract import (
    COMPENSATION_PER_EMPLOYEE,
    EU27_PPS_CURRENT_PRICE_INDEX,
    NOMINAL_PRODUCTIVITY_PER_PERSON,
)


def _config() -> StudyConfig:
    return StudyConfig(
        study_id="test",
        country="PT",
        benchmark="EU27_2020",
        start_year=2023,
        end_year=2024,
        latest_year_primary=2024,
        bootstrap_replications=10,
        bootstrap_seed=1,
        dataset="nama_10_lp_ulc",
        frequency="A",
        unit=EU27_PPS_CURRENT_PRICE_INDEX,
        wage_indicator=COMPENSATION_PER_EMPLOYEE,
        productivity_indicator=NOMINAL_PRODUCTIVITY_PER_PERSON,
        comparator_countries=("DE", "FR", "ES"),
        minimum_comparator_countries_per_year=3,
    )


def _payload(indicator: str) -> dict[str, object]:
    geos = ["PT", "EU27_2020", "DE", "FR", "ES"]
    return {
        "id": ["freq", "unit", "na_item", "geo", "time"],
        "size": [1, 1, 1, len(geos), 2],
        "dimension": {
            "freq": {"category": {"index": {"A": 0}}},
            "unit": {"category": {"index": {EU27_PPS_CURRENT_PRICE_INDEX: 0}}},
            "na_item": {"category": {"index": {indicator: 0}}},
            "geo": {"category": {"index": {geo: index for index, geo in enumerate(geos)}}},
            "time": {"category": {"index": {"2023": 0, "2024": 1}}},
        },
        "value": [80.0, 81.0, 100.0, 100.0, 110.0, 111.0, 105.0, 106.0, 90.0, 91.0],
    }


def test_snapshot_validation_accepts_exact_registered_cube() -> None:
    validate_snapshot_payload(_payload(COMPENSATION_PER_EMPLOYEE), config=_config(), role="wage")


def test_snapshot_validation_rejects_wrong_indicator() -> None:
    with pytest.raises(DataValidationError, match="na_item"):
        validate_snapshot_payload(
            _payload(NOMINAL_PRODUCTIVITY_PER_PERSON),
            config=_config(),
            role="wage",
        )


def test_offline_snapshot_import_preserves_exact_bytes_and_writes_receipt(tmp_path: Path) -> None:
    source = tmp_path / "wage-download.json"
    source.write_text(json.dumps(_payload(COMPENSATION_PER_EMPLOYEE)), encoding="utf-8")
    repo_root = tmp_path / "repo"

    raw_path, receipt_path = import_jsonstat_snapshot(
        source_path=source,
        role="wage",
        config=_config(),
        repo_root=repo_root,
    )

    assert raw_path.read_bytes() == source.read_bytes()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["role"] == "wage"
    assert receipt["dataset"] == "nama_10_lp_ulc"
    assert receipt["canonical_request_url"].startswith("https://ec.europa.eu/eurostat/api/")


def test_canonical_query_url_contains_exact_registered_codes() -> None:
    url = canonical_query_url(_config(), "productivity")
    assert "freq=A" in url
    assert f"unit={EU27_PPS_CURRENT_PRICE_INDEX}" in url
    assert f"na_item={NOMINAL_PRODUCTIVITY_PER_PERSON}" in url
    assert "geo=PT" in url
    assert "geo=EU27_2020" in url
