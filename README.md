# fund-overlap-lab

A Python tool to pull the underlying holdings of wrapper funds and compare overlap between two funds.

Initial provider support:
- Vanguard UK wrapper funds via published `portfolio-data` pages

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

Other strong names you could use later:
- `lookthrough-engine`
- `fund-xray`
- `overlap-alpha`
- `portfolio-overlap`

## Features

- Fetch direct underlying holdings for a supported wrapper fund
- Normalize holding names for more reliable joins
- Compute direct overlap using `sum(min(weight_a, weight_b))`
- Compute bucket overlap using a curated asset bucket map
- Export comparison results to CSV
- Inspect results in Streamlit

## Supported example instruments

- `VGL100A` — LifeStrategy 100% Equity Fund
- `VAR45GA` — Target Retirement 2045 Fund

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows PowerShell

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

## Streamlit usage

```bash
streamlit run app.py
```

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
    └── test_compare.py
```

## Notes

- This project is intentionally **wrapper-level** first.
- It does **not** yet do security-level look-through.
- Vanguard markup may change, so the parser includes fallback logic but is not guaranteed permanently stable.
- For a more robust production version, add:
  - response caching
  - PDF factsheet fallback
  - more providers
  - historical snapshots
  - proper identifier mapping

## Suggested next steps

1. Add disk caching for fetched HTML
2. Add a provider registry and YAML config
3. Add PDF fallback parsing for factsheets
4. Add economic exposure mapping beyond simple name matching
5. Add a portfolio-vs-candidate overlap mode

