import json
from decimal import Decimal

from scripts.worldbank_wdi import COLUMNS, FIRST_YEAR, INDICATORS, LAST_YEAR, build_rows

COUNTRIES = [
    {
        "id": "IND",
        "name": "India",
        "region": {"value": "South Asia"},
        "incomeLevel": {"value": "Lower middle income"},
    },
    {"id": "WLD", "name": "World", "region": {"value": "Aggregates"}, "incomeLevel": {"value": "Aggregates"}},
]


def page(records):
    return json.dumps([{"page": 1, "pages": 1, "per_page": 20000, "total": len(records)}, records]).encode()


def indicator_pages(gdp_per_capita):
    pages = {code: page([]) for code, _ in INDICATORS}
    pages["NY.GDP.PCAP.CD"] = page(
        [
            {"indicator": {"id": "NY.GDP.PCAP.CD"}, "countryiso3code": iso, "date": year, "value": value}
            for iso, year, value in gdp_per_capita
        ]
    )
    return pages


def test_rows_exclude_aggregates_keep_nulls_and_round_half_up():
    rows = build_rows(
        page(COUNTRIES),
        indicator_pages([("IND", "2023", 2434.44826340989), ("IND", "2024", None), ("WLD", "2023", 13000.0)]),
    )
    gdp = COLUMNS.index("GDP_PER_CAPITA_USD")
    assert {row[0] for row in rows} == {"IND"}
    assert len(rows) == LAST_YEAR - FIRST_YEAR + 1
    by_year = {row[4]: row for row in rows}
    assert by_year[2023][1:4] == ("India", "South Asia", "Lower middle income")
    assert by_year[2023][gdp] == Decimal("2434.448263")
    assert by_year[2024][gdp] is None
    assert by_year[2023][COLUMNS.index("POPULATION")] is None


def test_paginated_response_is_refused():
    import pytest

    paged = json.dumps([{"page": 1, "pages": 2}, []]).encode()
    with pytest.raises(ValueError, match="paginated"):
        build_rows(paged, indicator_pages([]))
