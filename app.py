from __future__ import annotations

import html
import re
import textwrap

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from fund_overlap_lab.compare import analyze_portfolio, compare_by_bucket, compare_funds
from fund_overlap_lab.models import PortfolioPosition
from fund_overlap_lab.providers import VanguardUKProvider


st.set_page_config(page_title="Fund Overlap Lab", layout="wide")
st.title("Fund Overlap Lab")
st.caption("Wrapper fund overlap analysis for Vanguard UK funds")


@st.cache_data(ttl=3600)
def load_product_options() -> list[dict]:
    p = VanguardUKProvider()
    options = p.list_products()
    for item in options:
        ref = item["ticker"] or item["sedol"] or item["slug"]
        share_class = (item.get("share_class") or "").strip()
        if not share_class:
            slug = item.get("slug", "").lower()
            if "accumulation" in slug:
                share_class = "Accumulation"
            elif "income" in slug:
                share_class = "Income"

        suffix = f" - {share_class}" if share_class else ""
        item["label"] = f"{item['name']}{suffix} ({ref})"
        item["name_norm"] = re.sub(r"\s+", " ", item["name"]).strip().lower()
    return options


def parse_portfolio_lines(text: str, product_options: list[dict]) -> tuple[pd.DataFrame, list[str]]:
    if not text.strip():
        return pd.DataFrame(columns=["ticker", "weight_pct"]), []

    index_by_name: dict[str, list[dict]] = {}
    for item in product_options:
        index_by_name.setdefault(item["name_norm"], []).append(item)

    rows: list[dict] = []
    unresolved: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = re.match(r"^(.+?)\s+(-?\d+(?:\.\d+)?)\s*%?$", line)
        if not match:
            unresolved.append(line)
            continue

        name_part = re.sub(r"\s+", " ", match.group(1)).strip().lower()
        weight = float(match.group(2))
        if weight <= 0:
            unresolved.append(line)
            continue

        candidates = index_by_name.get(name_part, [])
        if not candidates:
            unresolved.append(line)
            continue

        selected = candidates[0]
        if len(candidates) > 1:
            if "accum" in line.lower():
                for c in candidates:
                    if (c.get("share_class") or "").lower().startswith("accum"):
                        selected = c
                        break
            elif "income" in line.lower():
                for c in candidates:
                    if (c.get("share_class") or "").lower().startswith("income"):
                        selected = c
                        break

        rows.append({"ticker": selected["code"], "weight_pct": weight})

    return pd.DataFrame(rows), unresolved


def render_summary_html(summary: dict) -> str:
    overlap = float(summary.get("wrapper_overlap_pct", 0.0))
    fund_a = html.escape(str(summary.get("fund_a", "")))
    fund_b = html.escape(str(summary.get("fund_b", "")))
    fund_a_name = html.escape(str(summary.get("fund_a_name", "")))
    fund_b_name = html.escape(str(summary.get("fund_b_name", "")))
    as_of_a = html.escape(str(summary.get("as_of_a", "")))
    as_of_b = html.escape(str(summary.get("as_of_b", "")))
    risk_a = summary.get("risk_a")
    risk_b = summary.get("risk_b")
    ocf_a = html.escape(str(summary.get("ocf_a", "") or "n/a"))
    ocf_b = html.escape(str(summary.get("ocf_b", "") or "n/a"))
    distinct_a = int(summary.get("distinct_count_a", 0))
    distinct_b = int(summary.get("distinct_count_b", 0))
    shared = int(summary.get("shared_count", 0))

    risk_a_text = f"Risk: {risk_a}/7" if risk_a is not None else "Risk: n/a"
    risk_b_text = f"Risk: {risk_b}/7" if risk_b is not None else "Risk: n/a"
    cost_a_text = f"Cost (OCF): {ocf_a}"
    cost_b_text = f"Cost (OCF): {ocf_b}"

    html_doc = textwrap.dedent(f"""
        <style>
            .summary-card {{
                border: 1px solid #d6dbe1;
                border-radius: 14px;
                background: linear-gradient(160deg, #f8fafc 0%, #eef5fb 100%);
                padding: 18px 20px;
                margin-bottom: 18px;
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
            .summary-risk {{
                margin-top: 3px;
                color: #274d66;
                font-size: 0.82rem;
                font-weight: 600;
            }}
            .summary-cost {{
                margin-top: 2px;
                color: #36596f;
                font-size: 0.8rem;
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
                    <div class="summary-risk">{risk_a_text}</div>
                    <div class="summary-cost">{cost_a_text}</div>
                </div>
                <div class="summary-vs">vs</div>
                <div class="summary-fund">
                    <div class="summary-ticker">{fund_b}</div>
                    <div class="summary-name">{fund_b_name}</div>
                    <div class="summary-date">As of: {as_of_b}</div>
                    <div class="summary-risk">{risk_b_text}</div>
                    <div class="summary-cost">{cost_b_text}</div>
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
        """).strip()
    return html_doc


