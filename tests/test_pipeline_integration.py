import json
import math
from pathlib import Path
from typing import cast

import pandas as pd

from pt_wage_gap.config import StudyConfig
from pt_wage_gap.pipeline import analyse_level_panel, prepare_level_panel
from pt_wage_gap.snapshots import SnapshotRole, import_jsonstat_snapshot
from pt_wage_gap.source_contract import (
    COMPENSATION_PER_EMPLOYEE,
    EU27_PPS_CURRENT_PRICE_INDEX,
    NOMINAL_PRODUCTIVITY_PER_PERSON,
)


def _config() -> StudyConfig:
    comparators = ("BE", "DE", "ES", "FR", "IT", "NL", "AT", "FI", "SE", "DK")
    return StudyConfig(
        study_id="integration",
        country="PT",
        benchmark="EU27_2020",
        start_year=2020,
        end_year=2024,
        latest_year_primary=2024,
        bootstrap_replications=40,
        bootstrap_seed=19,
        dataset="nama_10_lp_ulc",
        frequency="A",
        unit=EU27_PPS_CURRENT_PRICE_INDEX,
        wage_indicator=COMPENSATION_PER_EMPLOYEE,
        productivity_indicator=NOMINAL_PRODUCTIVITY_PER_PERSON,
        comparator_countries=comparators,
        minimum_comparator_countries_per_year=8,
    )


def _cube(config: StudyConfig, *, role: str) -> dict[str, object]:
    geos = [config.country, config.benchmark, *config.comparator_countries]
    years = list(range(config.start_year, config.end_year + 1))
    indicator = (
        config.wage_indicator if role == "wage" else config.productivity_indicator
    )

    values: list[float] = []
    for geo_index, geo in enumerate(geos):
        for year_index, _year in enumerate(years):
            if geo == config.benchmark:
                productivity = 100.0
                wage = 100.0
            else:
                base = 72.0 + 4.5 * geo_index
                trend = 1.0 + (0.005 + 0.001 * geo_index) * year_index
                productivity = base * trend
                wage = 100.0 * (productivity / 100.0) ** 0.78
                if geo == config.country:
                    # Plant a persistent Portuguese compensation penalty.
                    wage *= 0.84
            values.append(float(wage if role == "wage" else productivity))

    return {
        "id": ["freq", "unit", "na_item", "geo", "time"],
        "size": [1, 1, 1, len(geos), len(years)],
        "dimension": {
            "freq": {"category": {"index": {config.frequency: 0}}},
            "unit": {"category": {"index": {config.unit: 0}}},
            "na_item": {"category": {"index": {indicator: 0}}},
            "geo": {
                "category": {
                    "index": {geo: index for index, geo in enumerate(geos)}
                }
            },
            "time": {
                "category": {
                    "index": {str(year): index for index, year in enumerate(years)}
                }
            },
        },
        "value": values,
    }


def test_offline_import_prepare_and_analysis_are_end_to_end(tmp_path: Path) -> None:
    config = _config()
    repo_root = tmp_path / "repo"

    for role in ("wage", "productivity"):
        source = tmp_path / f"{role}.json"
        source.write_text(json.dumps(_cube(config, role=role)), encoding="utf-8")
        import_jsonstat_snapshot(
            source_path=source,
            role=cast(SnapshotRole, role),
            config=config,
            repo_root=repo_root,
        )

    panel_path = prepare_level_panel(config, repo_root)
    panel = pd.read_csv(panel_path)
    assert len(panel) == 12 * 5
    assert set(panel.loc[panel["geo"] == "EU27_2020", "wage"]) == {100.0}
    assert set(panel.loc[panel["geo"] == "EU27_2020", "productivity"]) == {100.0}

    outputs = analyse_level_panel(config, repo_root)
    gaps = pd.read_csv(outputs["gap"])
    latest_gap = gaps.loc[gaps["year"] == 2024].iloc[0]
    assert latest_gap["excess_wage_log_gap"] < 0.0

    residuals = pd.read_csv(outputs["residuals"])
    latest_residual = float(residuals.loc[residuals["year"] == 2024, "log_residual"].item())
    assert latest_residual < 0.0
    assert math.isfinite(latest_residual)

    bootstrap = json.loads(outputs["bootstrap"].read_text(encoding="utf-8"))
    assert bootstrap["gate_pass"] is True
    assert bootstrap["successful_replications"] >= 38
