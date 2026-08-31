"""Command-line interface for the reproducible analysis pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence, cast

from pt_wage_gap.bulk import EUROSTAT_BULK_TSV_URL
from pt_wage_gap.config import load_config
from pt_wage_gap.eurostat import EurostatError
from pt_wage_gap.figures import plot_conditional_residuals, plot_gap_history
from pt_wage_gap.pipeline import (
    analyse_level_panel,
    fetch_primary_eurostat,
    prepare_level_panel,
    prepare_level_panel_from_bulk,
)
from pt_wage_gap.provenance import freeze_design, verify_design_lock
from pt_wage_gap.release import (
    ReleaseGateError,
    finalise_primary_release,
    write_release_status,
)
from pt_wage_gap.snapshots import SnapshotRole, canonical_query_url, import_jsonstat_snapshot

DESIGN_FILES = (
    "artifacts/source_contract_audit_v0.2.3.json",
    "artifacts/source_contract_execution_audit_v0.2.4.json",
    "configs/study.yml",
    "configs/source_registry.yml",
    "docs/empirical_design.md",
    "docs/data_sources.md",
    "docs/data_contracts.md",
    "src/pt_wage_gap/source_contract.py",
    "src/pt_wage_gap/cli.py",
    "src/pt_wage_gap/config.py",
    "src/pt_wage_gap/eurostat.py",
    "src/pt_wage_gap/snapshots.py",
    "src/pt_wage_gap/bulk.py",
    "src/pt_wage_gap/pipeline.py",
    "src/pt_wage_gap/release.py",
    "src/pt_wage_gap/metrics.py",
    "src/pt_wage_gap/econometrics.py",
    "scripts/run_pipeline.sh",
)


EMPIRICAL_EXECUTION_COMMANDS = frozenset(
    {
        "fetch-eurostat",
        "import-eurostat-json",
        "import-eurostat-bulk",
        "prepare",
        "analyse",
        "figures",
        "finalise-primary-release",
    }
)


def _repo_root(config_path: Path) -> Path:
    resolved = config_path.resolve()
    # configs/study.yml -> repository root
    return resolved.parent.parent


def _add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=Path("configs/study.yml"))


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="pt-wage-gap")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "freeze-design",
        "verify-design-lock",
        "validate-source-config",
        "show-source-queries",
        "show-bulk-source-url",
        "fetch-eurostat",
        "prepare",
        "analyse",
        "figures",
        "release-status",
        "finalise-primary-release",
    ):
        sub = subparsers.add_parser(command)
        _add_config_argument(sub)

    snapshot = subparsers.add_parser("import-eurostat-json")
    _add_config_argument(snapshot)
    snapshot.add_argument("--role", choices=("wage", "productivity"), required=True)
    snapshot.add_argument("--file", type=Path, required=True)

    bulk = subparsers.add_parser("import-eurostat-bulk")
    _add_config_argument(bulk)
    bulk.add_argument("--file", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested pipeline command."""
    args = build_parser().parse_args(argv)
    config_path: Path = args.config
    repo_root = _repo_root(config_path)

    if args.command == "freeze-design":
        output = repo_root / "artifacts" / "design_lock.json"
        freeze_design(repo_root, DESIGN_FILES, output)
        print(output)
        return 0
    if args.command == "verify-design-lock":
        manifest = repo_root / "artifacts" / "design_lock.json"
        verify_design_lock(repo_root, manifest)
        print("Design lock: valid")
        return 0

    config = load_config(config_path)
    if args.command in EMPIRICAL_EXECUTION_COMMANDS:
        verify_design_lock(repo_root, repo_root / "artifacts" / "design_lock.json")

    if args.command == "validate-source-config":
        # Loading the typed configuration already validates the exact source contract.
        print("Primary Eurostat source contract: valid")
        return 0
    if args.command == "show-source-queries":
        print(f"wage\t{canonical_query_url(config, 'wage')}")
        print(f"productivity\t{canonical_query_url(config, 'productivity')}")
        return 0
    if args.command == "show-bulk-source-url":
        print(EUROSTAT_BULK_TSV_URL)
        return 0
    if args.command == "import-eurostat-json":
        role = cast(SnapshotRole, args.role)
        raw_path, receipt_path = import_jsonstat_snapshot(
            source_path=args.file,
            role=role,
            config=config,
            repo_root=repo_root,
        )
        print(raw_path)
        print(receipt_path)
        return 0
    if args.command == "import-eurostat-bulk":
        print(prepare_level_panel_from_bulk(config, repo_root, args.file))
        return 0
    if args.command == "fetch-eurostat":
        try:
            fetch_primary_eurostat(config, repo_root)
        except EurostatError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0
    if args.command == "prepare":
        print(prepare_level_panel(config, repo_root))
        return 0
    if args.command == "analyse":
        for path in analyse_level_panel(config, repo_root).values():
            print(path)
        return 0
    if args.command == "figures":
        gap = repo_root / "results" / "tables" / "pt_gap_by_year.csv"
        residuals = repo_root / "results" / "estimates" / "pt_conditional_residuals.csv"
        plot_gap_history(gap, repo_root / "results" / "figures" / "gap_history.png")
        plot_conditional_residuals(
            residuals, repo_root / "results" / "figures" / "conditional_residuals.png"
        )
        return 0
    if args.command == "release-status":
        status_path = write_release_status(config, repo_root)
        print(status_path)
        return 0
    if args.command == "finalise-primary-release":
        try:
            output = finalise_primary_release(config, repo_root)
        except ReleaseGateError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(output)
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
