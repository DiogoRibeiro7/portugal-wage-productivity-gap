"""End-to-end data preparation and analysis orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from pt_wage_gap.bulk import (
    extract_primary_bulk_frame,
    parse_eurostat_bulk_tsv,
    preserve_bulk_source,
)
from pt_wage_gap.config import StudyConfig
from pt_wage_gap.econometrics import cluster_bootstrap_target_residual, fit_and_predict
from pt_wage_gap.eurostat import (
    EurostatQuery,
    fetch_jsonstat,
    jsonstat_to_frame,
    write_raw_with_receipt,
)
from pt_wage_gap.metrics import (
    DataValidationError,
    compute_pt_gaps,
    validate_eu_index_panel,
    validate_level_panel,
)
from pt_wage_gap.provenance import sha256_file, utc_now_iso, verify_file_receipt
from pt_wage_gap.snapshots import primary_query


def _raw_paths(repo_root: Path, role: str) -> tuple[Path, Path]:
    base = repo_root / "data" / "raw" / "eurostat"
    return base / f"{role}.json", base / f"{role}.receipt.json"


def fetch_primary_eurostat(config: StudyConfig, repo_root: Path) -> None:
    """Fetch registered wage and productivity cubes from Eurostat."""
    queries = {
        "wage": primary_query(config, "wage"),
        "productivity": primary_query(config, "productivity"),
    }

    for role, query in queries.items():
        _, raw, request_url = fetch_jsonstat(query)
        raw_path, receipt_path = _raw_paths(repo_root, role)
        write_raw_with_receipt(
            payload_bytes=raw,
            request_url=request_url,
            query=query,
            raw_path=raw_path,
            receipt_path=receipt_path,
        )


def _read_verified_json(raw_path: Path, receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    expected = str(receipt["sha256"])
    verify_file_receipt(raw_path, expected)
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DataValidationError(f"Raw payload at {raw_path} is not an object")
    return payload


def _select_series(
    frame: pd.DataFrame, *, value_name: str, status_name: str
) -> pd.DataFrame:
    """Select the canonical fields from one tidy Eurostat indicator frame."""
    required = {"geo", "time", "value", "status"}
    missing = required.difference(frame.columns)
    if missing:
        raise DataValidationError(f"Eurostat parsed frame is missing: {sorted(missing)}")
    selected = frame.loc[frame["value"].notna(), ["geo", "time", "value", "status"]].copy()
    selected = selected.rename(
        columns={"time": "year", "value": value_name, "status": status_name}
    )
    selected["year"] = selected["year"].astype(int)
    return selected


def _write_level_panel(
    *,
    panel: pd.DataFrame,
    config: StudyConfig,
    repo_root: Path,
    source_receipt: dict[str, object],
) -> Path:
    """Validate and persist the canonical level panel with provenance."""
    panel = panel.sort_values(["geo", "year"]).reset_index(drop=True)
    validate_level_panel(panel)
    validate_eu_index_panel(panel, benchmark=config.benchmark)

    output = repo_root / "data" / "processed" / "level_panel.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False)

    receipt = {
        **source_receipt,
        "rows": int(len(panel)),
        "countries": int(panel["geo"].nunique()),
        "min_year": int(panel["year"].min()),
        "max_year": int(panel["year"].max()),
        "output_sha256": sha256_file(output),
    }
    receipt_path = repo_root / "data" / "processed" / "level_panel.receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output


def prepare_level_panel(config: StudyConfig, repo_root: Path) -> Path:
    """Build the canonical wage/productivity panel from verified JSON-stat cubes."""
    wage_raw, wage_receipt = _raw_paths(repo_root, "wage")
    prod_raw, prod_receipt = _raw_paths(repo_root, "productivity")
    if not wage_raw.exists() or not prod_raw.exists():
        raise FileNotFoundError("Run fetch-eurostat or import-eurostat-json before prepare")

    wage = jsonstat_to_frame(_read_verified_json(wage_raw, wage_receipt))
    productivity = jsonstat_to_frame(_read_verified_json(prod_raw, prod_receipt))
    wage_selected = _select_series(wage, value_name="wage", status_name="wage_status")
    prod_selected = _select_series(
        productivity, value_name="productivity", status_name="productivity_status"
    )
    panel = wage_selected.merge(prod_selected, on=["geo", "year"], how="inner")
    return _write_level_panel(
        panel=panel,
        config=config,
        repo_root=repo_root,
        source_receipt={
            "acquisition_mode": "jsonstat",
            "source_wage_path": str(wage_raw.relative_to(repo_root)),
            "source_wage_sha256": sha256_file(wage_raw),
            "source_wage_receipt_path": str(wage_receipt.relative_to(repo_root)),
            "source_wage_receipt_sha256": sha256_file(wage_receipt),
            "source_productivity_path": str(prod_raw.relative_to(repo_root)),
            "source_productivity_sha256": sha256_file(prod_raw),
            "source_productivity_receipt_path": str(prod_receipt.relative_to(repo_root)),
            "source_productivity_receipt_sha256": sha256_file(prod_receipt),
        },
    )


def prepare_level_panel_from_bulk(
    config: StudyConfig, repo_root: Path, source_path: Path
) -> Path:
    """Build the canonical panel from an official Eurostat bulk TSV download."""
    raw_path, receipt_path, raw_bytes = preserve_bulk_source(
        source_path=source_path, repo_root=repo_root, config=config
    )
    frame = extract_primary_bulk_frame(parse_eurostat_bulk_tsv(raw_bytes), config)
    wage = frame.loc[frame["na_item"] == config.wage_indicator]
    productivity = frame.loc[frame["na_item"] == config.productivity_indicator]
    wage_selected = _select_series(wage, value_name="wage", status_name="wage_status")
    prod_selected = _select_series(
        productivity, value_name="productivity", status_name="productivity_status"
    )
    panel = wage_selected.merge(prod_selected, on=["geo", "year"], how="inner")
    return _write_level_panel(
        panel=panel,
        config=config,
        repo_root=repo_root,
        source_receipt={
            "acquisition_mode": "bulk_tsv",
            "source_bulk_path": str(raw_path.relative_to(repo_root)),
            "source_bulk_sha256": sha256_file(raw_path),
            "source_bulk_receipt_path": str(receipt_path.relative_to(repo_root)),
            "source_bulk_receipt_sha256": sha256_file(receipt_path),
        },
    )


def analyse_level_panel(config: StudyConfig, repo_root: Path) -> dict[str, Path]:
    """Run primary descriptive and conditional-residual analyses."""
    panel_path = repo_root / "data" / "processed" / "level_panel.csv"
    if not panel_path.exists():
        raise FileNotFoundError("Run prepare before analyse")
    panel = pd.read_csv(panel_path)
    validate_level_panel(panel)
    validate_eu_index_panel(panel, benchmark=config.benchmark)

    comparator_count = int(
        panel.loc[panel["year"] == config.latest_year_primary, "geo"]
        .isin(config.comparator_countries)
        .sum()
    )
    if comparator_count < config.minimum_comparator_countries_per_year:
        raise DataValidationError(
            f"Only {comparator_count} comparator countries in primary year; "
            f"minimum is {config.minimum_comparator_countries_per_year}"
        )

    gap = compute_pt_gaps(panel, country=config.country, benchmark=config.benchmark)
    gap_path = repo_root / "results" / "tables" / "pt_gap_by_year.csv"
    gap_path.parent.mkdir(parents=True, exist_ok=True)
    gap.to_csv(gap_path, index=False)

    model, residuals = fit_and_predict(
        panel,
        country=config.country,
        comparator_countries=config.comparator_countries,
        cluster_robust=True,
    )
    residuals["model_nobs"] = int(model.result.nobs)
    residuals["comparator_countries"] = len(model.comparator_countries)
    residual_path = repo_root / "results" / "estimates" / "pt_conditional_residuals.csv"
    residual_path.parent.mkdir(parents=True, exist_ok=True)
    residuals.to_csv(residual_path, index=False)

    bootstrap, distribution = cluster_bootstrap_target_residual(
        panel,
        country=config.country,
        comparator_countries=config.comparator_countries,
        target_year=config.latest_year_primary,
        replications=config.bootstrap_replications,
        seed=config.bootstrap_seed,
    )
    bootstrap_path = repo_root / "results" / "estimates" / "primary_bootstrap.json"
    bootstrap_payload = {
        "target_year": config.latest_year_primary,
        "point_estimate_log_residual": bootstrap.point_estimate,
        "ci95_lower": bootstrap.lower,
        "ci95_upper": bootstrap.upper,
        "successful_replications": bootstrap.successful_replications,
        "requested_replications": bootstrap.requested_replications,
        "success_rate": bootstrap.success_rate,
        "gate_pass": bootstrap.success_rate >= 0.95,
    }
    bootstrap_path.write_text(
        json.dumps(bootstrap_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    dist_path = repo_root / "results" / "estimates" / "primary_bootstrap_draws.csv"
    pd.DataFrame({"log_residual": distribution}).to_csv(dist_path, index=False)

    panel_receipt_path = repo_root / "data" / "processed" / "level_panel.receipt.json"
    config_path = repo_root / "configs" / "study.yml"
    design_lock_path = repo_root / "artifacts" / "design_lock.json"
    outputs = {
        str(path.relative_to(repo_root)): sha256_file(path)
        for path in (gap_path, residual_path, bootstrap_path, dist_path)
    }
    analysis_manifest = {
        "study_id": config.study_id,
        "target_year": config.latest_year_primary,
        "created_at_utc": utc_now_iso(),
        "input_panel_sha256": sha256_file(panel_path),
        "input_panel_receipt_sha256": (
            sha256_file(panel_receipt_path) if panel_receipt_path.is_file() else None
        ),
        "config_sha256": sha256_file(config_path) if config_path.is_file() else None,
        "design_lock_sha256": (
            sha256_file(design_lock_path) if design_lock_path.is_file() else None
        ),
        "model": "log_wage ~ log_productivity + year_fixed_effects",
        "target_country_excluded_from_fit": config.country,
        "comparator_countries": list(config.comparator_countries),
        "bootstrap_replications": config.bootstrap_replications,
        "bootstrap_seed": config.bootstrap_seed,
        "outputs": outputs,
    }
    analysis_manifest_path = repo_root / "results" / "estimates" / "analysis_manifest.json"
    analysis_manifest_path.write_text(
        json.dumps(analysis_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return {
        "gap": gap_path,
        "residuals": residual_path,
        "bootstrap": bootstrap_path,
        "bootstrap_draws": dist_path,
        "analysis_manifest": analysis_manifest_path,
    }
