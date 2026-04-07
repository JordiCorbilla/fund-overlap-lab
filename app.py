from __future__ import annotations

import html

import streamlit as st

from fund_overlap_lab.compare import compare_by_bucket, compare_funds
from fund_overlap_lab.providers import VanguardUKProvider


st.set_page_config(page_title="Fund Overlap Lab", layout="wide")
st.title("Fund Overlap Lab")
st.caption("Wrapper fund overlap analysis for Vanguard UK funds")


def render_summary_html(summary: dict) -> str:
        overlap = float(summary.get("wrapper_overlap_pct", 0.0))
        fund_a = html.escape(str(summary.get("fund_a", "")))
        fund_b = html.escape(str(summary.get("fund_b", "")))
        fund_a_name = html.escape(str(summary.get("fund_a_name", "")))
        fund_b_name = html.escape(str(summary.get("fund_b_name", "")))
        as_of_a = html.escape(str(summary.get("as_of_a", "")))
        as_of_b = html.escape(str(summary.get("as_of_b", "")))
        distinct_a = int(summary.get("distinct_count_a", 0))
        distinct_b = int(summary.get("distinct_count_b", 0))
        shared = int(summary.get("shared_count", 0))

        return f"""
<style>
    .summary-card {{
        border: 1px solid #d6dbe1;
        border-radius: 14px;
        background: linear-gradient(160deg, #f8fafc 0%, #eef5fb 100%);
        padding: 18px 20px;
        margin-bottom: 12px;
    }}
    .summary-title {{
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 10px;
        color: #153a59;
    }}
    .summary-pair {{
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        gap: 10px;
        align-items: center;
        margin-bottom: 14px;
    }}
    .summary-fund {{
        background: #ffffff;
        border: 1px solid #dce5ee;
        border-radius: 10px;
        padding: 10px 12px;
    }}
    .summary-ticker {{
        font-size: 0.86rem;
        font-weight: 700;
        color: #174f73;
        letter-spacing: 0.02em;
    }}
    .summary-name {{
        font-size: 0.95rem;
        color: #1f2d3d;
        margin-top: 3px;
    }}
    .summary-date {{
        margin-top: 5px;
        color: #4d5f72;
        font-size: 0.82rem;
    }}
    .summary-vs {{
        font-size: 0.78rem;
        font-weight: 700;
        color: #4b6178;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    .summary-overlap {{
        background: #153a59;
        color: #ffffff;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
        text-align: center;
    }}
    .summary-overlap-value {{
        font-size: 1.55rem;
        font-weight: 800;
        line-height: 1;
    }}
    .summary-overlap-label {{
        font-size: 0.8rem;
        opacity: 0.9;
        margin-top: 4px;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }}
    .summary-metrics {{
        display: grid;
        grid-template-columns: repeat(3, minmax(120px, 1fr));
        gap: 8px;
    }}
    .summary-metric {{
        background: #ffffff;
        border: 1px solid #dce5ee;
        border-radius: 10px;
        padding: 10px;
        text-align: center;
    }}
    .summary-metric-value {{
        font-size: 1.2rem;
        font-weight: 700;
        color: #12273a;
        line-height: 1;
    }}
    .summary-metric-label {{
        margin-top: 5px;
        font-size: 0.76rem;
        color: #4b6178;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
</style>

<div class="summary-card">
    <div class="summary-title">Comparison Summary</div>
    <div class="summary-pair">
        <div class="summary-fund">
            <div class="summary-ticker">{fund_a}</div>
            <div class="summary-name">{fund_a_name}</div>
            <div class="summary-date">As of: {as_of_a}</div>
        </div>
        <div class="summary-vs">vs</div>
        <div class="summary-fund">
            <div class="summary-ticker">{fund_b}</div>
            <div class="summary-name">{fund_b_name}</div>
            <div class="summary-date">As of: {as_of_b}</div>
        </div>
    </div>

    <div class="summary-overlap">
        <div class="summary-overlap-value">{overlap:.2f}%</div>
        <div class="summary-overlap-label">Wrapper Overlap</div>
    </div>

    <div class="summary-metrics">
        <div class="summary-metric">
            <div class="summary-metric-value">{distinct_a}</div>
            <div class="summary-metric-label">Distinct A</div>
        </div>
        <div class="summary-metric">
            <div class="summary-metric-value">{shared}</div>
            <div class="summary-metric-label">Shared</div>
        </div>
        <div class="summary-metric">
            <div class="summary-metric-value">{distinct_b}</div>
            <div class="summary-metric-label">Distinct B</div>
        </div>
    </div>
</div>
"""

provider = VanguardUKProvider()

col1, col2 = st.columns(2)
with col1:
    ticker_a = st.text_input("Fund A", value="VGL100A")
with col2:
    ticker_b = st.text_input("Fund B", value="VAR45GA")

if st.button("Compare", type="primary"):
    try:
        a = provider.get_holdings(ticker_a)
        b = provider.get_holdings(ticker_b)

        result = compare_funds(a, b)
        buckets = compare_by_bucket(a, b)

        st.subheader("Summary")
        st.markdown(render_summary_html(result["summary"]), unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"{a.ticker} holdings")
            st.dataframe(a.holdings, use_container_width=True)
        with c2:
            st.subheader(f"{b.ticker} holdings")
            st.dataframe(b.holdings, use_container_width=True)

        st.subheader("Common holdings")
        st.dataframe(result["common_holdings"], use_container_width=True)

        st.subheader("Bucket overlap")
        st.dataframe(buckets, use_container_width=True)

        st.subheader(f"Only in {a.ticker}")
        st.dataframe(result["only_in_a"], use_container_width=True)

        st.subheader(f"Only in {b.ticker}")
        st.dataframe(result["only_in_b"], use_container_width=True)

    except Exception as exc:
        st.error(f"Failed to compare funds: {exc}")
