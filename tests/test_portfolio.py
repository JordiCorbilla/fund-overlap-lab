import pandas as pd

from fund_overlap_lab.compare import (
    analyze_portfolio,
    portfolio_pairwise_overlap_matrix,
    portfolio_weighted_bucket_exposures,
    portfolio_weighted_underlying_exposures,
)
from fund_overlap_lab.models import FundHoldings, PortfolioPosition


def make_fund(ticker: str, rows: list[tuple[str, float, str]]) -> FundHoldings:
    df = pd.DataFrame(rows, columns=["fund_name", "weight_pct", "fund_name_norm"])
    return FundHoldings(
        ticker=ticker,
        name=ticker,
        source_url="http://example.com",
        as_of="01 Jan 2026",
        holdings=df,
    )


def test_portfolio_weighted_underlying_exposures():
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
            ("US Equity Index Fund", 20.0, "us equity index fund"),
            ("Global Bond Index Fund Hedged", 80.0, "global bond index fund hedged"),
        ],
    )

    positions = [
        PortfolioPosition(fund=a, portfolio_weight=50.0),
        PortfolioPosition(fund=b, portfolio_weight=50.0),
    ]

    out = portfolio_weighted_underlying_exposures(positions)
    us_row = out[out["fund_name_norm"] == "us equity index fund"].iloc[0]
    uk_row = out[out["fund_name_norm"] == "uk equity index fund"].iloc[0]
    bond_row = out[out["fund_name_norm"] == "global bond index fund hedged"].iloc[0]

    assert us_row["portfolio_contribution_pct"] == 40.0
    assert uk_row["portfolio_contribution_pct"] == 20.0
    assert bond_row["portfolio_contribution_pct"] == 40.0


def test_portfolio_pairwise_overlap_matrix():
    a = make_fund("A", [("US Equity Index Fund", 100.0, "us equity index fund")])
    b = make_fund("B", [("US Equity Index Fund", 50.0, "us equity index fund")])
    c = make_fund("C", [("Global Bond Index Fund Hedged", 100.0, "global bond index fund hedged")])

    positions = [
        PortfolioPosition(fund=a, portfolio_weight=40.0),
        PortfolioPosition(fund=b, portfolio_weight=30.0),
        PortfolioPosition(fund=c, portfolio_weight=30.0),
    ]

    matrix = portfolio_pairwise_overlap_matrix(positions)

    assert matrix.loc["A", "A"] == 100.0
    assert matrix.loc["B", "B"] == 100.0
    assert matrix.loc["C", "C"] == 100.0
    assert matrix.loc["A", "B"] == 50.0
    assert matrix.loc["B", "A"] == 50.0
    assert matrix.loc["A", "C"] == 0.0


def test_portfolio_weighted_bucket_exposures():
    a = make_fund("A", [("US Equity Index Fund", 100.0, "us equity index fund")])
    b = make_fund("B", [("S&P 500 UCITS ETF", 100.0, "s p 500 ucits etf")])
    positions = [
        PortfolioPosition(fund=a, portfolio_weight=60.0),
        PortfolioPosition(fund=b, portfolio_weight=40.0),
    ]

    buckets = portfolio_weighted_bucket_exposures(positions)
    us_row = buckets[buckets["bucket"] == "US Equity"].iloc[0]
    assert us_row["portfolio_contribution_pct"] == 100.0


def test_analyze_portfolio_summary():
    a = make_fund("A", [("US Equity Index Fund", 100.0, "us equity index fund")])
    b = make_fund("B", [("US Equity Index Fund", 50.0, "us equity index fund")])
    a.risk_level = 5
    b.risk_level = 3
    a.ocf = "0.20%"
    b.ocf = "0.10%"

    positions = [
        PortfolioPosition(fund=a, portfolio_weight=70.0),
        PortfolioPosition(fund=b, portfolio_weight=30.0),
    ]

    result = analyze_portfolio(positions)
    summary = result["summary"]

    assert summary["fund_count"] == 2
    assert summary["total_input_weight_pct"] == 100.0
    assert summary["weighted_risk"] == 4.4
    assert summary["weighted_ocf_pct"] == 0.17
