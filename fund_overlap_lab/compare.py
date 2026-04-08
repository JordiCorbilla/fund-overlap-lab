from __future__ import annotations

import pandas as pd

from .buckets import ASSET_BUCKETS
from .models import FundHoldings, PortfolioPosition


def compare_funds(a: FundHoldings, b: FundHoldings) -> dict:
    left = a.holdings.rename(columns={"fund_name": "fund_name_a", "weight_pct": "weight_a"})
    right = b.holdings.rename(columns={"fund_name": "fund_name_b", "weight_pct": "weight_b"})

    merged = left.merge(right, on="fund_name_norm", how="outer")
    merged["weight_a"] = merged["weight_a"].fillna(0.0)
    merged["weight_b"] = merged["weight_b"].fillna(0.0)
    merged["fund_name"] = merged["fund_name_a"].combine_first(merged["fund_name_b"])
    merged["overlap_pct"] = merged[["weight_a", "weight_b"]].min(axis=1)
    merged["difference_pct"] = (merged["weight_a"] - merged["weight_b"]).abs()

    common = merged.loc[merged["overlap_pct"] > 0].copy().sort_values("overlap_pct", ascending=False)
    only_a = merged.loc[(merged["weight_a"] > 0) & (merged["weight_b"] == 0)].copy().sort_values("weight_a", ascending=False)
    only_b = merged.loc[(merged["weight_b"] > 0) & (merged["weight_a"] == 0)].copy().sort_values("weight_b", ascending=False)

    summary = {
        "fund_a": a.ticker,
        "fund_b": b.ticker,
        "fund_a_name": a.name,
        "fund_b_name": b.name,
        "as_of_a": a.as_of,
        "as_of_b": b.as_of,
        "risk_a": a.risk_level,
        "risk_b": b.risk_level,
        "ocf_a": a.ocf,
        "ocf_b": b.ocf,
        "wrapper_overlap_pct": round(float(common["overlap_pct"].sum()), 4),
        "distinct_count_a": int((merged["weight_a"] > 0).sum()),
        "distinct_count_b": int((merged["weight_b"] > 0).sum()),
        "shared_count": int((merged["overlap_pct"] > 0).sum()),
    }

    return {
        "summary": summary,
        "common_holdings": common[["fund_name", "weight_a", "weight_b", "overlap_pct", "difference_pct"]].reset_index(drop=True),
        "only_in_a": only_a[["fund_name", "weight_a"]].reset_index(drop=True),
        "only_in_b": only_b[["fund_name", "weight_b"]].reset_index(drop=True),
        "full_matrix": merged[["fund_name", "fund_name_norm", "weight_a", "weight_b", "overlap_pct", "difference_pct"]]
            .sort_values(["overlap_pct", "difference_pct"], ascending=[False, True])
            .reset_index(drop=True),
    }


def compare_by_bucket(a: FundHoldings, b: FundHoldings) -> pd.DataFrame:
    a_df = a.holdings.copy()
    b_df = b.holdings.copy()

    a_df["bucket"] = a_df["fund_name_norm"].map(ASSET_BUCKETS).fillna("Other")
    b_df["bucket"] = b_df["fund_name_norm"].map(ASSET_BUCKETS).fillna("Other")

    a_bucket = a_df.groupby("bucket", as_index=False)["weight_pct"].sum().rename(columns={"weight_pct": "weight_a"})
    b_bucket = b_df.groupby("bucket", as_index=False)["weight_pct"].sum().rename(columns={"weight_pct": "weight_b"})

    merged = a_bucket.merge(b_bucket, on="bucket", how="outer").fillna(0.0)
    merged["overlap_pct"] = merged[["weight_a", "weight_b"]].min(axis=1)
    merged["difference_pct"] = (merged["weight_a"] - merged["weight_b"]).abs()
    return merged.sort_values("overlap_pct", ascending=False).reset_index(drop=True)


