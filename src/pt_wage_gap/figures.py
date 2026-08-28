"""Publication-oriented figures for the primary analysis."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_gap_history(gap_path: Path, output_path: Path) -> None:
    """Plot Portuguese wage and productivity shortfalls against the benchmark."""
    frame = pd.read_csv(gap_path)
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=200)
    plt.close(figure)


def plot_conditional_residuals(residual_path: Path, output_path: Path) -> None:
    """Plot Portuguese conditional compensation residuals through time."""
    frame = pd.read_csv(residual_path)
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=200)
    plt.close(figure)