def render_overlap_heatmap(matrix: pd.DataFrame) -> alt.Chart:
    heat_df = matrix.reset_index().rename(columns={"index": "fund_a"})
    heat_df = heat_df.melt(id_vars="fund_a", var_name="fund_b", value_name="overlap_pct")

    return (
        alt.Chart(heat_df)
        .mark_rect(cornerRadius=2)
        .encode(
            x=alt.X("fund_b:N", title="Fund B"),
            y=alt.Y("fund_a:N", title="Fund A"),
            color=alt.Color("overlap_pct:Q", title="Overlap %", scale=alt.Scale(scheme="blues")),
            tooltip=[
                alt.Tooltip("fund_a:N", title="Fund A"),
                alt.Tooltip("fund_b:N", title="Fund B"),
                alt.Tooltip("overlap_pct:Q", title="Overlap %", format=".2f"),
            ],
        )
        .properties(height=320)
    )


def run_two_fund_compare_tab(provider: VanguardUKProvider, product_options: list[dict]) -> None:
    mode_col1, mode_col2 = st.columns([2, 1])
    with mode_col1:
        lookthrough_mode = st.toggle("Ultimate Look-Through (Recursive)", value=False, key="pair_lookthrough_toggle")
    with mode_col2:
        max_depth = st.slider("Max Depth", min_value=1, max_value=6, value=4, step=1, key="pair_max_depth")

    if lookthrough_mode:
        st.info("Ultimate mode recursively expands fund-of-funds/ETF layers into deeper constituents where data is available.")

    use_picker = st.toggle("Use All Vanguard Products Picker", value=bool(product_options), key="pair_picker_toggle")

    if use_picker and product_options:
        st.caption("Search and select from Vanguard's full product list. You can still override with manual code input.")
        labels = [item["label"] for item in product_options]
        default_a = 0
        default_b = min(1, len(product_options) - 1)
        for i, item in enumerate(product_options):
            slug = item["slug"]
            if item["code"] == "VGL100A" or slug == "vanguard-lifestrategy-100-equity-fund-accumulation-shares":
                default_a = i
            if item["code"] == "VAR45GA" or slug == "vanguard-target-retirement-2045-fund-accumulation-shares":
                default_b = i

        col1, col2 = st.columns(2)
        with col1:
            picked_a = st.selectbox("Fund A", options=labels, index=default_a, key="pair_fund_a")
            ticker_a_override = st.text_input("Fund A manual code (optional)", value="", key="pair_fund_a_override")
        with col2:
            picked_b = st.selectbox("Fund B", options=labels, index=default_b, key="pair_fund_b")
            ticker_b_override = st.text_input("Fund B manual code (optional)", value="", key="pair_fund_b_override")

        selected_a = product_options[labels.index(picked_a)]
        selected_b = product_options[labels.index(picked_b)]
        ticker_a = (ticker_a_override.strip() or selected_a["code"]).upper()
        ticker_b = (ticker_b_override.strip() or selected_b["code"]).upper()
    else:
        if use_picker and not product_options:
            st.warning("Could not load product list, falling back to manual code entry.")
        col1, col2 = st.columns(2)
        with col1:
            ticker_a = st.text_input("Fund A", value="VGL100A", key="pair_manual_a")
        with col2:
            ticker_b = st.text_input("Fund B", value="VAR45GA", key="pair_manual_b")

    if st.button("Compare", type="primary", key="pair_compare_btn"):
        try:
            if lookthrough_mode:
                a = provider.get_holdings_lookthrough(ticker_a, max_depth=max_depth)
                b = provider.get_holdings_lookthrough(ticker_b, max_depth=max_depth)
            else:
                a = provider.get_holdings(ticker_a)
                b = provider.get_holdings(ticker_b)

            result = compare_funds(a, b)
            buckets = compare_by_bucket(a, b)

            st.subheader("Summary")
            components.html(render_summary_html(result["summary"]), height=380, scrolling=False)

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


