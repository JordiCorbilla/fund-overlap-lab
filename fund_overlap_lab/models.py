from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class FundHoldings:
    ticker: str
    name: str
    source_url: str
    as_of: Optional[str]
    holdings: pd.DataFrame
    risk_level: Optional[int] = None
