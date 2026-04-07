from bs4 import BeautifulSoup

from fund_overlap_lab.providers import VanguardUKProvider


def test_extract_underlying_table_from_html_table():
    html = """
    <html>
      <body>
        <h2>Portfolio composition</h2>
        <table>
          <thead>
            <tr><th>Underlying fund</th><th>Allocation (%)</th></tr>
          </thead>
          <tbody>
            <tr><td>US Equity Index Fund</td><td>55.5%</td></tr>
            <tr><td>Global Bond Index Fund Hedged</td><td>44.5%</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")

    provider = VanguardUKProvider()
    result = provider._extract_underlying_table(soup)

    assert len(result) == 2
    assert list(result["fund_name"]) == [
        "US Equity Index Fund",
        "Global Bond Index Fund Hedged",
    ]
    assert list(result["weight_pct"]) == [55.5, 44.5]


def test_extract_underlying_table_from_text_fallback():
    html = """
    <html>
      <body>
        <div>Allocation to underlying investments</div>
        <div>US Equity Index Fund 60.0%</div>
        <div>UK Equity Index Fund 40.0%</div>
        <div>Asset allocation</div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")

    provider = VanguardUKProvider()
    result = provider._extract_underlying_table(soup)

    assert len(result) == 2
    assert list(result["weight_pct"]) == [60.0, 40.0]


def test_slug_from_fund_url():
    url = "https://www.vanguardinvestor.co.uk/investments/vanguard-lifestrategy-100-equity-fund-accumulation-shares/portfolio-data"
    assert VanguardUKProvider._slug_from_fund_url(url) == "vanguard-lifestrategy-100-equity-fund-accumulation-shares"


def test_asset_allocations_to_holdings():
    payload = {
        "assetAllocations": [
            {"label": "Equity", "value": 80},
            {"label": "Bonds", "value": 20},
            {"label": "Cash", "value": 0},
        ]
    }
    out = VanguardUKProvider._asset_allocations_to_holdings(payload)
    assert out is not None
    assert list(out["fund_name"]) == ["Equity Allocation", "Bonds Allocation"]
    assert list(out["weight_pct"]) == [80.0, 20.0]
