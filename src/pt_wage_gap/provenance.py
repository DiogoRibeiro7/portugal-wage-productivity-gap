"""Hashing, receipts and design-lock utilities."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, cast


class DesignLockError(ValueError):
    """Raised when a design-lock manifest is malformed or no longer matches."""


def sha256_bytes(data: bytes) -> str:
    """Return the hexadecimal SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _canonical_manifest_bytes(payload: Mapping[str, object]) -> bytes:
    """Serialise a lock payload exactly as used by the manifest digest."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def freeze_design(
    repo_root: Path, relative_paths: Iterable[str], output_path: Path
) -> dict[str, object]:
    """Create a deterministic manifest of files defining the empirical design.

    The timestamp documents when the lock was created; the file hashes define the
    substantive lock. The manifest does not claim that the study is confirmatory.
    """
    files: dict[str, str] = {}
    for relative in sorted(relative_paths):
        full_path = repo_root / relative
        if not full_path.is_file():
            raise FileNotFoundError(f"Design-lock input does not exist: {full_path}")
        files[relative] = sha256_file(full_path)

    payload: dict[str, object] = {
        "lock_type": "prospectively_locked_follow_up",
        "created_at_utc": utc_now_iso(),
        "files": files,
    }
    payload["manifest_sha256"] = sha256_bytes(_canonical_manifest_bytes(payload))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def verify_design_lock(repo_root: Path, manifest_path: Path) -> None:
    """Verify the manifest digest and every design-file digest.

    The check deliberately rejects absolute paths and parent traversal in the
    manifest before resolving any design file against the repository root.
    """
    try:
        raw_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DesignLockError(f"Unable to read design lock: {manifest_path}") from exc
    if not isinstance(raw_payload, dict):
        raise DesignLockError("Design-lock root must be a JSON object")

    expected_manifest = raw_payload.get("manifest_sha256")
    if not isinstance(expected_manifest, str) or not expected_manifest:
        raise DesignLockError("Design lock has no valid manifest_sha256")
    unsigned = dict(raw_payload)
    del unsigned["manifest_sha256"]
    observed_manifest = sha256_bytes(_canonical_manifest_bytes(unsigned))
    if observed_manifest != expected_manifest:
        raise DesignLockError(
            "Design-lock manifest SHA-256 mismatch: "
            f"expected {expected_manifest}, observed {observed_manifest}"
        )

    files_raw = raw_payload.get("files")
    if not isinstance(files_raw, dict) or not files_raw:
        raise DesignLockError("Design lock has no file digest mapping")

    root = repo_root.resolve()
    files = cast(dict[object, object], files_raw)
    for relative_raw, expected_raw in files.items():
        if not isinstance(relative_raw, str) or not isinstance(expected_raw, str):
            raise DesignLockError("Design-lock file entries must map strings to digests")
        relative = Path(relative_raw)
        if relative.is_absolute() or ".." in relative.parts:
            raise DesignLockError(f"Unsafe design-lock path: {relative_raw!r}")
        full_path = (root / relative).resolve()
        if not full_path.is_relative_to(root):
            raise DesignLockError(f"Design-lock path escapes repository: {relative_raw!r}")
        if not full_path.is_file():
            raise DesignLockError(f"Locked design file is missing: {relative_raw}")
        observed = sha256_file(full_path)
        if observed != expected_raw:
            raise DesignLockError(
                f"Design file SHA-256 mismatch for {relative_raw}: "
                f"expected {expected_raw}, observed {observed}"
            )


def verify_file_receipt(path: Path, expected_sha256: str) -> None:
    """Raise if a file no longer matches a recorded digest."""
    observed = sha256_file(path)
    if observed != expected_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {path}: expected {expected_sha256}, observed {observed}"
        )
