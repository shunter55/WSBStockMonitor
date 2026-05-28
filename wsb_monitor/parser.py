from __future__ import annotations

import json
import re
from typing import Any


def extract_answer_text(payload: dict[str, Any]) -> str:
    if text := payload.get("text"):
        return str(text)

    if markdown := payload.get("reconstructed_markdown"):
        return str(markdown)

    blocks = payload.get("text_blocks") or []
    parts: list[str] = []
    for block in blocks:
        parts.extend(_flatten_text_block(block))
    return "\n".join(parts).strip()


def parse_stocks_json(answer_text: str) -> dict[str, Any]:
    if not answer_text.strip():
        raise ValueError("Empty response from Gemini")

    candidates = [answer_text.strip()]
    candidates.extend(_extract_json_candidates(answer_text))

    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and "stocks" in data:
                return data
            if isinstance(data, list):
                return {"stocks": data, "sources_summary": None, "as_of": None}
        except json.JSONDecodeError as exc:
            last_error = exc

    raise ValueError(
        "Could not parse stock JSON from Gemini response. "
        f"Last error: {last_error}"
    )


def parse_stocks_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    if parsed := raw_payload.get("parsed"):
        if isinstance(parsed, dict) and "stocks" in parsed:
            return normalize_stocks_section(parsed)
    return normalize_stocks_section(parse_stocks_json(extract_answer_text(raw_payload)))


def parse_gemini_section_payload(
    raw_payload: dict[str, Any],
    section_id: str,
) -> dict[str, Any]:
    parsed = raw_payload.get("parsed")
    if isinstance(parsed, dict):
        section = parsed.get(section_id)
        if isinstance(section, dict) and "stocks" in section:
            return normalize_stocks_section(section, section_id=section_id)
    raise ValueError(f"Gemini response missing parsed section '{section_id}'")


def normalize_gemini_parsed(parsed: dict[str, Any]) -> dict[str, Any]:
    """Map alternate Gemini field names to the report schema."""
    if "stocks" in parsed:
        parsed["stocks"] = normalize_stocks(parsed["stocks"])
    for section_id in ("top_mentions", "mention_momentum"):
        section = parsed.get(section_id)
        if isinstance(section, dict) and "stocks" in section:
            parsed[section_id] = normalize_stocks_section(section, section_id=section_id)
    return parsed


def normalize_stocks_section(
    section: dict[str, Any],
    *,
    section_id: str | None = None,
) -> dict[str, Any]:
    stocks = section.get("stocks")
    if not isinstance(stocks, list):
        return section
    return {**section, "stocks": normalize_stocks(stocks, section_id=section_id)}


def normalize_stocks(
    stocks: list[Any],
    *,
    section_id: str | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(stocks):
        if isinstance(item, dict):
            normalized.append(normalize_stock(item, index=index, section_id=section_id))
    return normalized


def normalize_stock(
    stock: dict[str, Any],
    *,
    index: int,
    section_id: str | None = None,
) -> dict[str, Any]:
    out = dict(stock)

    rank = _coerce_int(
        stock.get("rank"),
        stock.get("position"),
        stock.get("order"),
    )
    out["rank"] = rank if rank is not None else index + 1

    ticker = stock.get("ticker") or stock.get("symbol") or stock.get("ticker_symbol")
    if ticker is not None:
        out["ticker"] = str(ticker).upper().strip().lstrip("$")

    exchange = stock.get("exchange") or stock.get("market") or stock.get("listing_exchange")
    if exchange is not None:
        out["exchange"] = normalize_exchange(str(exchange))

    value = stock.get("mention_value")
    if value is None:
        value = _first_present(
            stock,
            "mentions",
            "mention_count",
            "estimated_mentions",
            "mention_volume",
            "volume",
            "count",
            "increase",
            "mention_increase",
            "growth",
            "mention_growth",
        )
    if value is not None:
        out["mention_value"] = _coerce_number(value)

    metric = stock.get("mention_metric") or stock.get("metric") or stock.get("mention_type")
    if not metric and section_id == "top_mentions":
        metric = "estimated mentions"
    elif not metric and section_id == "mention_momentum":
        metric = "mention increase"
    if metric:
        out["mention_metric"] = str(metric)

    if stock.get("mention_growth_pct") is None:
        growth = _first_present(
            stock,
            "mention_growth_pct",
            "growth_pct",
            "percent_increase",
            "increase_pct",
        )
        if growth is not None:
            out["mention_growth_pct"] = _coerce_number(growth)

    return out


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None and data[key] != "":
            return data[key]
    return None


def _coerce_int(*values: Any) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


_EXCHANGE_ALIASES: dict[str, str] = {
    "NASDAQ": "NASDAQ",
    "NYSE": "NYSE",
    "NYSE ARCA": "NYSEARCA",
    "ARCA": "NYSEARCA",
    "NYSEARCA": "NYSEARCA",
    "AMEX": "AMEX",
    "NYSE AMERICAN": "AMEX",
    "NYSEAMERICAN": "AMEX",
    "OTC": "OTCMKTS",
    "OTCBB": "OTCMKTS",
    "OTCMKTS": "OTCMKTS",
    "PINK": "OTCMKTS",
    "BATS": "BATS",
    "CBOE": "CBOE",
}


def normalize_exchange(exchange: str) -> str:
    key = exchange.strip().upper().replace(".", "")
    return _EXCHANGE_ALIASES.get(key, key)


def _coerce_number(value: Any) -> int | float:
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    if "." in text:
        return float(text)
    return int(text)


def _flatten_text_block(block: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if answer := block.get("answer"):
        lines.append(str(answer))
    if snippet := block.get("snippet"):
        lines.append(str(snippet))

    for item in block.get("items") or []:
        if isinstance(item, dict):
            lines.extend(_flatten_text_block(item))
        elif isinstance(item, str):
            lines.append(item)

    for nested in block.get("text_blocks") or []:
        if isinstance(nested, dict):
            lines.extend(_flatten_text_block(nested))

    return lines


def _extract_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []

    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE):
        candidates.append(match.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])

    return candidates
