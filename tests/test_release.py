import gzip
import json
from pathlib import Path
from typing import cast

import pandas as pd

from pt_wage_gap.config import StudyConfig
from pt_wage_gap.pipeline import (
    analyse_level_panel,
    prepare_level_panel,
    prepare_level_panel_from_bulk,
)
from pt_wage_gap.provenance import freeze_design, sha256_file
from pt_wage_gap.release import (
    evaluate_primary_release,
    finalise_primary_release,
    write_release_status,
)
from pt_wage_gap.snapshots import SnapshotRole, import_jsonstat_snapshot
from pt_wage_gap.source_contract import (
    COMPENSATION_PER_EMPLOYEE,
    EU27_PPS_CURRENT_PRICE_INDEX,
    NOMINAL_PRODUCTIVITY_PER_PERSON,
)


def _config() -> StudyConfig:
    return StudyConfig(
        study_id="release-test",
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
        comparator_countries=("BE", "DE", "ES", "FR", "IT", "NL", "AT", "FI", "SE", "DK"),
        minimum_comparator_countries_per_year=8,
    )


def _write_config(repo_root: Path, config: StudyConfig) -> Path:
    path = repo_root / "configs" / "study.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    countries = "\n".join(f"    - {geo}" for geo in config.comparator_countries)
    path.write_text(
        f"""study:
  id: "{config.study_id}"
  country: "{config.country}"
  benchmark: "{config.benchmark}"
  start_year: {config.start_year}
  end_year: {config.end_year}
  latest_year_primary: {config.latest_year_primary}
  bootstrap_replications: {config.bootstrap_replications}
  bootstrap_seed: {config.bootstrap_seed}

primary_levels:
  source: "eurostat"
  dataset: "{config.dataset}"
  frequency: "{config.frequency}"
  unit: "{config.unit}"
  wage_indicator: "{config.wage_indicator}"
  productivity_indicator: "{config.productivity_indicator}"

comparators:
  countries:
{countries}

analysis:
  minimum_comparator_countries_per_year: {config.minimum_comparator_countries_per_year}
  primary_model: "pooled_log_levels_year_fe"
  exclude_portugal_from_model_fit: true
  report_cluster_robust_standard_errors: true
  bootstrap_cluster: "country"
  causal_language_allowed: false
""",
        encoding="utf-8",
    )
    return path


def _cube(config: StudyConfig, role: str) -> dict[str, object]:
    geos = [config.country, config.benchmark, *config.comparator_countries]
    years = list(range(config.start_year, config.end_year + 1))
    indicator = config.wage_indicator if role == "wage" else config.productivity_indicator
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
                    wage *= 0.84
            values.append(float(wage if role == "wage" else productivity))

    return {
        "id": ["freq", "unit", "na_item", "geo", "time"],
        "size": [1, 1, 1, len(geos), len(years)],
        "dimension": {
            "freq": {"category": {"index": {config.frequency: 0}}},
            "unit": {"category": {"index": {config.unit: 0}}},
            "na_item": {"category": {"index": {indicator: 0}}},
            "geo": {"category": {"index": {geo: i for i, geo in enumerate(geos)}}},
            "time": {
                "category": {"index": {str(year): i for i, year in enumerate(years)}}
            },
        },
        "value": values,
    }



def _bulk_source_bytes(config: StudyConfig) -> bytes:
    years = list(range(config.start_year, config.end_year + 1))
    geos = [config.country, config.benchmark, *config.comparator_countries]
    header = "freq,unit,na_item,geo\\TIME_PERIOD\t" + "\t".join(str(y) for y in years)
    lines = [header]

    for indicator in (config.wage_indicator, config.productivity_indicator):
        for geo_index, geo in enumerate(geos):
            observations: list[str] = []
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
                        wage *= 0.84
                value = wage if indicator == config.wage_indicator else productivity
                observations.append(f"{value:.12f}")
            key = f"{config.frequency},{config.unit},{indicator},{geo}"
            lines.append(key + "\t" + "\t".join(observations))
    return ("\n".join(lines) + "\n").encode("utf-8")

def _build_releasable_fixture(tmp_path: Path) -> tuple[StudyConfig, Path]:
    config = _config()
    repo_root = tmp_path / "repo"
    config_path = _write_config(repo_root, config)
    assert config_path.is_file()

    design_lock = repo_root / "artifacts" / "design_lock.json"
    freeze_design(repo_root, ["configs/study.yml"], design_lock)

    for role in ("wage", "productivity"):
        source = tmp_path / f"{role}.json"
        source.write_text(json.dumps(_cube(config, role)), encoding="utf-8")
        import_jsonstat_snapshot(
            source_path=source,
            role=cast(SnapshotRole, role),
            config=config,
            repo_root=repo_root,
        )

    prepare_level_panel(config, repo_root)
    analyse_level_panel(config, repo_root)
    return config, repo_root


