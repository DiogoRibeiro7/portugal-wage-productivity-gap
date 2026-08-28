import numpy as np
import pandas as pd
import pytest

from pt_wage_gap.econometrics import cluster_bootstrap_target_residual, fit_and_predict


def _synthetic_panel() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    countries = ["A", "B", "C", "D", "E", "F"]
    years = list(range(2010, 2020))
    rows: list[dict[str, float | int | str]] = []
    for c_index, country in enumerate(countries):
        for year in years:
            productivity = 50.0 + 4.0 * c_index + 1.2 * (year - 2010)
            log_wage = 1.0 + 0.8 * np.log(productivity) + 0.01 * (year - 2010)
            log_wage += rng.normal(0.0, 0.01)
            rows.append(
                {
                    "geo": country,
                    "year": year,
                    "wage": float(np.exp(log_wage)),
                    "productivity": productivity,
                }
            )
    # Target country follows the same relation but has a persistent ~20% penalty.
    for year in years:
        productivity = 60.0 + 1.2 * (year - 2010)
        log_wage = 1.0 + 0.8 * np.log(productivity) + 0.01 * (year - 2010) + np.log(0.8)
        rows.append(
            {
                "geo": "PT",
                "year": year,
                "wage": float(np.exp(log_wage)),
                "productivity": productivity,
            }
        )
    return pd.DataFrame(rows)


def test_model_excludes_target_and_recovers_negative_residual() -> None:
    panel = _synthetic_panel()
    model, residuals = fit_and_predict(
        panel,
        country="PT",
        comparator_countries=["A", "B", "C", "D", "E", "F"],
        cluster_robust=False,
    )
    assert "PT" not in model.comparator_countries
    latest = residuals.loc[residuals["year"] == 2019, "log_residual"].item()
    assert latest == pytest.approx(np.log(0.8), abs=0.04)


def test_cluster_bootstrap_is_deterministic() -> None:
    panel = _synthetic_panel()
    kwargs = dict(
        panel=panel,
        country="PT",
        comparator_countries=["A", "B", "C", "D", "E", "F"],
        target_year=2019,
        replications=50,
        seed=7,
    )
    first, first_draws = cluster_bootstrap_target_residual(**kwargs)
    second, second_draws = cluster_bootstrap_target_residual(**kwargs)
    assert first.point_estimate == pytest.approx(second.point_estimate)
    assert np.array_equal(first_draws, second_draws)
    assert first.successful_replications >= 45
