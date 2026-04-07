from __future__ import annotations

import argparse
from pathlib import Path

from .compare import compare_by_bucket, compare_funds
from .providers import VanguardUKProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fund-overlap-lab", description="Compare overlap between wrapper funds")
    sub = parser.add_subparsers(dest="command", required=True)

    p_holdings = sub.add_parser("holdings", help="Fetch holdings for one fund")
    p_holdings.add_argument("ticker", help="Fund code, e.g. VGL100A")

    p_compare = sub.add_parser("compare", help="Compare two funds")
    p_compare.add_argument("ticker_a")
    p_compare.add_argument("ticker_b")
    p_compare.add_argument("--outdir", type=Path, default=None, help="Optional output directory for CSV files")

    return parser


def cmd_holdings(ticker: str) -> int:
    provider = VanguardUKProvider()
    fund = provider.get_holdings(ticker)
    print(f"Ticker: {fund.ticker}")
    print(f"Name:   {fund.name}")
    print(f"As of:  {fund.as_of}")
    print(f"URL:    {fund.source_url}")
    print()
    print(fund.holdings.to_string(index=False))
    return 0


def cmd_compare(ticker_a: str, ticker_b: str, outdir: Path | None) -> int:
    provider = VanguardUKProvider()
    a = provider.get_holdings(ticker_a)
    b = provider.get_holdings(ticker_b)

    result = compare_funds(a, b)
    buckets = compare_by_bucket(a, b)

    print("SUMMARY")
    for k, v in result["summary"].items():
        print(f"- {k}: {v}")
    print()

    print("COMMON HOLDINGS")
    print(result["common_holdings"].to_string(index=False))
    print()

    print("BUCKET OVERLAP")
    print(buckets.to_string(index=False))

    if outdir is not None:
        outdir.mkdir(parents=True, exist_ok=True)
        result["common_holdings"].to_csv(outdir / "common_holdings.csv", index=False)
        result["only_in_a"].to_csv(outdir / "only_in_a.csv", index=False)
        result["only_in_b"].to_csv(outdir / "only_in_b.csv", index=False)
        result["full_matrix"].to_csv(outdir / "full_matrix.csv", index=False)
        buckets.to_csv(outdir / "bucket_overlap.csv", index=False)
        print()
        print(f"Saved CSV outputs to: {outdir.resolve()}")

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "holdings":
        return cmd_holdings(args.ticker)
    if args.command == "compare":
        return cmd_compare(args.ticker_a, args.ticker_b, args.outdir)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
