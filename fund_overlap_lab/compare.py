from __future__ import annotations

import pandas as pd

from .buckets import ASSET_BUCKETS
from .models import FundHoldings


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
