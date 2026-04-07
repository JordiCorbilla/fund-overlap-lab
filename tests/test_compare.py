import pandas as pd

from fund_overlap_lab.compare import compare_by_bucket, compare_funds
from fund_overlap_lab.models import FundHoldings


def make_fund(ticker: str, rows: list[tuple[str, float, str]]) -> FundHoldings:
    df = pd.DataFrame(rows, columns=["fund_name", "weight_pct", "fund_name_norm"])
    return FundHoldings(
        ticker=ticker,
        name=ticker,
        source_url="http://example.com",
        as_of="01 Jan 2026",
        holdings=df,
    )


def test_compare_funds_overlap():
    a = make_fund(
        "A",
        [
            ("US Equity Index Fund", 60.0, "us equity index fund"),
            ("UK Equity Index Fund", 40.0, "uk equity index fund"),
        ],
    )
    b = make_fund(
        "B",
        [
            ("US Equity Index Fund", 30.0, "us equity index fund"),
            ("Global Bond Index Fund Hedged", 70.0, "global bond index fund hedged"),
        ],
    )

    result = compare_funds(a, b)
    assert result["summary"]["wrapper_overlap_pct"] == 30.0
    assert len(result["common_holdings"]) == 1
    assert result["common_holdings"].iloc[0]["overlap_pct"] == 30.0


def test_compare_by_bucket():
    a = make_fund(
        "A",
        [("US Equity Index Fund", 100.0, "us equity index fund")],
    )
    b = make_fund(
        "B",
        [("S&P 500 UCITS ETF", 50.0, "s p 500 ucits etf")],
    )

    buckets = compare_by_bucket(a, b)
    us_row = buckets[buckets["bucket"] == "US Equity"].iloc[0]
    assert us_row["overlap_pct"] == 50.0