def portfolio_pairwise_overlap_matrix(positions: list[PortfolioPosition]) -> pd.DataFrame:
    tickers = [p.fund.ticker for p in positions]
    matrix = pd.DataFrame(0.0, index=tickers, columns=tickers)

    for i, left in enumerate(positions):
        for j, right in enumerate(positions):
            if i == j:
                matrix.iat[i, j] = 100.0
            elif j > i:
                overlap = float(compare_funds(left.fund, right.fund)["summary"]["wrapper_overlap_pct"])
                matrix.iat[i, j] = overlap
                matrix.iat[j, i] = overlap

    return matrix


def portfolio_weighted_underlying_exposures(positions: list[PortfolioPosition]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for pos in positions:
        df = pos.fund.holdings[["fund_name", "fund_name_norm", "weight_pct"]].copy()
        df["ticker"] = pos.fund.ticker
        df["portfolio_weight_pct"] = float(pos.portfolio_weight)
        df["portfolio_contribution_pct"] = df["weight_pct"] * float(pos.portfolio_weight) / 100.0
        rows.append(df)

    if not rows:
        return pd.DataFrame(columns=["fund_name", "fund_name_norm", "portfolio_contribution_pct", "num_funds_holding"])

    combined = pd.concat(rows, ignore_index=True)
    aggregated = (
        combined.groupby("fund_name_norm", as_index=False)
        .agg(
            fund_name=("fund_name", "first"),
            portfolio_contribution_pct=("portfolio_contribution_pct", "sum"),
            num_funds_holding=("ticker", "nunique"),
        )
        .sort_values("portfolio_contribution_pct", ascending=False)
        .reset_index(drop=True)
    )
    return aggregated


def portfolio_weighted_bucket_exposures(positions: list[PortfolioPosition]) -> pd.DataFrame:
    exposures = portfolio_weighted_underlying_exposures(positions).copy()
    if exposures.empty:
        return pd.DataFrame(columns=["bucket", "portfolio_contribution_pct", "num_holdings"])

    exposures["bucket"] = exposures["fund_name_norm"].map(ASSET_BUCKETS).fillna("Other")
    buckets = (
        exposures.groupby("bucket", as_index=False)
        .agg(
            portfolio_contribution_pct=("portfolio_contribution_pct", "sum"),
            num_holdings=("fund_name_norm", "count"),
        )
        .sort_values("portfolio_contribution_pct", ascending=False)
        .reset_index(drop=True)
    )
    return buckets


def analyze_portfolio(positions: list[PortfolioPosition]) -> dict:
    matrix = portfolio_pairwise_overlap_matrix(positions)
    underlying = portfolio_weighted_underlying_exposures(positions)
    buckets = portfolio_weighted_bucket_exposures(positions)

    total_weight = round(float(sum(p.portfolio_weight for p in positions)), 4)
    weighted_risk = None
    weighted_ocf = None

    risk_rows = [(p.fund.risk_level, p.portfolio_weight) for p in positions if p.fund.risk_level is not None]
    if risk_rows:
        weighted_risk = sum(r * w for r, w in risk_rows) / sum(w for _, w in risk_rows)

    ocf_rows: list[tuple[float, float]] = []
    for p in positions:
        if p.fund.ocf:
            try:
                ocf_rows.append((float(str(p.fund.ocf).replace("%", "")), p.portfolio_weight))
            except ValueError:
                pass
    if ocf_rows:
        weighted_ocf = sum(v * w for v, w in ocf_rows) / sum(w for _, w in ocf_rows)

    return {
        "summary": {
            "fund_count": len(positions),
            "total_input_weight_pct": total_weight,
            "weighted_risk": round(weighted_risk, 3) if weighted_risk is not None else None,
            "weighted_ocf_pct": round(weighted_ocf, 4) if weighted_ocf is not None else None,
            "top_underlying_pct": round(float(underlying["portfolio_contribution_pct"].iloc[0]), 4) if not underlying.empty else 0.0,
        },
        "pairwise_overlap_matrix": matrix,
        "underlying_exposures": underlying,
        "bucket_exposures": buckets,
    }
