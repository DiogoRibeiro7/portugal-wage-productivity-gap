"""Eurostat bulk-TSV import for restricted execution environments.

Eurostat's dataset download action exposes the complete ``nama_10_lp_ulc``
flow as TSV, optionally compressed with gzip.  This module preserves those
provider bytes, records their digest, parses the Eurostat wide-series format,
and extracts only the primary source contract registered by the study.
"""

from __future__ import annotations

import gzip
import io
import json
from pathlib import Path
from typing import Final

import pandas as pd

from pt_wage_gap.config import StudyConfig
from pt_wage_gap.metrics import DataValidationError
from pt_wage_gap.provenance import sha256_bytes, utc_now_iso

EUROSTAT_BULK_TSV_URL: Final = (
    "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
    "nama_10_lp_ulc/?compressed=true&format=TSV"
)
_GZIP_MAGIC: Final = b"\x1f\x8b"


def _decode_bulk_bytes(raw_bytes: bytes) -> str:
    """Decode plain or gzip-compressed Eurostat TSV bytes as UTF-8 text."""
    try:
        payload = gzip.decompress(raw_bytes) if raw_bytes.startswith(_GZIP_MAGIC) else raw_bytes
        return payload.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise DataValidationError("Eurostat bulk file is not valid UTF-8 TSV/gzip") from exc


def _parse_observation(cell: object) -> tuple[float | None, str | None]:
    """Parse one Eurostat bulk cell into numeric value and observation flags."""
    if cell is None or pd.isna(cell):
        return None, None
    text = str(cell).strip()
    if not text or text.startswith(":"):
        return None, text[1:].strip() or None

    parts = text.split()
    try:
        value = float(parts[0])
    except ValueError as exc:
        raise DataValidationError(f"Invalid Eurostat bulk observation: {text!r}") from exc
    status = " ".join(parts[1:]) or None
    return value, status


def parse_eurostat_bulk_tsv(raw_bytes: bytes) -> pd.DataFrame:
    """Parse the Eurostat wide-series TSV format into a tidy observation frame.

    Returns
    -------
    pandas.DataFrame
        Columns ``freq``, ``unit``, ``na_item``, ``geo``, ``time``, ``value``
        and ``status``. Missing observations remain in the frame with ``value``
        set to ``NaN`` so that subsequent filters can diagnose coverage.
    """
    text = _decode_bulk_bytes(raw_bytes)
    try:
        wide = pd.read_csv(io.StringIO(text), sep="\t", dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, ValueError) as exc:
        raise DataValidationError("Unable to parse Eurostat bulk TSV") from exc
    if wide.empty or len(wide.columns) < 2:
        raise DataValidationError("Eurostat bulk TSV contains no series or time columns")

    key_column = str(wide.columns[0])
    key_prefix = key_column.replace("\\TIME_PERIOD", "").strip()
    dimensions = [part.strip() for part in key_prefix.split(",") if part.strip()]
    if dimensions != ["freq", "unit", "na_item", "geo"]:
        raise DataValidationError(
            f"Unexpected Eurostat bulk series-key dimensions: {dimensions!r}"
        )

    keys = wide[key_column].astype(str).str.strip().str.split(",", expand=True)
    if keys.shape[1] != len(dimensions):
        raise DataValidationError("Eurostat bulk series keys do not match the header dimensions")
    keys.columns = dimensions

    year_columns = [column for column in wide.columns[1:] if str(column).strip().isdigit()]
    if not year_columns:
        raise DataValidationError("Eurostat bulk TSV contains no annual time columns")

    series = pd.concat(
        [keys.reset_index(drop=True), wide[year_columns].reset_index(drop=True)],
        axis=1,
    )
    long = series.melt(
        id_vars=dimensions,
        value_vars=year_columns,
        var_name="time",
        value_name="observation",
    )
    parsed = long["observation"].map(_parse_observation)
    long["value"] = [item[0] for item in parsed]
    long["status"] = [item[1] for item in parsed]
    long["time"] = long["time"].astype(str).str.strip().astype(int)
    return long.loc[:, [*dimensions, "time", "value", "status"]]


def extract_primary_bulk_frame(frame: pd.DataFrame, config: StudyConfig) -> pd.DataFrame:
    """Extract and validate the registered primary contract from a bulk dataset."""
    required_columns = {"freq", "unit", "na_item", "geo", "time", "value", "status"}
    missing = required_columns.difference(frame.columns)
    if missing:
        raise DataValidationError(f"Bulk frame is missing columns: {sorted(missing)}")

    required_geos = {config.country, config.benchmark, *config.comparator_countries}
    selected = frame.loc[
        (frame["freq"] == config.frequency)
        & (frame["unit"] == config.unit)
        & frame["na_item"].isin([config.wage_indicator, config.productivity_indicator])
        & frame["geo"].isin(required_geos)
        & frame["time"].between(config.start_year, config.end_year)
    ].copy()
    if selected.empty:
        raise DataValidationError(
            "Bulk TSV contains no observations for the registered source contract"
        )

    observed_items = set(selected["na_item"].unique())
    expected_items = {config.wage_indicator, config.productivity_indicator}
    if observed_items != expected_items:
        raise DataValidationError(
            f"Bulk TSV is missing registered indicators: {sorted(expected_items - observed_items)}"
        )

    observed_geos = set(selected["geo"].unique())
    missing_geos = required_geos - observed_geos
    if missing_geos:
        raise DataValidationError(
            f"Bulk TSV is missing registered geographies: {sorted(missing_geos)}"
        )

    years = selected["time"].astype(int)
    if int(years.min()) > config.start_year or int(years.max()) < config.end_year:
        raise DataValidationError(
            "Bulk TSV does not cover the complete registered study window "
            f"{config.start_year}-{config.end_year}"
        )
    return selected.reset_index(drop=True)


def preserve_bulk_source(
    *, source_path: Path, repo_root: Path, config: StudyConfig
) -> tuple[Path, Path, bytes]:
    """Preserve exact provider bulk bytes and write a content-addressed receipt."""
    raw_bytes = source_path.read_bytes()
    # Parse before promotion so malformed files never enter the canonical raw location.
    extract_primary_bulk_frame(parse_eurostat_bulk_tsv(raw_bytes), config)

    suffix = ".tsv.gz" if raw_bytes.startswith(_GZIP_MAGIC) else ".tsv"
    raw_dir = repo_root / "data" / "raw" / "eurostat" / "bulk"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{config.dataset}{suffix}"
    receipt_path = raw_dir / f"{config.dataset}.receipt.json"
    raw_path.write_bytes(raw_bytes)

    receipt = {
        "source": "Eurostat SDMX 2.1 bulk dataset download",
        "dataset": config.dataset,
        "source_url": EUROSTAT_BULK_TSV_URL,
        "imported_from": str(source_path.resolve()),
        "imported_at_utc": utc_now_iso(),
        "sha256": sha256_bytes(raw_bytes),
        "bytes": len(raw_bytes),
        "compression": "gzip" if raw_bytes.startswith(_GZIP_MAGIC) else "none",
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return raw_path, receipt_path, raw_bytes
