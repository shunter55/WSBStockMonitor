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
            return parsed
    return parse_stocks_json(extract_answer_text(raw_payload))


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
