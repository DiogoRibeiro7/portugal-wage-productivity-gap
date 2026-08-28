"""Core wage-productivity gap estimands and validation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


class DataValidationError(ValueError):
    """Raised when an empirical input violates the registered data contract."""


@dataclass(frozen=True)
class GapEstimate:
    """One annual Portuguese wage/productivity gap observation."""

    year: int
    wage_log_gap: float
    productivity_log_gap: float
    excess_wage_log_gap: float
    wage_shortfall_pct: float
    productivity_shortfall_pct: float


def validate_level_panel(panel: pd.DataFrame) -> None:
    """Validate the canonical level panel required by the primary analysis."""
    required = {"geo", "year", "wage", "productivity"}
    missing = required.difference(panel.columns)
    if missing:
        raise DataValidationError(f"Missing required columns: {sorted(missing)}")
    if panel.empty:
        raise DataValidationError("Level panel is empty")
    if panel[["geo", "year"]].duplicated().any():
        raise DataValidationError("(geo, year) must be unique")

    for column in ("wage", "productivity"):
        numeric = pd.to_numeric(panel[column], errors="coerce")
        if numeric.isna().any():
            raise DataValidationError(f"{column} contains missing or non-numeric values")
        values = numeric.to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise DataValidationError(f"{column} contains non-finite values")
        if (values <= 0).any():
            raise DataValidationError(f"{column} must be strictly positive")


def validate_eu_index_panel(
    panel: pd.DataFrame,
    *,
    benchmark: str,
    expected_index: float = 100.0,
    tolerance: float = 0.2,
) -> None:
    """Validate the EU-index invariant for the primary PPS comparison.

    The registered Eurostat unit expresses each country as a percentage of the
    EU27 benchmark.  Benchmark observations should therefore be 100 apart from
    harmless provider rounding.  A failure usually indicates a wrong unit or
    an incorrectly combined source extract.
    """
    validate_level_panel(panel)
    if tolerance <= 0:
        raise DataValidationError("EU-index tolerance must be positive")
    benchmark_rows = panel.loc[panel["geo"] == benchmark]
    if benchmark_rows.empty:
        raise DataValidationError(f"Benchmark {benchmark!r} is absent from the level panel")
    for column in ("wage", "productivity"):
        deviations = (benchmark_rows[column].astype(float) - expected_index).abs()
        if (deviations > tolerance).any():
            worst = float(deviations.max())
            raise DataValidationError(
                f"{column} benchmark is not an EU27=100 index; maximum deviation is {worst:.3f}"
            )


def log_gap(value: float, benchmark: float) -> float:
    """Return log(value / benchmark) for positive finite inputs."""
    if not math.isfinite(value) or not math.isfinite(benchmark):
        raise DataValidationError("Gap inputs must be finite")
    if value <= 0 or benchmark <= 0:
        raise DataValidationError("Gap inputs must be strictly positive")
    return math.log(value / benchmark)


def shortfall_pct(value: float, benchmark: float) -> float:
    """Return the percentage shortfall relative to benchmark.

    Positive values mean the target is below the benchmark. A negative value
    means the target exceeds the benchmark.
    """
    if benchmark <= 0:
        raise DataValidationError("Benchmark must be strictly positive")
    return 100.0 * (1.0 - value / benchmark)


def compute_pt_gaps(panel: pd.DataFrame, *, country: str, benchmark: str) -> pd.DataFrame:
    """Compute annual target-country wage and productivity gaps."""
    validate_level_panel(panel)
    target = panel.loc[panel["geo"] == country].copy()
    bench = panel.loc[panel["geo"] == benchmark].copy()
    merged = target.merge(bench, on="year", suffixes=("_pt", "_benchmark"), how="inner")
    if merged.empty:
        raise DataValidationError("No overlapping target and benchmark years")

    rows: list[dict[str, float | int]] = []
    for record in merged.itertuples(index=False):
        wage_pt = float(record.wage_pt)
        wage_b = float(record.wage_benchmark)
        prod_pt = float(record.productivity_pt)
        prod_b = float(record.productivity_benchmark)
        wage_gap = log_gap(wage_pt, wage_b)
        productivity_gap = log_gap(prod_pt, prod_b)
        rows.append(
            {
                "year": int(record.year),
                "wage_pt": wage_pt,
                "wage_benchmark": wage_b,
                "productivity_pt": prod_pt,
                "productivity_benchmark": prod_b,
                "wage_log_gap": wage_gap,
                "productivity_log_gap": productivity_gap,
                "excess_wage_log_gap": wage_gap - productivity_gap,
                "wage_shortfall_pct": shortfall_pct(wage_pt, wage_b),
                "productivity_shortfall_pct": shortfall_pct(prod_pt, prod_b),
            }
        )
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
