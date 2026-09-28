import json
from pathlib import Path

import pytest
from dataexcept import FileReadError, FileWriteError

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


def test_hash_failure_retains_path_and_original_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileReadError) as caught:
        sha256_file(missing)
    assert caught.value.path == str(missing)
    assert isinstance(caught.value.original, FileNotFoundError)
    assert caught.value.__cause__ is caught.value.original


def test_design_lock_read_failure_preserves_public_error(tmp_path: Path) -> None:
    missing = tmp_path / "design_lock.json"
    with pytest.raises(DesignLockError, match="Unable to read design lock") as caught:
        verify_design_lock(tmp_path, missing)
    assert isinstance(caught.value.__cause__, FileReadError)
    assert caught.value.__cause__.path == str(missing)
    assert isinstance(caught.value.__cause__.original, FileNotFoundError)


def test_freeze_design_write_failure_retains_output_path(tmp_path: Path) -> None:
    source = tmp_path / "design.txt"
    source.write_text("locked", encoding="utf-8")
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    output = blocker / "design_lock.json"

    with pytest.raises(FileWriteError) as caught:
        freeze_design(tmp_path, ["design.txt"], output)
    assert caught.value.path == str(output)
    assert isinstance(caught.value.original, OSError)
    assert caught.value.__cause__ is caught.value.original
