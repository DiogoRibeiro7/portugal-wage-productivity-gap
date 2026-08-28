"""Cross-country conditional wage benchmark and bootstrap inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from numpy.typing import NDArray
from statsmodels.regression.linear_model import RegressionResultsWrapper

from pt_wage_gap.metrics import DataValidationError, validate_level_panel


@dataclass(frozen=True)
class WageProductivityModel:
    """Fitted comparator-country log-level model and its design columns."""

    result: RegressionResultsWrapper
    design_columns: tuple[str, ...]
    comparator_countries: tuple[str, ...]


@dataclass(frozen=True)
class BootstrapSummary:
    """Bootstrap distribution summary for one Portuguese residual estimand."""

    point_estimate: float
    lower: float
    upper: float
    successful_replications: int
    requested_replications: int

    @property
    def success_rate(self) -> float:
        """Fraction of requested replications that completed successfully."""
        return self.successful_replications / self.requested_replications


def _design_matrix(
    frame: pd.DataFrame, *, year_levels: Iterable[int] | None = None
) -> pd.DataFrame:
    """Build the registered log-productivity + year-FE design matrix."""
    if (frame["productivity"] <= 0).any():
        raise DataValidationError("productivity must be positive before log transformation")

    base = pd.DataFrame(
        {"log_productivity": np.log(frame["productivity"].astype(float))},
        index=frame.index,
    )
    year = frame["year"].astype(int)
    dummies = pd.get_dummies(year, prefix="year", dtype=float)

    if year_levels is not None:
        expected = [f"year_{int(level)}" for level in sorted(set(year_levels))]
        dummies = dummies.reindex(columns=expected, fill_value=0.0)

    # Drop the earliest year as the reference category.
    if not dummies.empty:
        dummies = dummies.drop(columns=[sorted(dummies.columns)[0]])
    design = pd.concat([base, dummies], axis=1)
    return sm.add_constant(design, has_constant="add")


def fit_comparator_model(
    panel: pd.DataFrame,
    *,
    country: str,
    comparator_countries: Iterable[str],
    cluster_robust: bool = True,
) -> WageProductivityModel:
    """Fit the primary comparator-country log-level wage model.

    Portugal/target country is never used to estimate the relationship.
    """
    validate_level_panel(panel)
    comparators = tuple(dict.fromkeys(comparator_countries))
    train = panel.loc[panel["geo"].isin(comparators) & (panel["geo"] != country)].copy()
    if train.empty:
        raise DataValidationError("Comparator model has no training observations")
    if train["geo"].nunique() < 3:
        raise DataValidationError("Comparator model requires at least three countries")

    y = np.log(train["wage"].astype(float))
    x = _design_matrix(train)
    if np.linalg.matrix_rank(x.to_numpy(dtype=float)) < x.shape[1]:
        raise DataValidationError("Comparator model design matrix is rank deficient")

    base_result = sm.OLS(y, x).fit()
    if cluster_robust:
        result = base_result.get_robustcov_results(cov_type="cluster", groups=train["geo"])
        # statsmodels returns a wrapper with the same prediction interface.
        result = RegressionResultsWrapper(result)
    else:
        result = base_result

    return WageProductivityModel(
        result=result,
        design_columns=tuple(x.columns),
        comparator_countries=tuple(sorted(train["geo"].unique())),
    )


def predict_target_residuals(
    model: WageProductivityModel,
    panel: pd.DataFrame,
    *,
    country: str,
) -> pd.DataFrame:
    """Predict target-country compensation and return annual log residuals."""
    target = panel.loc[panel["geo"] == country].copy().sort_values("year")
    if target.empty:
        raise DataValidationError(f"No observations for target country {country}")

    train_years = [
        int(column.removeprefix("year_"))
        for column in model.design_columns
        if column.startswith("year_")
    ]
    # Include the omitted reference year from the panel's comparator support.
    comparator_years = sorted(
        panel.loc[panel["geo"].isin(model.comparator_countries), "year"].astype(int).unique()
    )
    year_levels = comparator_years if comparator_years else train_years
    x = _design_matrix(target, year_levels=year_levels)
    x = x.reindex(columns=model.design_columns, fill_value=0.0)

    predicted = np.asarray(model.result.predict(x), dtype=float)
    observed = np.log(target["wage"].to_numpy(dtype=float))
    residual = observed - predicted
    return pd.DataFrame(
        {
            "year": target["year"].to_numpy(dtype=int),
            "observed_log_wage": observed,
            "predicted_log_wage": predicted,
            "log_residual": residual,
            "multiplicative_residual_pct": 100.0 * np.expm1(residual),
        }
    )


def fit_and_predict(
    panel: pd.DataFrame,
    *,
    country: str,
    comparator_countries: Iterable[str],
    cluster_robust: bool = True,
) -> tuple[WageProductivityModel, pd.DataFrame]:
    """Convenience wrapper for the registered primary model and predictions."""
    model = fit_comparator_model(
        panel,
        country=country,
        comparator_countries=comparator_countries,
        cluster_robust=cluster_robust,
    )
    residuals = predict_target_residuals(model, panel, country=country)
    return model, residuals


def cluster_bootstrap_target_residual(
    panel: pd.DataFrame,
    *,
    country: str,
    comparator_countries: Iterable[str],
    target_year: int,
    replications: int,
    seed: int,
) -> tuple[BootstrapSummary, NDArray[np.float64]]:
    """Bootstrap the target-country residual by resampling country histories.

    Each replication samples comparator countries with replacement and includes
    every available year for each sampled country. The target country is never
    resampled or used to estimate the wage-productivity relationship.
    """
    if replications < 1:
        raise ValueError("replications must be positive")
    comparators = tuple(sorted(set(comparator_countries)))
    if len(comparators) < 3:
        raise DataValidationError("Bootstrap requires at least three comparator countries")

    _, point_residuals = fit_and_predict(
        panel,
        country=country,
        comparator_countries=comparators,
        cluster_robust=False,
    )
    point_row = point_residuals.loc[point_residuals["year"] == target_year]
    if len(point_row) != 1:
        raise DataValidationError(f"Target year {target_year} is unavailable or duplicated")
    point_estimate = float(point_row.iloc[0]["log_residual"])

    rng = np.random.default_rng(seed)
    draws: list[float] = []
    target_rows = panel.loc[panel["geo"] == country].copy()

    for _ in range(replications):
        sampled = rng.choice(
            np.asarray(comparators, dtype=object),
            size=len(comparators),
            replace=True,
        )
        pieces: list[pd.DataFrame] = [target_rows]
        sampled_labels: list[str] = []
        # Assign a unique bootstrap cluster label to each sampled history so
        # duplicate countries act as independent resampled clusters.
        for draw_index, geo in enumerate(sampled):
            rows = panel.loc[panel["geo"] == str(geo)].copy()
            bootstrap_geo = f"BOOT_{draw_index:03d}_{geo}"
            rows.loc[:, "geo"] = bootstrap_geo
            pieces.append(rows)
            sampled_labels.append(bootstrap_geo)
        bootstrap_panel = pd.concat(pieces, ignore_index=True)

        try:
            _, residuals = fit_and_predict(
                bootstrap_panel,
                country=country,
                comparator_countries=sampled_labels,
                cluster_robust=False,
            )
            row = residuals.loc[residuals["year"] == target_year]
            if len(row) == 1:
                value = float(row.iloc[0]["log_residual"])
                if np.isfinite(value):
                    draws.append(value)
        except (DataValidationError, ValueError, np.linalg.LinAlgError):
            continue

    if not draws:
        raise DataValidationError("All bootstrap replications failed")
    distribution = np.asarray(draws, dtype=float)
    lower, upper = np.quantile(distribution, [0.025, 0.975])
    summary = BootstrapSummary(
        point_estimate=point_estimate,
        lower=float(lower),
        upper=float(upper),
        successful_replications=len(draws),
        requested_replications=replications,
    )
    return summary, distribution
