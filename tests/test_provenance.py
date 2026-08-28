import json
from pathlib import Path

import pytest

from pt_wage_gap.provenance import (
    DesignLockError,
    freeze_design,
    sha256_file,
    verify_design_lock,
    verify_file_receipt,
)


def test_receipt_verification_detects_tampering(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("original", encoding="utf-8")
    expected = sha256_file(artifact)
    verify_file_receipt(artifact, expected)

    artifact.write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_file_receipt(artifact, expected)


def test_design_lock_round_trip_and_file_tampering(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source = repo_root / "design.txt"
    source.parent.mkdir(parents=True)
    source.write_text("locked", encoding="utf-8")
    manifest = repo_root / "artifacts" / "design_lock.json"

    freeze_design(repo_root, ["design.txt"], manifest)
    verify_design_lock(repo_root, manifest)

    source.write_text("changed", encoding="utf-8")
    with pytest.raises(DesignLockError, match="Design file SHA-256 mismatch"):
        verify_design_lock(repo_root, manifest)


def test_design_lock_detects_manifest_tampering(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source = repo_root / "design.txt"
    source.parent.mkdir(parents=True)
    source.write_text("locked", encoding="utf-8")
    manifest = repo_root / "artifacts" / "design_lock.json"
    freeze_design(repo_root, ["design.txt"], manifest)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["lock_type"] = "tampered"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DesignLockError, match="manifest SHA-256 mismatch"):
        verify_design_lock(repo_root, manifest)
