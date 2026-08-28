from pathlib import Path

import pytest

from pt_wage_gap.bulk import EUROSTAT_BULK_TSV_URL
from pt_wage_gap.cli import main
from pt_wage_gap.provenance import DesignLockError, freeze_design


def test_validate_source_config_command(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["validate-source-config", "--config", "configs/study.yml"])
    assert result == 0
    assert capsys.readouterr().out.strip() == "Primary Eurostat source contract: valid"


def test_show_bulk_source_url_command(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["show-bulk-source-url", "--config", "configs/study.yml"])
    assert result == 0
    assert capsys.readouterr().out.strip() == EUROSTAT_BULK_TSV_URL


def test_verify_design_lock_command_uses_manifest_without_loading_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    configs = repo_root / "configs"
    configs.mkdir(parents=True)
    config_path = configs / "study.yml"
    design_file = repo_root / "design.txt"
    design_file.write_text("locked", encoding="utf-8")
    manifest = repo_root / "artifacts" / "design_lock.json"
    freeze_design(repo_root, ["design.txt"], manifest)

    result = main(["verify-design-lock", "--config", str(config_path)])
    assert result == 0
    assert capsys.readouterr().out.strip() == "Design lock: valid"


def test_empirical_cli_command_requires_valid_design_lock(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    configs = repo_root / "configs"
    configs.mkdir(parents=True)
    config_path = configs / "study.yml"
    config_path.write_text(Path("configs/study.yml").read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(DesignLockError, match="Unable to read design lock"):
        main(["analyse", "--config", str(config_path)])


def test_repository_runner_verifies_lock_instead_of_refreezing() -> None:
    script = Path("scripts/run_pipeline.sh").read_text(encoding="utf-8")
    assert "verify-design-lock" in script
    assert "freeze-design" not in script


def test_finalise_primary_release_reports_blocked_gate_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = tmp_path / "repo"
    configs = repo_root / "configs"
    configs.mkdir(parents=True)
    config_path = configs / "study.yml"
    config_path.write_text(Path("configs/study.yml").read_text(encoding="utf-8"), encoding="utf-8")

    # The command itself requires a valid pre-existing lock. A minimal lock is
    # sufficient here because this test targets the user-facing release error.
    freeze_design(repo_root, ["configs/study.yml"], repo_root / "artifacts" / "design_lock.json")

    result = main(["finalise-primary-release", "--config", str(config_path)])
    captured = capsys.readouterr()
    assert result == 2
    assert "Primary empirical release is blocked by" in captured.err
    assert "Traceback" not in captured.err
