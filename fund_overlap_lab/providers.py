from __future__ import annotations

import re
from io import StringIO
from typing import Dict
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .models import FundHoldings
from .utils import normalize_fund_name, parse_percentage


class VanguardUKProvider:
    """
    Pull direct underlying holdings from Vanguard UK portfolio-data pages.
    """

    FUND_URLS: Dict[str, str] = {
        "VGL100A": "https://www.vanguardinvestor.co.uk/investments/vanguard-lifestrategy-100-equity-fund-accumulation-shares/portfolio-data",
        "VAR45GA": "https://www.vanguardinvestor.co.uk/investments/vanguard-target-retirement-2045-fund-accumulation-shares/portfolio-data",
    }

    # Common shorthand/legacy aliases seen in user input.
    TICKER_ALIASES: Dict[str, str] = {
        "VL100AG": "VGL100A",
    }

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    API_BASE = "https://www.vanguardinvestor.co.uk/api"
    GPX_PATH = "/gpx/graphql"

    UNDERLYING_ALLOCATIONS_QUERY = """
query UnderlyingAllocationsQuery($portIds: [String!]!) {
    borHoldings(portIds: $portIds) {
        holdings(limit: 1500, securityTypes: [\"MF.MF\", \"EQ.ETF\", \"FI.IP\"]) {
            items {
                issuerName
                securityType
                marketValuePercentage
                sedol1
                effectiveDate
                securityLongDescription
            }
        }
    }
}
"""

    UNDERLYING_FUND_NAMES_QUERY = """
query UnderlyingFundNamesQuery($sedols: [String!]) {
    funds(sedols: $sedols) {
        profile {
            fundFullName
            portId
        }
    }
}
"""

    def get_holdings(self, ticker: str) -> FundHoldings:
        ticker, url = self._resolve_ticker_and_url(ticker)
        gpx_result = self._extract_holdings_from_gpx(url)
        if gpx_result is not None:
            name = str(gpx_result.get("name") or "Unknown Fund")
            as_of = gpx_result.get("as_of")
            risk_level = gpx_result.get("risk_level")
            ocf = gpx_result.get("ocf")
            holdings = gpx_result["holdings"]
        else:
            html = self._fetch_html(url)
            soup = BeautifulSoup(html, "lxml")

            name = self._extract_title(soup)
            as_of = self._extract_as_of(soup)
            risk_level = None
            ocf = None
            try:
                holdings = self._extract_underlying_table(soup)
            except ValueError:
                api_fallback = self._extract_holdings_from_api(url)
                if api_fallback is None:
                    raise

                holdings = api_fallback["holdings"]
                risk_level = api_fallback.get("risk_level")
                ocf = api_fallback.get("ocf")
                if (
                    (name == "Unknown Fund" or "Personal Investing in the UK" in name)
                    and api_fallback.get("name")
                ):
                    name = str(api_fallback["name"])
                if as_of is None and api_fallback.get("as_of"):
                    as_of = str(api_fallback["as_of"])

        holdings["fund_name_norm"] = holdings["fund_name"].map(normalize_fund_name)

        return FundHoldings(
            ticker=ticker,
            name=name,
            source_url=url,
            as_of=as_of,
            holdings=holdings[["fund_name", "weight_pct", "fund_name_norm"]].copy(),
            risk_level=risk_level,
            ocf=ocf,
        )

    def list_products(self) -> list[dict]:
        products = self._fetch_json(f"{self.API_BASE}/productList")
        if not isinstance(products, list):
            return []

        out: list[dict] = []
        for item in products:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or "").strip()
            slug = str(item.get("id") or "").strip()
            ticker = str(item.get("ticker") or "").strip().upper()
            sedol = str(item.get("sedol") or "").strip().upper()
            share_class = str(item.get("shareClass") or "").strip()

            if not slug:
                continue

            code = ticker or sedol or slug
            if not code:
                continue

            out.append(
                {
                    "code": code,
                    "name": name or slug,
                    "ticker": ticker,
                    "sedol": sedol,
                    "slug": slug,
                    "share_class": share_class,
                }
            )

        out.sort(key=lambda p: (p["name"].lower(), p["code"]))
        return out

    def _resolve_ticker_and_url(self, ticker: str) -> tuple[str, str]:
        requested = ticker.upper().strip()
        resolved = self.TICKER_ALIASES.get(requested, requested)

        if resolved in self.FUND_URLS:
            return resolved, self.FUND_URLS[resolved]

        product = self._lookup_product_by_code(resolved)
        if product is not None:
            slug = str(product.get("id") or "").strip()
            if slug:
                return resolved, f"https://www.vanguardinvestor.co.uk/investments/{slug}/portfolio-data"

        supported = ", ".join(sorted(self.FUND_URLS))
        raise KeyError(f"Unsupported ticker '{requested}'. Supported examples: {supported}")

    def _lookup_product_by_code(self, code: str) -> dict | None:
        try:
            products = self._fetch_json(f"{self.API_BASE}/productList")
        except Exception:
            return None

        if not isinstance(products, list):
            return None

        code_upper = code.upper().strip()
        for item in products:
            if not isinstance(item, dict):
                continue
            sedol = str(item.get("sedol") or "").upper().strip()
            ticker = str(item.get("ticker") or "").upper().strip()
            slug = str(item.get("id") or "").upper().strip()
            if code_upper in {sedol, ticker, slug}:
                return item
        return None

    def _fetch_html(self, url: str) -> str:
        response = requests.get(url, headers=self.HEADERS, timeout=30)
        response.raise_for_status()
        return response.text

    def _fetch_json(self, url: str) -> dict | list:
        response = requests.get(url, headers=self.HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()

    def _post_json(self, url: str, payload: dict) -> dict | list:
        response = requests.post(url, json=payload, headers=self.HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()

    def _extract_holdings_from_gpx(self, fund_url: str) -> dict | None:
        slug = self._slug_from_fund_url(fund_url)
        if slug is None:
            return None

        product = self._lookup_product_by_slug(slug)
        if not product:
            return None

        port_id = product.get("portId")
        if port_id is None:
            return None

        fund_data = None
        risk_level = None
        ocf = None
        try:
            data = self._fetch_json(f"{self.API_BASE}/funds/{port_id}")
            if isinstance(data, dict):
                fund_data = data
                risk_level = self._extract_risk_level(data)
                ocf = self._extract_ocf(data)
        except Exception:
            pass

        gpx_url = f"{urlparse(fund_url).scheme}://{urlparse(fund_url).netloc}{self.GPX_PATH}"

        try:
            allocations_payload = {
                "operationName": "UnderlyingAllocationsQuery",
                "query": self.UNDERLYING_ALLOCATIONS_QUERY,
                "variables": {"portIds": [str(port_id)]},
            }
            allocations = self._post_json(gpx_url, allocations_payload)
        except Exception:
            return None

        items = (
            allocations.get("data", {})
            .get("borHoldings", [{}])[0]
            .get("holdings", {})
            .get("items", [])
            if isinstance(allocations, dict)
            else []
        )
        if not items:
            return None

        rows = []
        as_of = None
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                pct = float(item.get("marketValuePercentage"))
            except (TypeError, ValueError):
                continue
            if pct <= 0:
                continue
            sedol = str(item.get("sedol1") or "").strip()
            if as_of is None:
                as_of = item.get("effectiveDate")
            rows.append(
                {
                    "fund_name": str(item.get("issuerName") or item.get("securityLongDescription") or "").strip(),
                    "weight_pct": pct,
                    "security_type": str(item.get("securityType") or "").strip(),
                    "sedol1": sedol,
                }
            )

        if not rows:
            return None

        # Resolve cleaner fund names from sedol-based profile query when available.
        sedols = [r["sedol1"] for r in rows if r["sedol1"] and r["security_type"] != "FI.IP"]
        name_map = self._fetch_fund_names_by_sedol(gpx_url, sedols)
        for r in rows:
            mapped = name_map.get(r["sedol1"])
            if mapped:
                r["fund_name"] = mapped

        out = pd.DataFrame(rows)
        out["fund_name"] = out["fund_name"].str.replace("Vanguard ", "", regex=False).str.strip()
        out = out[out["fund_name"] != ""]
        if out.empty:
            return None

        # Aggregate any duplicate rows after name normalization.
        out = out.groupby("fund_name", as_index=False)["weight_pct"].sum()
        out = out.sort_values("weight_pct", ascending=False).reset_index(drop=True)

        return {
            "name": (fund_data or {}).get("name") or product.get("name"),
            "as_of": as_of,
            "risk_level": risk_level,
            "ocf": ocf,
            "holdings": out,
        }

    def _fetch_fund_names_by_sedol(self, gpx_url: str, sedols: list[str]) -> dict[str, str]:
        unique_sedols = list(dict.fromkeys([s for s in sedols if s]))
        if not unique_sedols:
            return {}

        payload = {
            "operationName": "UnderlyingFundNamesQuery",
            "query": self.UNDERLYING_FUND_NAMES_QUERY,
            "variables": {"sedols": unique_sedols},
        }

        try:
            response = self._post_json(gpx_url, payload)
        except Exception:
            return {}

        funds = response.get("data", {}).get("funds", []) if isinstance(response, dict) else []
        if not isinstance(funds, list):
            return {}

        # This endpoint returns funds in the same order as request sedols.
        out: dict[str, str] = {}
        for sedol, fund in zip(unique_sedols, funds):
            if not isinstance(fund, dict):
                continue
            profile = fund.get("profile") if isinstance(fund.get("profile"), dict) else {}
            full_name = str(profile.get("fundFullName") or "").strip()
            if full_name:
                out[sedol] = full_name
        return out

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(" ", strip=True)
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return "Unknown Fund"

    @staticmethod
    def _extract_as_of(soup: BeautifulSoup) -> str | None:
        text = soup.get_text(" ", strip=True)
        match = re.search(r"As at\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", text)
        return match.group(1) if match else None

    def _extract_underlying_table(self, soup: BeautifulSoup) -> pd.DataFrame:
        from_tables = self._extract_from_html_tables(soup)
        if from_tables is not None:
            return from_tables

        from_text = self._extract_from_text_lines(soup)
        if from_text is not None:
            return from_text

        raise ValueError("Could not locate underlying funds section in HTML")

    def _extract_holdings_from_api(self, fund_url: str) -> dict | None:
        slug = self._slug_from_fund_url(fund_url)
        if slug is None:
            return None

        product = self._lookup_product_by_slug(slug)
        if not product:
            return None

        port_id = product.get("portId")
        if port_id is None:
            return None

        try:
            fund_data = self._fetch_json(f"{self.API_BASE}/funds/{port_id}")
        except Exception:
            return None

        holdings = self._asset_allocations_to_holdings(fund_data)
        if holdings is None:
            return None

        return {
            "name": fund_data.get("name") or product.get("name"),
            "as_of": fund_data.get("totalAssetsAsOfDate"),
            "risk_level": self._extract_risk_level(fund_data),
            "ocf": self._extract_ocf(fund_data),
            "holdings": holdings,
        }

    @staticmethod
    def _extract_risk_level(fund_data: dict) -> int | None:
        if not isinstance(fund_data, dict):
            return None
        risk = fund_data.get("risk")
        if not isinstance(risk, dict):
            return None
        value = risk.get("value")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_ocf(fund_data: dict) -> str | None:
        if not isinstance(fund_data, dict):
            return None
        value = fund_data.get("OCF")
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    def _lookup_product_by_slug(self, slug: str) -> dict | None:
        try:
            products = self._fetch_json(f"{self.API_BASE}/productList")
        except Exception:
            return None

        if not isinstance(products, list):
            return None

        for item in products:
            if isinstance(item, dict) and item.get("id") == slug:
                return item
        return None

    @staticmethod
    def _slug_from_fund_url(fund_url: str) -> str | None:
        path = urlparse(fund_url).path.strip("/")
        parts = path.split("/")
        if len(parts) < 3:
            return None
        if parts[0] != "investments":
            return None
        return parts[1]

    @staticmethod
    def _asset_allocations_to_holdings(fund_data: dict) -> pd.DataFrame | None:
        allocations = fund_data.get("assetAllocations") if isinstance(fund_data, dict) else None
        if not isinstance(allocations, list):
            return None

        rows: list[tuple[str, float]] = []
        for item in allocations:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            value = item.get("value")
            if not label:
                continue
            try:
                pct = float(value)
            except (TypeError, ValueError):
                continue
            if pct <= 0:
                continue
            rows.append((f"{label} Allocation", pct))

        if not rows:
            return None

        return pd.DataFrame(rows, columns=["fund_name", "weight_pct"])

    def _extract_from_html_tables(self, soup: BeautifulSoup) -> pd.DataFrame | None:
        try:
            tables = pd.read_html(StringIO(str(soup)))
        except Exception:
            return None

        best: pd.DataFrame | None = None
        best_score = -1.0

        for table in tables:
            candidate = self._table_to_holdings(table)
            if candidate is None or candidate.empty:
                continue

            score = float(len(candidate))
            total_weight = float(candidate["weight_pct"].sum())
            if 70.0 <= total_weight <= 130.0:
                score += 20.0
            if total_weight > 0:
                score += 5.0

            if score > best_score:
                best_score = score
                best = candidate

        return best.reset_index(drop=True) if best is not None else None

    @staticmethod
    def _table_to_holdings(table: pd.DataFrame) -> pd.DataFrame | None:
        if table is None or table.empty or table.shape[1] < 2:
            return None

        candidate = table.copy()
        candidate.columns = [str(c).strip() for c in candidate.columns]

        weight_col = None
        for col in candidate.columns:
            header = col.lower()
            if any(tok in header for tok in ("%", "percentage", "allocation", "weight", "net assets", "portfolio")):
                weight_col = col
                break

        if weight_col is None:
            for col in candidate.columns:
                values = candidate[col].astype(str)
                if values.str.contains(r"\d+(?:[\.,]\d+)?\s*%", regex=True).sum() >= max(2, int(len(values) * 0.4)):
                    weight_col = col
                    break

        if weight_col is None:
            return None

        name_col = None
        for col in candidate.columns:
            if col == weight_col:
                continue
            values = candidate[col].astype(str).str.strip()
            if (values != "").sum() == 0:
                continue
            if values.str.contains(r"[A-Za-z]", regex=True).mean() >= 0.6:
                name_col = col
                break

        if name_col is None:
            return None

        out = candidate[[name_col, weight_col]].copy()
        out.columns = ["fund_name", "weight_raw"]
        out["fund_name"] = out["fund_name"].astype(str).str.strip()
        out["weight_raw"] = out["weight_raw"].astype(str).str.replace(",", "", regex=False).str.strip()
        out = out[out["fund_name"] != ""]
        out = out[out["weight_raw"].str.contains(r"\d", regex=True)]
        if out.empty:
            return None

        out["weight_pct"] = out["weight_raw"].str.extract(r"(-?\d+(?:\.\d+)?)")[0]
        out = out.dropna(subset=["weight_pct"])
        if out.empty:
            return None

        out["weight_pct"] = out["weight_pct"].map(parse_percentage)
        out = out[(out["weight_pct"] >= 0.0) & (out["weight_pct"] <= 100.0)]
        if out.empty:
            return None

        return out[["fund_name", "weight_pct"]]

    @staticmethod
    def _extract_from_text_lines(soup: BeautifulSoup) -> pd.DataFrame | None:
        text = soup.get_text("\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return None

        anchor_terms = ("underlying", "holdings", "portfolio", "allocation")
        stop_terms = ("asset allocation", "region", "sector", "country", "disclaimer", "risk")

        anchors = [
            i
            for i, line in enumerate(lines)
            if any(term in line.lower() for term in anchor_terms)
        ]

        def parse_window(start: int) -> list[tuple[str, float]]:
            rows: list[tuple[str, float]] = []
            for line in lines[start : start + 180]:
                lowered = line.lower()
                if rows and any(stop in lowered for stop in stop_terms):
                    break
                match = re.match(r"(.+?)\s+(-?\d{1,3}(?:[\.,]\d+)?)\s*%$", line)
                if not match:
                    continue
                name = match.group(1).strip()
                pct = float(match.group(2).replace(",", ""))
                if 0.0 <= pct <= 100.0 and len(name) >= 3:
                    rows.append((name, pct))
            return rows

        # Prefer rows close to domain-specific anchors.
        for idx in anchors:
            rows = parse_window(idx)
            if len(rows) >= 2:
                return pd.DataFrame(rows, columns=["fund_name", "weight_pct"])

        # As a final fallback, scan from the top and require enough rows.
        rows = parse_window(0)
        if len(rows) >= 2:
            return pd.DataFrame(rows, columns=["fund_name", "weight_pct"])

        return None