def test_release_status_is_blocked_without_empirical_inputs(tmp_path: Path) -> None:
    config = _config()
    repo_root = tmp_path / "repo"
    _write_config(repo_root, config)

    report = evaluate_primary_release(config, repo_root)
    assert report.passed is False
    assert report.status == "blocked"
    assert report.evidence_tier == "none"
    assert {check.name for check in report.checks if not check.passed} >= {
        "design_lock",
        "canonical_panel",
        "source_provenance",
        "analysis_manifest",
        "bootstrap_gate",
    }

    status_path = write_release_status(config, repo_root)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert payload["passed"] is False


def test_complete_registered_snapshot_chain_can_be_finalised(tmp_path: Path) -> None:
    config, repo_root = _build_releasable_fixture(tmp_path)

    report = evaluate_primary_release(config, repo_root)
    assert report.passed is True
    assert report.status == "ready_for_primary_release"
    assert report.evidence_tier == "registered_eurostat_snapshot"

    output = finalise_primary_release(config, repo_root)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "empirical_primary"
    assert payload["target_year"] == 2024
    estimates = payload["headline_estimates"]
    assert estimates["excess_wage_log_gap"] < 0.0
    assert estimates["conditional_log_residual"] < 0.0
    assert estimates["wage_index_eu27_100"] > 0.0
    assert estimates["productivity_index_eu27_100"] > 0.0


def test_source_tampering_blocks_release_after_analysis(tmp_path: Path) -> None:
    config, repo_root = _build_releasable_fixture(tmp_path)
    raw = repo_root / "data" / "raw" / "eurostat" / "wage.json"
    raw.write_bytes(raw.read_bytes() + b"\n")

    report = evaluate_primary_release(config, repo_root)
    assert report.passed is False
    source_check = next(check for check in report.checks if check.name == "source_provenance")
    assert source_check.passed is False
    assert "SHA-256" in source_check.detail


def test_analysis_output_tampering_blocks_release(tmp_path: Path) -> None:
    config, repo_root = _build_releasable_fixture(tmp_path)
    residuals = repo_root / "results" / "estimates" / "pt_conditional_residuals.csv"
    residuals.write_text(residuals.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    report = evaluate_primary_release(config, repo_root)
    assert report.passed is False
    manifest_check = next(check for check in report.checks if check.name == "analysis_manifest")
    assert manifest_check.passed is False
    assert "SHA-256" in manifest_check.detail


def test_bulk_registered_snapshot_chain_can_pass_release_gate(tmp_path: Path) -> None:
    config = _config()
    repo_root = tmp_path / "repo"
    _write_config(repo_root, config)
    freeze_design(
        repo_root,
        ["configs/study.yml"],
        repo_root / "artifacts" / "design_lock.json",
    )

    source = tmp_path / "nama_10_lp_ulc.tsv.gz"
    source.write_bytes(gzip.compress(_bulk_source_bytes(config)))
    prepare_level_panel_from_bulk(config, repo_root, source)
    analyse_level_panel(config, repo_root)

    report = evaluate_primary_release(config, repo_root)
    assert report.passed is True
    assert report.evidence_tier == "registered_eurostat_snapshot"


def test_recalculation_catches_coordinated_residual_and_manifest_edit(tmp_path: Path) -> None:
    config, repo_root = _build_releasable_fixture(tmp_path)
    residual_path = repo_root / "results" / "estimates" / "pt_conditional_residuals.csv"
    residuals = pd.read_csv(residual_path)
    residuals.loc[residuals["year"] == 2024, "log_residual"] += 0.25
    residuals.to_csv(residual_path, index=False)

    manifest_path = repo_root / "results" / "estimates" / "analysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative = "results/estimates/pt_conditional_residuals.csv"
    manifest["outputs"][relative] = sha256_file(residual_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report = evaluate_primary_release(config, repo_root)
    manifest_check = next(check for check in report.checks if check.name == "analysis_manifest")
    recalc_check = next(check for check in report.checks if check.name == "result_recalculation")
    assert manifest_check.passed is True
    assert recalc_check.passed is False
    assert "recomputation" in recalc_check.detail


def test_bootstrap_consistency_catches_draw_edit_even_if_manifest_is_rehashed(
    tmp_path: Path,
) -> None:
    config, repo_root = _build_releasable_fixture(tmp_path)
    draws_path = repo_root / "results" / "estimates" / "primary_bootstrap_draws.csv"
    draws = pd.read_csv(draws_path)
    draws["log_residual"] = draws["log_residual"] + 1.0
    draws.to_csv(draws_path, index=False)

    manifest_path = repo_root / "results" / "estimates" / "analysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative = "results/estimates/primary_bootstrap_draws.csv"
    manifest["outputs"][relative] = sha256_file(draws_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report = evaluate_primary_release(config, repo_root)
    manifest_check = next(check for check in report.checks if check.name == "analysis_manifest")
    bootstrap_check = next(check for check in report.checks if check.name == "bootstrap_gate")
    assert manifest_check.passed is True
    assert bootstrap_check.passed is False
    assert "interval" in bootstrap_check.detail
