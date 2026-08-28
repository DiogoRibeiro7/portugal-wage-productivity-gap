"""Registered Eurostat source contract for the primary level analysis.

The constants in this module are deliberately explicit.  They protect the
analysis from silently querying a plausible but scientifically different
Eurostat series when provider code lists evolve or a configuration is edited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


PRIMARY_DATASET: Final = "nama_10_lp_ulc"
ANNUAL_FREQUENCY: Final = "A"
EU27_PPS_CURRENT_PRICE_INDEX: Final = "PC_EU27_2020_MPPS_CP"
COMPENSATION_PER_EMPLOYEE: Final = "D1_SAL_PER"
NOMINAL_PRODUCTIVITY_PER_PERSON: Final = "NLPR_EMP"
EU27_BENCHMARK: Final = "EU27_2020"
EU27_INDEX_VALUE: Final = 100.0


class SourceContractError(ValueError):
    """Raised when the configured primary source differs from the registered design."""


@dataclass(frozen=True)
class PrimarySourceContract:
    """Exact Eurostat codes required by the primary level estimand."""

    dataset: str = PRIMARY_DATASET
    frequency: str = ANNUAL_FREQUENCY
    unit: str = EU27_PPS_CURRENT_PRICE_INDEX
    wage_indicator: str = COMPENSATION_PER_EMPLOYEE
    productivity_indicator: str = NOMINAL_PRODUCTIVITY_PER_PERSON
    benchmark: str = EU27_BENCHMARK

    def validate(
        self,
        *,
        dataset: str,
        frequency: str,
        unit: str,
        wage_indicator: str,
        productivity_indicator: str,
        benchmark: str,
    ) -> None:
        """Validate configured values against the registered source contract."""
        observed = {
            "dataset": dataset,
            "frequency": frequency,
            "unit": unit,
            "wage_indicator": wage_indicator,
            "productivity_indicator": productivity_indicator,
            "benchmark": benchmark,
        }
        expected = {
            "dataset": self.dataset,
            "frequency": self.frequency,
            "unit": self.unit,
            "wage_indicator": self.wage_indicator,
            "productivity_indicator": self.productivity_indicator,
            "benchmark": self.benchmark,
        }
        mismatches = {
            key: (expected[key], observed[key])
            for key in expected
            if observed[key] != expected[key]
        }
        if mismatches:
            details = "; ".join(
                f"{key}: expected {want!r}, got {got!r}"
                for key, (want, got) in mismatches.items()
            )
            raise SourceContractError(f"Primary Eurostat source contract mismatch: {details}")
