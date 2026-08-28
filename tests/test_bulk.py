import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from pt_wage_gap.bulk import (
    EUROSTAT_BULK_TSV_URL,
    extract_primary_bulk_frame,
    parse_eurostat_bulk_tsv,
)
from pt_wage_gap.config import StudyConfig
from pt_wage_gap.metrics import DataValidationError
from pt_wage_gap.pipeline import prepare_level_panel_from_bulk
from pt_wage_gap.provenance import sha256_bytes
from pt_wage_gap.source_contract import (
    COMPENSATION_PER_EMPLOYEE,
    EU27_PPS_CURRENT_PRICE_INDEX,
    NOMINAL_PRODUCTIVITY_PER_PERSON,
)


def _config() -> StudyConfig:
    return StudyConfig(
        study_id="bulk-test",
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


def _bulk_bytes(*, wrong_unit: bool = False) -> bytes:
    config = _config()
    unit = "WRONG_UNIT" if wrong_unit else config.unit
    geos = [config.country, config.benchmark, *config.comparator_countries]
    lines = ["freq,unit,na_item,geo\\TIME_PERIOD\t2023 \t2024 "]
    for indicator in (config.wage_indicator, config.productivity_indicator):
        for index, geo in enumerate(geos):
            if geo == config.benchmark:
                values = ("100.0", "100.0 p")
            elif indicator == config.wage_indicator:
                values = (f"{70.0 + index:.1f}", f"{71.0 + index:.1f}")
            else:
                values = (f"{80.0 + index:.1f}", f"{81.0 + index:.1f}")
            key = f"{config.frequency},{unit},{indicator},{geo}"
            lines.append(f"{key}\t{values[0]}\t{values[1]}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_bulk_parser_handles_plain_and_gzip_bytes() -> None:
    raw = _bulk_bytes()
    plain = parse_eurostat_bulk_tsv(raw)
    compressed = parse_eurostat_bulk_tsv(gzip.compress(raw))

    pd.testing.assert_frame_equal(plain, compressed)
    assert set(plain.columns) == {"freq", "unit", "na_item", "geo", "time", "value", "status"}
    assert set(plain["time"]) == {2023, 2024}
    eu_wage_2024 = plain.loc[
        (plain["geo"] == "EU27_2020")
        & (plain["na_item"] == COMPENSATION_PER_EMPLOYEE)
        & (plain["time"] == 2024)
    ].iloc[0]
    assert eu_wage_2024["value"] == pytest.approx(100.0)
    assert eu_wage_2024["status"] == "p"


def test_bulk_extract_rejects_wrong_registered_unit() -> None:
    frame = parse_eurostat_bulk_tsv(_bulk_bytes(wrong_unit=True))
    with pytest.raises(DataValidationError, match="registered source contract"):
        extract_primary_bulk_frame(frame, _config())


def test_bulk_import_preserves_provider_bytes_and_builds_panel(tmp_path: Path) -> None:
    config = _config()
    provider_bytes = gzip.compress(_bulk_bytes())
    source = tmp_path / "nama_10_lp_ulc.tsv.gz"
    source.write_bytes(provider_bytes)
    repo_root = tmp_path / "repo"

    panel_path = prepare_level_panel_from_bulk(config, repo_root, source)
    panel = pd.read_csv(panel_path)
    assert len(panel) == 5 * 2
    assert set(panel.loc[panel["geo"] == "EU27_2020", "wage"]) == {100.0}
    assert set(panel.loc[panel["geo"] == "EU27_2020", "productivity"]) == {100.0}

    raw_path = repo_root / "data" / "raw" / "eurostat" / "bulk" / "nama_10_lp_ulc.tsv.gz"
    raw_receipt_path = (
        repo_root / "data" / "raw" / "eurostat" / "bulk" / "nama_10_lp_ulc.receipt.json"
    )
    panel_receipt_path = repo_root / "data" / "processed" / "level_panel.receipt.json"
    assert raw_path.read_bytes() == provider_bytes

    raw_receipt = json.loads(raw_receipt_path.read_text(encoding="utf-8"))
    assert raw_receipt["source_url"] == EUROSTAT_BULK_TSV_URL
    assert raw_receipt["sha256"] == sha256_bytes(provider_bytes)
    assert raw_receipt["compression"] == "gzip"

    panel_receipt = json.loads(panel_receipt_path.read_text(encoding="utf-8"))
    assert panel_receipt["acquisition_mode"] == "bulk_tsv"
    assert panel_receipt["source_bulk_sha256"] == sha256_bytes(provider_bytes)
