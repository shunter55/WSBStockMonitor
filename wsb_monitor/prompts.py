from __future__ import annotations

STOCKS_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "stocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "ticker": {"type": "string"},
                    "exchange": {
                        "type": "string",
                        "description": (
                            "Google Finance exchange code, e.g. NASDAQ, NYSE, "
                            "NYSEARCA, AMEX, OTCMKTS"
                        ),
                    },
                    "company_name": {"type": "string"},
                    "mention_metric": {"type": "string"},
                    "mention_value": {"type": "number"},
                    "bullish_pct": {"type": "number"},
                    "bearish_pct": {"type": "number"},
                    "sentiment_notes": {"type": "string"},
                },
                "required": [
                    "rank",
                    "ticker",
                    "exchange",
                    "mention_metric",
                    "mention_value",
                    "bullish_pct",
                    "bearish_pct",
                ],
            },
            "minItems": 10,
            "maxItems": 10,
        },
        "sources_summary": {"type": "string"},
        "as_of": {"type": "string"},
    },
    "required": ["stocks", "sources_summary", "as_of"],
}

GEMINI_COMBINED_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "top_mentions": STOCKS_RESPONSE_SCHEMA,
        "mention_momentum": STOCKS_RESPONSE_SCHEMA,
    },
    "required": ["top_mentions", "mention_momentum"],
}


def _hours_label(window_hours: int) -> str:
    return f"{window_hours} hour" if window_hours == 1 else f"{window_hours} hours"


def system_instruction(window_hours: int) -> str:
    hours = _hours_label(window_hours)
    return f"""You are a financial social-media analyst focused on Reddit r/wallstreetbets.
Use recent web and Reddit discussion signals when available. Prefer verifiable, current sources.
For each stock, estimate mention counts or growth from the last {hours} and split community tone
into bullish_pct and bearish_pct (should sum to ~100). Include exchange using Google Finance codes
(NASDAQ, NYSE, NYSEARCA, AMEX, OTCMKTS, etc.) so ticker links resolve correctly. If data is
uncertain, say so in sentiment_notes.
"""


def top_mentions_query(window_hours: int) -> str:
    hours = _hours_label(window_hours)
    return f"""
What are the top 10 stock tickers most mentioned on Reddit r/wallstreetbets in the last {hours}?
For each ticker provide estimated mention volume in the last {hours} and bullish vs bearish sentiment %.
""".strip()


def momentum_mentions_query(window_hours: int) -> str:
    hours = _hours_label(window_hours)
    return f"""
What are the top 10 stock tickers on Reddit r/wallstreetbets with the largest increase in mentions
over the last {hours} compared to the prior {hours}?
For each ticker provide the mention increase (count or percent) and bullish vs bearish sentiment %.
""".strip()


JSON_RESPONSE_INSTRUCTION = """
Respond with ONLY valid JSON (no markdown fences, no extra text) matching this shape:
{
  "stocks": [
    {
      "rank": 1,
      "ticker": "GME",
      "exchange": "NYSE",
      "company_name": "",
      "mention_metric": "...",
      "mention_value": 0,
      "bullish_pct": 50.0,
      "bearish_pct": 50.0,
      "sentiment_notes": "..."
    }
  ],
  "sources_summary": "...",
  "as_of": "ISO-8601 timestamp"
}
Include exactly 10 items in stocks.
""".strip()

COMBINED_JSON_RESPONSE_INSTRUCTION = """
Respond with ONLY valid JSON (no markdown fences, no extra text) matching this shape:
{
  "top_mentions": {
    "stocks": [
      {
        "rank": 1,
        "ticker": "GME",
        "exchange": "NYSE",
        "mention_metric": "estimated mentions (96h)",
        "mention_value": 1200,
        "bullish_pct": 55.0,
        "bearish_pct": 45.0
      }
    ],
    "sources_summary": "...",
    "as_of": "ISO-8601 timestamp"
  },
  "mention_momentum": {
    "stocks": [
      {
        "rank": 1,
        "ticker": "GME",
        "exchange": "NYSE",
        "mention_metric": "mention increase vs prior 96h",
        "mention_value": 400,
        "bullish_pct": 60.0,
        "bearish_pct": 40.0
      }
    ],
    "sources_summary": "...",
    "as_of": "ISO-8601 timestamp"
  }
}
Each stocks array must have exactly 10 items with rank (1-10), exchange, mention_metric, and mention_value.
""".strip()


def gemini_combined_query(window_hours: int) -> str:
    return f"""
Answer both of the following about Reddit r/wallstreetbets in a single JSON response.

## Section 1 — top_mentions
{top_mentions_query(window_hours)}

## Section 2 — mention_momentum
{momentum_mentions_query(window_hours)}
""".strip()


def gemini_queries(window_hours: int) -> list[tuple[str, str, str]]:
    label = f"{window_hours}h"
    return [
        ("top_mentions", f"Top 10 most mentioned ({label})", top_mentions_query(window_hours)),
        (
            "mention_momentum",
            f"Top 10 fastest mention growth ({label})",
            momentum_mentions_query(window_hours),
        ),
    ]
