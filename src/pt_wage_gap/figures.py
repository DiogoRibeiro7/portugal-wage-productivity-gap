"""Publication-oriented figures for the primary analysis."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from dataexcept import DataLoadingError, FileWriteError
from matplotlib.figure import Figure


def _read_frame(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise DataLoadingError(str(path), exc) from exc


def _save_figure(figure: Figure, output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output_path, dpi=200)
    except OSError as exc:
        raise FileWriteError(str(output_path), exc) from exc
    finally:
        plt.close(figure)


def plot_gap_history(gap_path: Path, output_path: Path) -> None:
    """Plot Portuguese wage and productivity shortfalls against the benchmark."""
    frame = _read_frame(gap_path)
    required = {"year", "wage_shortfall_pct", "productivity_shortfall_pct"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Gap file missing columns: {sorted(missing)}")

    figure, axis = plt.subplots(figsize=(9, 5.5))
    axis.plot(frame["year"], frame["wage_shortfall_pct"], marker="o", label="Compensation gap")
    axis.plot(
        frame["year"],
        frame["productivity_shortfall_pct"],
        marker="o",
        label="Productivity gap",
    )
    axis.axhline(0.0, linewidth=0.8)
    axis.set_xlabel("Year")
    axis.set_ylabel("Shortfall relative to EU-27 benchmark (%)")
    axis.set_title("Portugal: compensation and productivity gaps")
    axis.legend()
    figure.tight_layout()
    _save_figure(figure, output_path)


def plot_conditional_residuals(residual_path: Path, output_path: Path) -> None:
    """Plot Portuguese conditional compensation residuals through time."""
    frame = _read_frame(residual_path)
    required = {"year", "multiplicative_residual_pct"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Residual file missing columns: {sorted(missing)}")

    figure, axis = plt.subplots(figsize=(9, 5.5))
    axis.plot(frame["year"], frame["multiplicative_residual_pct"], marker="o")
    axis.axhline(0.0, linewidth=0.8)
    axis.set_xlabel("Year")
    axis.set_ylabel("Observed minus predicted compensation (%)")
    axis.set_title("Portugal: conditional compensation residual")
    figure.tight_layout()
    _save_figure(figure, output_path)