def run_portfolio_tab(provider: VanguardUKProvider, product_options: list[dict]) -> None:
    st.caption("Analyze 3-12+ funds together and see overlap matrix plus weighted portfolio exposures.")

    mode_col1, mode_col2 = st.columns([2, 1])
    with mode_col1:
        lookthrough_mode = st.toggle("Ultimate Look-Through (Recursive)", value=False, key="portfolio_lookthrough_toggle")
    with mode_col2:
        max_depth = st.slider("Max Depth", min_value=1, max_value=6, value=4, step=1, key="portfolio_max_depth")

    if lookthrough_mode:
        st.info("Ultimate mode recursively expands fund-of-funds/ETF layers into deeper constituents where data is available.")

    if "portfolio_rows" not in st.session_state:
        st.session_state["portfolio_rows"] = pd.DataFrame(
            [
                {"ticker": "VGL100A", "weight_pct": 50.0},
                {"ticker": "VAR45GA", "weight_pct": 30.0},
                {"ticker": "VGL100A", "weight_pct": 20.0},
            ]
        )

    with st.expander("Load Portfolio From Text Lines", expanded=False):
        sample = "LifeStrategy® 20% Equity Fund 50%\nTarget Retirement 2045 Fund 30%\nLifeStrategy® 20% Equity Fund 20%"
        text = st.text_area("One fund per line: [name] [weight%]", value=sample, key="portfolio_lines")
        if st.button("Load Lines", key="portfolio_load_lines"):
            parsed, unresolved = parse_portfolio_lines(text, product_options)
            if parsed.empty:
                st.warning("No valid rows parsed from input.")
            else:
                st.session_state["portfolio_rows"] = parsed
                st.success(f"Loaded {len(parsed)} rows from text input.")
            if unresolved:
                st.info("Could not resolve these lines: " + "; ".join(unresolved))

    edited = st.data_editor(
        st.session_state["portfolio_rows"],
        num_rows="dynamic",
        use_container_width=True,
        key="portfolio_editor",
        column_config={
            "ticker": st.column_config.TextColumn("Fund Code (ticker/sedol/slug)", help="Example: VGL100A, VAR45GA, B41XG30"),
            "weight_pct": st.column_config.NumberColumn("Portfolio Weight %", min_value=0.0, max_value=1000.0, step=0.1, format="%.2f"),
        },
    )
    st.session_state["portfolio_rows"] = edited

    if st.button("Analyze Portfolio", type="primary", key="portfolio_analyze_btn"):
        if edited.empty:
            st.error("Add at least two funds with positive weights.")
            return

        rows = edited.copy()
        rows["ticker"] = rows["ticker"].astype(str).str.strip().str.upper()
        rows["weight_pct"] = pd.to_numeric(rows["weight_pct"], errors="coerce")
        rows = rows.dropna(subset=["weight_pct"])
        rows = rows[(rows["ticker"] != "") & (rows["weight_pct"] > 0)]

        if rows.empty:
            st.error("No valid positions found.")
            return

        rows = rows.groupby("ticker", as_index=False)["weight_pct"].sum().sort_values("weight_pct", ascending=False)
        total_weight = float(rows["weight_pct"].sum())

        if len(rows) < 2:
            st.error("At least two unique funds are required for an overlap matrix.")
            return

        if abs(total_weight - 100.0) > 0.01:
            st.warning(f"Portfolio weights sum to {total_weight:.2f}% (not 100%). Analysis uses entered weights as-is.")

        positions: list[PortfolioPosition] = []
        errors: list[str] = []
        with st.spinner("Fetching holdings for portfolio funds..."):
            for row in rows.itertuples(index=False):
                try:
                    if lookthrough_mode:
                        fund = provider.get_holdings_lookthrough(row.ticker, max_depth=max_depth)
                    else:
                        fund = provider.get_holdings(row.ticker)
                    positions.append(PortfolioPosition(fund=fund, portfolio_weight=float(row.weight_pct)))
                except Exception as exc:
                    errors.append(f"{row.ticker}: {exc}")

        if errors:
            st.error("Some funds failed to load: " + " | ".join(errors))
        if len(positions) < 2:
            st.error("Need at least two successfully loaded funds to continue.")
            return

        analysis = analyze_portfolio(positions)

        s = analysis["summary"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Funds", value=str(s["fund_count"]))
        m2.metric("Input Weight", value=f"{s['total_input_weight_pct']:.2f}%")
        m3.metric("Weighted Risk", value=(f"{s['weighted_risk']:.2f}/7" if s["weighted_risk"] is not None else "n/a"))
        m4.metric("Weighted OCF", value=(f"{s['weighted_ocf_pct']:.3f}%" if s["weighted_ocf_pct"] is not None else "n/a"))

        st.subheader("Pairwise Overlap Matrix")
        heatmap = render_overlap_heatmap(analysis["pairwise_overlap_matrix"])
        st.altair_chart(heatmap, use_container_width=True)
        st.dataframe(analysis["pairwise_overlap_matrix"].round(4), use_container_width=True)

        left, right = st.columns(2)
        with left:
            st.subheader("Top Underlying Exposures")
            top_underlying = analysis["underlying_exposures"].head(20).copy()
            if not top_underlying.empty:
                bar = (
                    alt.Chart(top_underlying)
                    .mark_bar(color="#1f77b4")
                    .encode(
                        x=alt.X("portfolio_contribution_pct:Q", title="Portfolio Exposure %"),
                        y=alt.Y("fund_name:N", sort="-x", title="Underlying"),
                        tooltip=[
                            alt.Tooltip("fund_name:N", title="Underlying"),
                            alt.Tooltip("portfolio_contribution_pct:Q", title="Exposure %", format=".3f"),
                            alt.Tooltip("num_funds_holding:Q", title="Held by # funds"),
                        ],
                    )
                    .properties(height=420)
                )
                st.altair_chart(bar, use_container_width=True)
            st.dataframe(top_underlying, use_container_width=True)

        with right:
            st.subheader("Bucket Exposures")
            buckets = analysis["bucket_exposures"].copy()
            if not buckets.empty:
                bar_b = (
                    alt.Chart(buckets)
                    .mark_bar(color="#2ca02c")
                    .encode(
                        x=alt.X("portfolio_contribution_pct:Q", title="Portfolio Exposure %"),
                        y=alt.Y("bucket:N", sort="-x", title="Bucket"),
                        tooltip=[
                            alt.Tooltip("bucket:N", title="Bucket"),
                            alt.Tooltip("portfolio_contribution_pct:Q", title="Exposure %", format=".3f"),
                            alt.Tooltip("num_holdings:Q", title="# underlyings"),
                        ],
                    )
                    .properties(height=420)
                )
                st.altair_chart(bar_b, use_container_width=True)
            st.dataframe(buckets, use_container_width=True)

provider = VanguardUKProvider()
product_options = load_product_options()

tab_pair, tab_portfolio = st.tabs(["Two-Fund Compare", "Portfolio Analysis"])

with tab_pair:
    run_two_fund_compare_tab(provider, product_options)

with tab_portfolio:
    run_portfolio_tab(provider, product_options)
