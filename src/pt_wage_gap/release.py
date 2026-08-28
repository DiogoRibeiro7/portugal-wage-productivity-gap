"""Machine-enforced gate for the first primary empirical release.

The scientific analysis can be executed independently of this module.  A result is
promoted to the primary empirical release only when its design lock, source-provenance
chain, canonical panel, analysis manifest and bootstrap success gate all verify.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, cast
from urllib.parse import parse_qsl, urlsplit

import numpy as np
import pandas as pd

from pt_wage_gap.bulk import EUROSTAT_BULK_TSV_URL
from pt_wage_gap.config import StudyConfig
from pt_wage_gap.econometrics import fit_and_predict
from pt_wage_gap.metrics import (
    DataValidationError,
    compute_pt_gaps,
    validate_eu_index_panel,
    validate_level_panel,
)
from pt_wage_gap.provenance import (
    sha256_file,
    utc_now_iso,
    verify_design_lock,
)
from pt_wage_gap.snapshots import SnapshotRole, canonical_query_url

PRIMARY_ANALYSIS_OUTPUTS = frozenset(
    {
        "results/tables/pt_gap_by_year.csv",
        "results/estimates/pt_conditional_residuals.csv",
        "results/estimates/primary_bootstrap.json",
        "results/estimates/primary_bootstrap_draws.csv",
    }
)


class ReleaseGateError(ValueError):
    """Raised when a primary empirical release is requested before the gate passes."""


@dataclass(frozen=True)
class GateCheck:
    """One deterministic primary-release gate check."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ReleaseGateReport:
    """Complete status of the primary empirical release gate."""

    status: str
    evidence_tier: str
    checks: tuple[GateCheck, ...]

    @property
    def passed(self) -> bool:
        """Return whether every required release check passed."""
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable representation."""
        return {
            "status": self.status,
            "passed": self.passed,
            "evidence_tier": self.evidence_tier,
            "checks": [asdict(check) for check in self.checks],
        }


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object or raise a release-specific error."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseGateError(f"Unable to read JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise ReleaseGateError(f"JSON root must be an object: {path}")
    return payload


def _same_url(left: str, right: str) -> bool:
    """Compare URLs while ignoring query-parameter ordering."""
    left_parts = urlsplit(left)
    right_parts = urlsplit(right)
    return (
        left_parts.scheme,
        left_parts.netloc,
        left_parts.path,
        sorted(parse_qsl(left_parts.query, keep_blank_values=True)),
    ) == (
        right_parts.scheme,
        right_parts.netloc,
        right_parts.path,
        sorted(parse_qsl(right_parts.query, keep_blank_values=True)),
    )


def _safe_relative_path(repo_root: Path, raw: object) -> Path:
    """Resolve a receipt path inside the repository and reject traversal."""
    if not isinstance(raw, str) or not raw:
        raise ReleaseGateError("Receipt contains no valid relative path")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReleaseGateError(f"Unsafe receipt path: {raw!r}")
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ReleaseGateError(f"Receipt path escapes repository: {raw!r}")
    return resolved


def _verify_bulk_provenance(
    *, repo_root: Path, config: StudyConfig, panel_receipt: Mapping[str, Any]
) -> str:
    """Verify the bulk-source receipt chain and return its evidence tier."""
    raw_path = _safe_relative_path(repo_root, panel_receipt.get("source_bulk_path"))
    raw_receipt_path = _safe_relative_path(
        repo_root, panel_receipt.get("source_bulk_receipt_path")
    )
    if not raw_path.is_file() or not raw_receipt_path.is_file():
        raise ReleaseGateError("Bulk raw file or raw receipt is missing")

    observed_raw_hash = sha256_file(raw_path)
    expected_raw_hash = panel_receipt.get("source_bulk_sha256")
    if observed_raw_hash != expected_raw_hash:
        raise ReleaseGateError("Bulk raw-file SHA-256 does not match panel receipt")
    if sha256_file(raw_receipt_path) != panel_receipt.get("source_bulk_receipt_sha256"):
        raise ReleaseGateError("Bulk raw-receipt SHA-256 does not match panel receipt")

    raw_receipt = _load_json_object(raw_receipt_path)
    if raw_receipt.get("dataset") != config.dataset:
        raise ReleaseGateError("Bulk receipt dataset does not match registered dataset")
    if raw_receipt.get("source_url") != EUROSTAT_BULK_TSV_URL:
        raise ReleaseGateError("Bulk receipt URL does not match registered Eurostat endpoint")
    if raw_receipt.get("sha256") != observed_raw_hash:
        raise ReleaseGateError("Bulk receipt does not bind the preserved provider bytes")
    if raw_receipt.get("bytes") != raw_path.stat().st_size:
        raise ReleaseGateError("Bulk receipt byte count does not match preserved provider bytes")
    return "registered_eurostat_snapshot"


def _receipt_request_url(receipt: Mapping[str, Any]) -> str:
    """Read the canonical/provider request URL from either JSON-stat receipt route."""
    value = receipt.get("request_url", receipt.get("canonical_request_url"))
    if not isinstance(value, str) or not value:
        raise ReleaseGateError("JSON-stat source receipt has no request URL")
    return value


def _verify_jsonstat_provenance(
    *, repo_root: Path, config: StudyConfig, panel_receipt: Mapping[str, Any]
) -> str:
    """Verify both JSON-stat source files and receipts."""
    for role in ("wage", "productivity"):
        raw_path = _safe_relative_path(repo_root, panel_receipt.get(f"source_{role}_path"))
        receipt_path = _safe_relative_path(
            repo_root, panel_receipt.get(f"source_{role}_receipt_path")
        )
        if not raw_path.is_file() or not receipt_path.is_file():
            raise ReleaseGateError(f"{role} raw file or receipt is missing")

        observed_hash = sha256_file(raw_path)
        if observed_hash != panel_receipt.get(f"source_{role}_sha256"):
            raise ReleaseGateError(f"{role} raw-file SHA-256 does not match panel receipt")
        if sha256_file(receipt_path) != panel_receipt.get(f"source_{role}_receipt_sha256"):
            raise ReleaseGateError(f"{role} receipt SHA-256 does not match panel receipt")

        receipt = _load_json_object(receipt_path)
        if receipt.get("dataset") != config.dataset:
            raise ReleaseGateError(f"{role} receipt dataset does not match registered dataset")
        if receipt.get("sha256") != observed_hash:
            raise ReleaseGateError(f"{role} receipt does not bind preserved source bytes")
        if receipt.get("bytes") != raw_path.stat().st_size:
            raise ReleaseGateError(f"{role} receipt byte count does not match source bytes")
        expected_url = canonical_query_url(config, cast(SnapshotRole, role))
        if not _same_url(_receipt_request_url(receipt), expected_url):
            raise ReleaseGateError(f"{role} receipt URL does not match registered query")
    return "registered_eurostat_snapshot"


def _verify_source_provenance(
    *, repo_root: Path, config: StudyConfig, panel_receipt: Mapping[str, Any]
) -> str:
    """Verify the complete source chain for the canonical primary panel."""
    mode = panel_receipt.get("acquisition_mode")
    if mode == "bulk_tsv":
        return _verify_bulk_provenance(
            repo_root=repo_root, config=config, panel_receipt=panel_receipt
        )
    if mode == "jsonstat":
        return _verify_jsonstat_provenance(
            repo_root=repo_root, config=config, panel_receipt=panel_receipt
        )
    raise ReleaseGateError(f"Unsupported or missing acquisition mode: {mode!r}")


def _hashes_match_manifest(repo_root: Path, manifest: Mapping[str, Any]) -> None:
    """Verify every output hash recorded by the analysis manifest."""
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping) or not outputs:
        raise ReleaseGateError("Analysis manifest has no output hash mapping")
    observed_paths = {str(path) for path in outputs}
    if observed_paths != PRIMARY_ANALYSIS_OUTPUTS:
        missing = sorted(PRIMARY_ANALYSIS_OUTPUTS.difference(observed_paths))
        extra = sorted(observed_paths.difference(PRIMARY_ANALYSIS_OUTPUTS))
        raise ReleaseGateError(
            f"Analysis output manifest has wrong members; missing={missing}, extra={extra}"
        )
    for relative_raw, expected_raw in outputs.items():
        if not isinstance(relative_raw, str) or not isinstance(expected_raw, str):
            raise ReleaseGateError("Analysis output manifest entries must be strings")
        path = _safe_relative_path(repo_root, relative_raw)
        if not path.is_file():
            raise ReleaseGateError(f"Analysis output is missing: {relative_raw}")
        if sha256_file(path) != expected_raw:
            raise ReleaseGateError(f"Analysis output SHA-256 mismatch: {relative_raw}")


def _verify_result_recalculation(
    *, config: StudyConfig, repo_root: Path, panel: pd.DataFrame
) -> None:
    """Recompute deterministic point estimates and compare them with stored outputs."""
    gap_path = repo_root / "results" / "tables" / "pt_gap_by_year.csv"
    residual_path = repo_root / "results" / "estimates" / "pt_conditional_residuals.csv"
    if not gap_path.is_file() or not residual_path.is_file():
        raise ReleaseGateError("Stored gap or residual output is missing")

    stored_gap = pd.read_csv(gap_path).sort_values("year").reset_index(drop=True)
    expected_gap = compute_pt_gaps(
        panel, country=config.country, benchmark=config.benchmark
    ).sort_values("year").reset_index(drop=True)
    if list(stored_gap.columns) != list(expected_gap.columns):
        raise ReleaseGateError("Stored gap table schema differs from deterministic recomputation")
    try:
        pd.testing.assert_frame_equal(
            stored_gap, expected_gap, check_exact=False, rtol=1e-12, atol=1e-12
        )
    except AssertionError as exc:
        raise ReleaseGateError("Stored gap table differs from deterministic recomputation") from exc

    _, expected_residuals = fit_and_predict(
        panel,
        country=config.country,
        comparator_countries=config.comparator_countries,
        cluster_robust=False,
    )
    stored_residuals = pd.read_csv(residual_path).sort_values("year").reset_index(drop=True)
    core = [
        "year",
        "observed_log_wage",
        "predicted_log_wage",
        "log_residual",
        "multiplicative_residual_pct",
    ]
    if not set(core).issubset(stored_residuals.columns):
        raise ReleaseGateError("Stored residual table is missing primary columns")
    stored_core = stored_residuals.loc[:, core]
    expected_core = expected_residuals.loc[:, core].sort_values("year").reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(
            stored_core, expected_core, check_exact=False, rtol=1e-12, atol=1e-12
        )
    except AssertionError as exc:
        raise ReleaseGateError(
            "Stored conditional residuals differ from deterministic recomputation"
        ) from exc


def _verify_bootstrap_consistency(
    *, config: StudyConfig, repo_root: Path, residuals_path: Path
) -> str:
    """Check bootstrap counts, quantiles and point estimate against stored draws."""
    bootstrap_path = repo_root / "results" / "estimates" / "primary_bootstrap.json"
    draws_path = repo_root / "results" / "estimates" / "primary_bootstrap_draws.csv"
    if not bootstrap_path.is_file() or not draws_path.is_file():
        raise ReleaseGateError("Bootstrap summary or draws are missing")

    bootstrap = _load_json_object(bootstrap_path)
    if bootstrap.get("target_year") != config.latest_year_primary:
        raise ReleaseGateError("Bootstrap target year differs from registered year")
    if bootstrap.get("requested_replications") != config.bootstrap_replications:
        raise ReleaseGateError("Bootstrap replication count differs from registered design")

    successful = bootstrap.get("successful_replications")
    if isinstance(successful, bool) or not isinstance(successful, int):
        raise ReleaseGateError("Bootstrap successful_replications must be an integer")
    draws = pd.read_csv(draws_path)
    if list(draws.columns) != ["log_residual"]:
        raise ReleaseGateError("Bootstrap-draw file has an unexpected schema")
    draw_values = draws["log_residual"].to_numpy(dtype=float)
    if len(draw_values) != successful:
        raise ReleaseGateError("Bootstrap draw count differs from successful_replications")
    if len(draw_values) == 0 or not np.isfinite(draw_values).all():
        raise ReleaseGateError("Bootstrap draws are empty or non-finite")

    requested = config.bootstrap_replications
    expected_rate = successful / requested
    observed_rate = float(bootstrap.get("success_rate", -1.0))
    if not math.isclose(observed_rate, expected_rate, rel_tol=0.0, abs_tol=1e-15):
        raise ReleaseGateError("Bootstrap success rate is inconsistent with replication counts")
    if bootstrap.get("gate_pass") is not (expected_rate >= 0.95):
        raise ReleaseGateError("Bootstrap gate_pass flag is inconsistent with success rate")
    if expected_rate < 0.95:
        raise ReleaseGateError(f"Bootstrap success gate failed: success_rate={expected_rate:.6f}")

    lower, upper = np.quantile(draw_values, [0.025, 0.975])
    if not math.isclose(float(bootstrap.get("ci95_lower")), float(lower), abs_tol=1e-12):
        raise ReleaseGateError("Bootstrap lower interval does not match stored draws")
    if not math.isclose(float(bootstrap.get("ci95_upper")), float(upper), abs_tol=1e-12):
        raise ReleaseGateError("Bootstrap upper interval does not match stored draws")

    residuals = pd.read_csv(residuals_path)
    target = residuals.loc[residuals["year"] == config.latest_year_primary, "log_residual"]
    if len(target) != 1:
        raise ReleaseGateError("Primary-year residual is unavailable or duplicated")
    point = float(bootstrap.get("point_estimate_log_residual"))
    if not math.isclose(point, float(target.iloc[0]), abs_tol=1e-12):
        raise ReleaseGateError("Bootstrap point estimate differs from stored primary residual")
    return f"{successful}/{requested} replications succeeded"


def evaluate_primary_release(config: StudyConfig, repo_root: Path) -> ReleaseGateReport:
    """Evaluate every condition required to promote results as primary evidence."""
    checks: list[GateCheck] = []
    evidence_tier = "none"

    design_lock_path = repo_root / "artifacts" / "design_lock.json"
    try:
        verify_design_lock(repo_root, design_lock_path)
    except (OSError, ValueError) as exc:
        checks.append(GateCheck("design_lock", False, str(exc)))
    else:
        checks.append(GateCheck("design_lock", True, "Current design lock verifies"))

    panel_path = repo_root / "data" / "processed" / "level_panel.csv"
    panel_receipt_path = repo_root / "data" / "processed" / "level_panel.receipt.json"
    panel_receipt: dict[str, Any] | None = None
    panel: pd.DataFrame | None = None

    if not panel_path.is_file():
        checks.append(GateCheck("canonical_panel", False, "Canonical level panel is absent"))
    else:
        try:
            panel = pd.read_csv(panel_path)
            validate_level_panel(panel)
            validate_eu_index_panel(panel, benchmark=config.benchmark)
        except (OSError, ValueError) as exc:
            checks.append(GateCheck("canonical_panel", False, str(exc)))
            panel = None
        else:
            checks.append(GateCheck("canonical_panel", True, "Panel and EU27=100 invariant verify"))

    if not panel_receipt_path.is_file():
        checks.append(GateCheck("panel_receipt", False, "Canonical panel receipt is absent"))
    else:
        try:
            panel_receipt = _load_json_object(panel_receipt_path)
            if not panel_path.is_file():
                raise ReleaseGateError("Panel receipt exists but canonical panel is absent")
            if panel_receipt.get("output_sha256") != sha256_file(panel_path):
                raise ReleaseGateError("Canonical panel SHA-256 does not match its receipt")
            if panel is not None:
                expected_metadata = {
                    "rows": int(len(panel)),
                    "countries": int(panel["geo"].nunique()),
                    "min_year": int(panel["year"].min()),
                    "max_year": int(panel["year"].max()),
                }
                for key, expected_value in expected_metadata.items():
                    if panel_receipt.get(key) != expected_value:
                        raise ReleaseGateError(
                            f"Canonical panel receipt metadata mismatch for {key}"
                        )
        except (OSError, ValueError) as exc:
            checks.append(GateCheck("panel_receipt", False, str(exc)))
            panel_receipt = None
        else:
            checks.append(GateCheck("panel_receipt", True, "Canonical panel receipt verifies"))

    if panel_receipt is None:
        checks.append(
            GateCheck("source_provenance", False, "No verified panel receipt for source audit")
        )
    else:
        try:
            evidence_tier = _verify_source_provenance(
                repo_root=repo_root, config=config, panel_receipt=panel_receipt
            )
        except (OSError, ValueError) as exc:
            checks.append(GateCheck("source_provenance", False, str(exc)))
            evidence_tier = "unverified"
        else:
            checks.append(
                GateCheck(
                    "source_provenance",
                    True,
                    "Preserved bytes and registered Eurostat receipt chain verify",
                )
            )

    if panel is None:
        checks.append(GateCheck("primary_year", False, "No verified panel to inspect"))
    else:
        required_geos = {config.country, config.benchmark, *config.comparator_countries}
        observed_geos = set(
            panel.loc[panel["year"] == config.latest_year_primary, "geo"].astype(str)
        )
        comparator_count = len(set(config.comparator_countries).intersection(observed_geos))
        missing_required = {config.country, config.benchmark}.difference(observed_geos)
        passed = (
            not missing_required
            and comparator_count >= config.minimum_comparator_countries_per_year
        )
        detail = (
            f"Primary year {config.latest_year_primary}: {comparator_count} comparators; "
            f"missing required geographies={sorted(missing_required)}"
        )
        checks.append(GateCheck("primary_year", passed, detail))

    analysis_manifest_path = repo_root / "results" / "estimates" / "analysis_manifest.json"
    analysis_manifest: dict[str, Any] | None = None
    if not analysis_manifest_path.is_file():
        checks.append(GateCheck("analysis_manifest", False, "Analysis manifest is absent"))
    else:
        try:
            analysis_manifest = _load_json_object(analysis_manifest_path)
            if analysis_manifest.get("study_id") != config.study_id:
                raise ReleaseGateError("Analysis manifest study_id differs from configuration")
            if not panel_path.is_file():
                raise ReleaseGateError("Analysis manifest exists but panel is absent")
            if analysis_manifest.get("input_panel_sha256") != sha256_file(panel_path):
                raise ReleaseGateError("Analysis manifest does not bind the current panel")
            if analysis_manifest.get("config_sha256") != sha256_file(
                repo_root / "configs" / "study.yml"
            ):
                raise ReleaseGateError("Analysis manifest does not bind the current study config")
            if analysis_manifest.get("input_panel_receipt_sha256") != sha256_file(
                panel_receipt_path
            ):
                raise ReleaseGateError("Analysis manifest does not bind the panel receipt")
            if analysis_manifest.get("design_lock_sha256") != sha256_file(design_lock_path):
                raise ReleaseGateError("Analysis manifest does not bind the current design lock")
            if analysis_manifest.get("target_year") != config.latest_year_primary:
                raise ReleaseGateError("Analysis manifest target year differs from registered year")
            _hashes_match_manifest(repo_root, analysis_manifest)
        except (OSError, ValueError) as exc:
            checks.append(GateCheck("analysis_manifest", False, str(exc)))
            analysis_manifest = None
        else:
            checks.append(
                GateCheck("analysis_manifest", True, "Analysis input and output hashes verify")
            )

    residuals_path = repo_root / "results" / "estimates" / "pt_conditional_residuals.csv"
    if analysis_manifest is None or panel is None:
        checks.append(
            GateCheck("result_recalculation", False, "Verified inputs or outputs are absent")
        )
    else:
        try:
            _verify_result_recalculation(config=config, repo_root=repo_root, panel=panel)
        except (ValueError, np.linalg.LinAlgError) as exc:
            checks.append(GateCheck("result_recalculation", False, str(exc)))
        else:
            checks.append(
                GateCheck(
                    "result_recalculation",
                    True,
                    "Gap and conditional residual outputs reproduce from the canonical panel",
                )
            )

    if analysis_manifest is None or not residuals_path.is_file():
        checks.append(GateCheck("bootstrap_gate", False, "Verified bootstrap result is absent"))
    else:
        try:
            bootstrap_detail = _verify_bootstrap_consistency(
                config=config, repo_root=repo_root, residuals_path=residuals_path
            )
        except (TypeError, ValueError) as exc:
            checks.append(GateCheck("bootstrap_gate", False, str(exc)))
        else:
            checks.append(GateCheck("bootstrap_gate", True, bootstrap_detail))

    passed = all(check.passed for check in checks)
    return ReleaseGateReport(
        status="ready_for_primary_release" if passed else "blocked",
        evidence_tier=evidence_tier,
        checks=tuple(checks),
    )


def write_release_status(
    config: StudyConfig, repo_root: Path, output_path: Path | None = None
) -> Path:
    """Evaluate and persist the current empirical release status."""
    report = evaluate_primary_release(config, repo_root)
    path = output_path or repo_root / "artifacts" / "release_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **report.to_dict(),
        "study_id": config.study_id,
        "target_year": config.latest_year_primary,
        "evaluated_at_utc": utc_now_iso(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def finalise_primary_release(config: StudyConfig, repo_root: Path) -> Path:
    """Write the first primary empirical manifest only when every gate passes."""
    report = evaluate_primary_release(config, repo_root)
    if not report.passed:
        failed = "; ".join(check.name for check in report.checks if not check.passed)
        raise ReleaseGateError(f"Primary empirical release is blocked by: {failed}")

    gap_path = repo_root / "results" / "tables" / "pt_gap_by_year.csv"
    residual_path = repo_root / "results" / "estimates" / "pt_conditional_residuals.csv"
    bootstrap_path = repo_root / "results" / "estimates" / "primary_bootstrap.json"
    gap = pd.read_csv(gap_path)
    residuals = pd.read_csv(residual_path)
    bootstrap = _load_json_object(bootstrap_path)

    gap_row = gap.loc[gap["year"] == config.latest_year_primary]
    residual_row = residuals.loc[residuals["year"] == config.latest_year_primary]
    if len(gap_row) != 1 or len(residual_row) != 1:
        raise ReleaseGateError("Primary-year result rows are unavailable or duplicated")

    gap_values = gap_row.iloc[0]
    residual_values = residual_row.iloc[0]
    analysis_manifest_path = repo_root / "results" / "estimates" / "analysis_manifest.json"
    panel_receipt_path = repo_root / "data" / "processed" / "level_panel.receipt.json"
    design_lock_path = repo_root / "artifacts" / "design_lock.json"

    lower = float(bootstrap["ci95_lower"])
    upper = float(bootstrap["ci95_upper"])
    excess_gap = float(gap_values["excess_wage_log_gap"])
    conditional_residual = float(residual_values["log_residual"])

    payload: dict[str, object] = {
        "status": "empirical_primary",
        "study_id": config.study_id,
        "target_year": config.latest_year_primary,
        "evidence_tier": report.evidence_tier,
        "created_at_utc": utc_now_iso(),
        "headline_estimates": {
            "wage_index_eu27_100": float(gap_values["wage_pt"]),
            "productivity_index_eu27_100": float(gap_values["productivity_pt"]),
            "wage_shortfall_pct": float(gap_values["wage_shortfall_pct"]),
            "productivity_shortfall_pct": float(gap_values["productivity_shortfall_pct"]),
            "excess_wage_log_gap": excess_gap,
            "excess_wage_ratio_pct": 100.0 * math.expm1(excess_gap),
            "conditional_log_residual": conditional_residual,
            "conditional_residual_pct": float(
                residual_values["multiplicative_residual_pct"]
            ),
            "bootstrap_ci95_log_residual": [lower, upper],
            "bootstrap_ci95_residual_pct": [
                100.0 * math.expm1(lower),
                100.0 * math.expm1(upper),
            ],
        },
        "directional_results": {
            "wage_gap_larger_than_productivity_gap": excess_gap < 0.0,
            "conditional_residual_negative": conditional_residual < 0.0,
            "bootstrap_interval_excludes_zero": lower > 0.0 or upper < 0.0,
        },
        "provenance": {
            "design_lock_sha256": sha256_file(design_lock_path),
            "panel_receipt_sha256": sha256_file(panel_receipt_path),
            "analysis_manifest_sha256": sha256_file(analysis_manifest_path),
            "config_sha256": sha256_file(repo_root / "configs" / "study.yml"),
        },
        "interpretation": (
            "Descriptive and predictive cross-country evidence only; no causal mechanism "
            "is identified by the primary residual."
        ),
    }
    output = repo_root / "results" / "primary_release_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
