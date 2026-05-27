from __future__ import annotations

BULLISH_TERMS = (
    "moon",
    "mooning",
    "calls",
    "call",
    "long",
    "buy",
    "bull",
    "bullish",
    "rocket",
    "🚀",
    "hold",
    "yolo",
    "green",
    "rip",
    "undervalued",
    "breakout",
    "squeeze",
    "tendies",
    "pump",
    "gain",
    "gains",
)

BEARISH_TERMS = (
    "puts",
    "put",
    "short",
    "sell",
    "bear",
    "bearish",
    "crash",
    "tank",
    "dump",
    "red",
    "overvalued",
    "bagholder",
    "bagholding",
    "drill",
    "loss",
    "losses",
    "rug",
    "bubble",
)


def score_text(text: str) -> tuple[float, float]:
    """Return (bullish_pct, bearish_pct) for a piece of text."""
    lower = text.lower()
    bull = sum(1 for term in BULLISH_TERMS if term in lower)
    bear = sum(1 for term in BEARISH_TERMS if term in lower)

    if bull == 0 and bear == 0:
        return 50.0, 50.0

    total = bull + bear
    return round(bull / total * 100, 1), round(bear / total * 100, 1)


def aggregate_ticker_sentiment(
    scores: list[tuple[float, float]],
) -> tuple[float, float, str]:
    if not scores:
        return 50.0, 50.0, "no text with sentiment keywords"

    bull_avg = sum(s[0] for s in scores) / len(scores)
    bear_avg = sum(s[1] for s in scores) / len(scores)
    total = bull_avg + bear_avg
    if total == 0:
        return 50.0, 50.0, "neutral"

    bullish_pct = round(bull_avg / total * 100, 1)
    bearish_pct = round(100 - bullish_pct, 1)
    return bullish_pct, bearish_pct, f"keyword-based over {len(scores)} mentions"
