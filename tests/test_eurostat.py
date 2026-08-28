import pandas as pd
import pytest
import requests

from pt_wage_gap.eurostat import EurostatError, EurostatQuery, fetch_jsonstat, jsonstat_to_frame
from pt_wage_gap.source_contract import EU27_PPS_CURRENT_PRICE_INDEX


def test_jsonstat_dense_cube_is_parsed_in_dimension_order() -> None:
    payload = {
        "id": ["geo", "time"],
        "size": [2, 2],
        "dimension": {
            "geo": {
                "category": {
                    "index": {"PT": 0, "DE": 1},
                    "label": {"PT": "Portugal", "DE": "Germany"},
                }
            },
            "time": {
                "category": {
                    "index": {"2023": 0, "2024": 1},
                    "label": {"2023": "2023", "2024": "2024"},
                }
            },
        },
        "value": [1.0, 2.0, 3.0, 4.0],
        "status": {"1": "p"},
    }
    frame = jsonstat_to_frame(payload)
    assert isinstance(frame, pd.DataFrame)
    assert frame[["geo", "time", "value"]].to_dict("records") == [
        {"geo": "PT", "time": "2023", "value": 1.0},
        {"geo": "PT", "time": "2024", "value": 2.0},
        {"geo": "DE", "time": "2023", "value": 3.0},
        {"geo": "DE", "time": "2024", "value": 4.0},
    ]
    assert frame.loc[1, "status"] == "p"


def test_query_preserves_frequency_geo_filters_and_time_window() -> None:
    query = EurostatQuery(
        dataset="nama_10_lp_ulc",
        filters={"freq": "A", "unit": EU27_PPS_CURRENT_PRICE_INDEX, "geo": ["PT", "DE"]},
        since_year=2000,
        until_year=2024,
    )
    params = query.params()
    assert ("freq", "A") in params
    assert ("unit", EU27_PPS_CURRENT_PRICE_INDEX) in params
    assert ("geo", "PT") in params
    assert ("geo", "DE") in params
    assert ("sinceTimePeriod", "2000") in params
    assert ("untilTimePeriod", "2024") in params


class _FailingSession:
    def get(self, *args: object, **kwargs: object) -> object:
        raise requests.ConnectionError("network unavailable")


def test_fetch_wraps_transport_failure_as_eurostat_error() -> None:
    query = EurostatQuery(dataset="nama_10_lp_ulc", filters={"freq": "A"})
    with pytest.raises(EurostatError, match="Eurostat request failed"):
        fetch_jsonstat(query, session=_FailingSession())  # type: ignore[arg-type]
