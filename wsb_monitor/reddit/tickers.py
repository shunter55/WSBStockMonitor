from __future__ import annotations

import re

CASHTAG_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")
BARE_TICKER_PATTERN = re.compile(r"\b([A-Z]{2,5})\b")

# Common English / finance words that match ticker shape but are not tickers.
TICKER_BLOCKLIST = frozenset(
    {
        "A",
        "AI",
        "ALL",
        "AM",
        "AN",
        "AND",
        "API",
        "ARE",
        "AS",
        "AT",
        "BE",
        "BIG",
        "CEO",
        "CFO",
        "DD",
        "DJT",
        "EPS",
        "ER",
        "ETF",
        "EU",
        "EV",
        "FDA",
        "FDIC",
        "FOR",
        "GDP",
        "GO",
        "HAS",
        "HE",
        "HER",
        "HIS",
        "HODL",
        "IMO",
        "IN",
        "IPO",
        "IRS",
        "IS",
        "IT",
        "ITS",
        "IV",
        "LLC",
        "LOL",
        "LT",
        "ME",
        "MY",
        "NEWS",
        "NOT",
        "NOW",
        "NYSE",
        "OF",
        "ON",
        "ONE",
        "OR",
        "OTM",
        "OUT",
        "PE",
        "PM",
        "PS",
        "RH",
        "SEC",
        "SEE",
        "SO",
        "THE",
        "THIS",
        "TO",
        "TOP",
        "UK",
        "UP",
        "US",
        "USA",
        "UTC",
        "VS",
        "WSB",
        "YOLO",
        "YOU",
    }
)


def extract_tickers(text: str) -> set[str]:
    if not text:
        return set()

    tickers: set[str] = set()
    for match in CASHTAG_PATTERN.findall(text):
        if _is_valid_ticker(match):
            tickers.add(match)

    for match in BARE_TICKER_PATTERN.findall(text):
        if match in tickers:
            continue
        if _is_valid_ticker(match):
            tickers.add(match)

    return tickers


def _is_valid_ticker(symbol: str) -> bool:
    if not symbol or len(symbol) > 5:
        return False
    if symbol in TICKER_BLOCKLIST:
        return False
    return symbol.isalpha()
