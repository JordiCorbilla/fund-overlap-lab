# fund-overlap-lab

A Python tool to pull underlying holdings of wrapper funds and compare overlap across two-fund and multi-fund workflows.

Current provider support:
- Vanguard UK funds via product catalog plus GraphQL holdings endpoints

Included interfaces:
- CLI
- Streamlit UI
- Reusable Python package

## Project name

**fund-overlap-lab**

Why this name:
- explicit about the goal
- broad enough to extend beyond Vanguard
- not tied to one provider or asset class

## Features

- Fetch holdings by code, SEDOL, or slug (plus common aliases)
- Normalize holding names for reliable joins
- Compute direct overlap using sum(min(weight_a, weight_b))
- Compute bucket overlap with curated asset bucket mapping
- Surface risk and OCF (when available)
- Two-Fund Compare tab with rich summary and detailed tables
- Portfolio Analysis tab with pairwise overlap matrix and weighted exposures
- Optional Ultimate Look-Through mode (recursive expansion) in both app tabs
- Portfolio text-line loader with robust normalization and fuzzy matching
- Export compare outputs to CSV via CLI

## Supported example instruments

- VGL100A - LifeStrategy 100% Equity Fund
- VAR45GA - Target Retirement 2045 Fund
- B76VTL9 - ESG Developed Europe Index Fund (Accumulation)

Note:
- The provider can resolve many instruments dynamically from Vanguard product data.

## Install

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\activate

pip install -r requirements.txt
```

## CLI usage

### Compare two funds

```bash
python -m fund_overlap_lab.cli compare VGL100A VAR45GA
```

### Save CSV outputs

```bash
python -m fund_overlap_lab.cli compare VGL100A VAR45GA --outdir ./output
```

### Dump holdings for one fund

```bash
python -m fund_overlap_lab.cli holdings VGL100A
```

CLI scope today:
- Direct holdings and two-fund comparison.
- Portfolio matrix and recursive look-through are currently exposed in the Streamlit app.

## Streamlit usage

```bash
streamlit run app.py
```

In the app you can:
- Compare two funds side-by-side
- Toggle Ultimate Look-Through and set max recursion depth
- Analyze a multi-fund portfolio with matrix heatmap and weighted exposures
- Load portfolio weights from pasted text lines

## Output metrics

### Direct wrapper overlap

For each shared underlying holding `i`:

```text
overlap_i = min(weight_a_i, weight_b_i)
```

Total overlap:

```text
total_overlap = sum(overlap_i)
```

This is the cleanest metric for direct wrapper comparison.

When Ultimate Look-Through is enabled in the app, the same overlap math is applied after recursive expansion.

### Bucket overlap

Holdings are mapped into coarse economic buckets such as:
- UK Equity
- US Equity
- Developed World ex UK Equity
- Emerging Markets Equity
- Global Bonds Hedged
- UK Government Bonds
- UK Investment Grade Bonds

This helps capture economic similarity even when wrapper holdings differ.

## Data pipeline

The provider uses a layered retrieval strategy:

- Primary: GraphQL holdings queries
- Fallback: HTML table/text parsing
- Resilience fallback: API allocation-level extraction

This improves reliability as upstream web rendering patterns evolve.

## Project structure

```text
fund-overlap-lab/
├── app.py
├── requirements.txt
├── README.md
├── fund_overlap_lab/
│   ├── __init__.py
│   ├── buckets.py
│   ├── cli.py
│   ├── compare.py
│   ├── models.py
│   ├── providers.py
│   └── utils.py
└── tests/
    ├── test_compare.py
    ├── test_portfolio.py
    └── test_providers.py
```

## Notes

- Ultimate look-through can return large outputs for mixed portfolios.
- Some instruments are wrappers, others expose security-level constituents directly.
- Results depend on source holdings availability and may include cash or FX lines.
- Upstream endpoint behavior can change over time.

## Suggested next steps

1. Add optional filters for cash, FX, and derivatives in ultimate mode
2. Expand bucket mapping to reduce Other classifications
3. Add local caching for repeated runs
4. Add historical snapshot support for overlap drift analysis
5. Add additional providers beyond Vanguard UK

