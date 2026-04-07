from __future__ import annotations

import re


def normalize_fund_name(name: str) -> str:
    s = name.lower().strip()
    replacements = {
        "u.k.": "uk",
        "u.s.": "us",
        "ex-u.k.": "ex uk",
        "ex-japan": "ex japan",
        "accumulating": "acc",
        "accumulation": "acc",
        "shares": "",
        "share": "",
        "fund": "fund",
        "unit trust": "unit trust",
        "&": " and ",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)

    s = re.sub(r"\bgbp\b", "", s)
    s = re.sub(r"\busd\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_percentage(value: str) -> float:
    s = str(value).strip().replace("%", "").replace(",", "")
    return float(s)
