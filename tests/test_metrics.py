import math

import pandas as pd
import pytest

from pt_wage_gap.metrics import (
    DataValidationError,
    compute_pt_gaps,
    log_gap,
    validate_eu_index_panel,
)


def test_excess_gap_is_negative_when_wage_shortfall_is_larger() -> None:
    panel = pd.DataFrame(
        {
            "geo": ["PT", "EU27_2020"],
            "year": [2024, 2024],
            "wage": [70.0, 100.0],
            "productivity": [85.0, 100.0],
        }
    )
    result = compute_pt_gaps(panel, country="PT", benchmark="EU27_2020")
    assert result.loc[0, "wage_shortfall_pct"] == pytest.approx(30.0)
    assert result.loc[0, "productivity_shortfall_pct"] == pytest.approx(15.0)
    assert result.loc[0, "excess_wage_log_gap"] < 0.0


def test_eu_index_validation_accepts_eu27_100_invariant() -> None:
    panel = pd.DataFrame(
        {
            "geo": ["PT", "EU27_2020", "PT", "EU27_2020"],
            "year": [2023, 2023, 2024, 2024],
            "wage": [78.0, 100.0, 80.0, 100.0],
            "productivity": [82.0, 100.0, 84.0, 100.0],
        }
    )
    validate_eu_index_panel(panel, benchmark="EU27_2020")


def test_eu_index_validation_rejects_wrong_unit_scale() -> None:
    panel = pd.DataFrame(
        {
            "geo": ["PT", "EU27_2020"],
            "year": [2024, 2024],
            "wage": [31_000.0, 42_000.0],
            "productivity": [74_000.0, 90_000.0],
        }
    )
    with pytest.raises(DataValidationError, match="EU27=100"):
        validate_eu_index_panel(panel, benchmark="EU27_2020")


def test_log_gap_rejects_non_positive_input() -> None:
    with pytest.raises(DataValidationError):
        log_gap(0.0, 1.0)


def test_log_gap_matches_ratio_definition() -> None:
    assert log_gap(80.0, 100.0) == pytest.approx(math.log(0.8))
