"""Minimal Eurostat Statistics API client and JSON-stat 2.0 parser."""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
import requests

from pt_wage_gap.provenance import sha256_bytes, utc_now_iso

EUROSTAT_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


class EurostatError(RuntimeError):
    """Raised for invalid or failed Eurostat API responses."""


@dataclass(frozen=True)
class EurostatQuery:
    """A reproducible query against one Eurostat dataset."""

    dataset: str
    filters: Mapping[str, str | Sequence[str]]
    since_year: int | None = None
    until_year: int | None = None

    def params(self) -> list[tuple[str, str]]:
        """Return ordered request parameters, preserving repeated dimensions."""
        params: list[tuple[str, str]] = [("lang", "EN")]
        for key in sorted(self.filters):
            value = self.filters[key]
            if isinstance(value, str):
                params.append((key, value))
            else:
                params.extend((key, item) for item in value)
        if self.since_year is not None:
            params.append(("sinceTimePeriod", str(self.since_year)))
        if self.until_year is not None:
            params.append(("untilTimePeriod", str(self.until_year)))
        return params


def fetch_jsonstat(
    query: EurostatQuery,
    *,
    timeout_seconds: float = 60.0,
    session: requests.Session | None = None,
) -> tuple[dict[str, Any], bytes, str]:
    """Fetch one Eurostat JSON-stat response.

    Returns the decoded payload, exact raw bytes, and final request URL.
    """
    client = session or requests.Session()
    url = f"{EUROSTAT_BASE_URL}/{query.dataset}"
    try:
        response = client.get(url, params=query.params(), timeout=timeout_seconds)
    except requests.RequestException as exc:
        raise EurostatError(f"Eurostat request failed: {exc}") from exc
    if response.status_code != 200:
        raise EurostatError(f"Eurostat HTTP {response.status_code}: {response.text[:500]}")

    raw = response.content
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise EurostatError("Eurostat returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise EurostatError("Eurostat response root is not an object")
    if "error" in payload:
        raise EurostatError(f"Eurostat API error: {payload['error']}")
    if "warning" in payload and "value" not in payload:
        raise EurostatError(f"Eurostat asynchronous/warning response: {payload['warning']}")

    return payload, raw, response.url


def write_raw_with_receipt(
    *,
    payload_bytes: bytes,
    request_url: str,
    query: EurostatQuery,
    raw_path: Path,
    receipt_path: Path,
) -> None:
    """Write exact provider bytes and a content-addressed receipt."""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(payload_bytes)

    receipt = {
        "source": "Eurostat Statistics API",
        "dataset": query.dataset,
        "request_url": request_url,
        "query_params": query.params(),
        "retrieved_at_utc": utc_now_iso(),
        "sha256": sha256_bytes(payload_bytes),
        "bytes": len(payload_bytes),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _category_codes(category: Mapping[str, Any], size: int) -> list[str]:
    index = category.get("index")
    if isinstance(index, list):
        codes = [str(item) for item in index]
    elif isinstance(index, dict):
        ordered = sorted(((int(position), str(code)) for code, position in index.items()))
        codes = [code for _, code in ordered]
    else:
        raise EurostatError("JSON-stat category.index has unsupported structure")
    if len(codes) != size:
        raise EurostatError("JSON-stat category size does not match dimension size")
    return codes


def _flat_values(payload: Mapping[str, Any], n_cells: int) -> list[float | None]:
    values_raw = payload.get("value")
    values: list[float | None] = [None] * n_cells
    if isinstance(values_raw, list):
        if len(values_raw) != n_cells:
            raise EurostatError("JSON-stat value vector has unexpected length")
        for idx, value in enumerate(values_raw):
            values[idx] = None if value is None else float(value)
        return values
    if isinstance(values_raw, dict):
        for key, value in values_raw.items():
            position = int(key)
            if position < 0 or position >= n_cells:
                raise EurostatError("JSON-stat sparse value index is out of bounds")
            values[position] = None if value is None else float(value)
        return values
    raise EurostatError("JSON-stat payload has no supported value container")


def _flat_status(payload: Mapping[str, Any], n_cells: int) -> list[str | None]:
    raw = payload.get("status")
    status: list[str | None] = [None] * n_cells
    if raw is None:
        return status
    if isinstance(raw, list):
        if len(raw) != n_cells:
            raise EurostatError("JSON-stat status vector has unexpected length")
        return [None if item is None else str(item) for item in raw]
    if isinstance(raw, dict):
        for key, value in raw.items():
            status[int(key)] = None if value is None else str(value)
        return status
    raise EurostatError("JSON-stat status has unsupported structure")


def jsonstat_to_frame(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Convert a Eurostat JSON-stat 2.0 cube to a tidy data frame.

    The function is generic over dimension order and handles dense or sparse
    JSON-stat value containers.
    """
    ids_raw = payload.get("id")
    sizes_raw = payload.get("size")
    dimensions_raw = payload.get("dimension")
    if not isinstance(ids_raw, list) or not all(isinstance(item, str) for item in ids_raw):
        raise EurostatError("JSON-stat id must be a list of strings")
    if not isinstance(sizes_raw, list) or not all(isinstance(item, int) for item in sizes_raw):
        raise EurostatError("JSON-stat size must be a list of integers")
    if not isinstance(dimensions_raw, Mapping):
        raise EurostatError("JSON-stat dimension must be an object")
    if len(ids_raw) != len(sizes_raw):
        raise EurostatError("JSON-stat id and size lengths differ")

    code_vectors: list[list[str]] = []
    label_maps: dict[str, Mapping[str, Any]] = {}
    for dim_id, dim_size in zip(ids_raw, sizes_raw, strict=True):
        dim = dimensions_raw.get(dim_id)
        if not isinstance(dim, Mapping):
            raise EurostatError(f"Missing dimension metadata for {dim_id}")
        category = dim.get("category")
        if not isinstance(category, Mapping):
            raise EurostatError(f"Missing category metadata for {dim_id}")
        code_vectors.append(_category_codes(category, dim_size))
        label = category.get("label")
        label_maps[dim_id] = label if isinstance(label, Mapping) else {}

    n_cells = 1
    for size in sizes_raw:
        n_cells *= size
    if n_cells == 0:
        raise EurostatError(
            "JSON-stat response contains no observations for the requested dimensions"
        )
    values = _flat_values(payload, n_cells)
    statuses = _flat_status(payload, n_cells)

    rows: list[dict[str, object]] = []
    for flat_index, positions in enumerate(itertools.product(*(range(size) for size in sizes_raw))):
        value = values[flat_index]
        if value is None:
            continue
        row: dict[str, object] = {"value": value, "status": statuses[flat_index]}
        for dim_id, codes, position in zip(ids_raw, code_vectors, positions, strict=True):
            code = codes[position]
            row[dim_id] = code
            row[f"{dim_id}_label"] = label_maps[dim_id].get(code)
        rows.append(row)

    return pd.DataFrame(rows)
