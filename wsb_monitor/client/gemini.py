from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import types

from wsb_monitor.config import GeminiSettings
from wsb_monitor.parser import normalize_gemini_parsed
from wsb_monitor.prompts import (
    COMBINED_JSON_RESPONSE_INSTRUCTION,
    GEMINI_COMBINED_RESPONSE_SCHEMA,
    gemini_combined_query,
    system_instruction,
)


class GeminiClient:
    def __init__(self, settings: GeminiSettings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.api_key)

    def query_combined(self) -> dict[str, Any]:
        """Single Gemini request returning all Gemini report sections."""
        window_hours = self._settings.window_hours
        prompt = gemini_combined_query(window_hours)
        return self._generate(
            prompt,
            json_schema=GEMINI_COMBINED_RESPONSE_SCHEMA,
            json_instruction=COMBINED_JSON_RESPONSE_INSTRUCTION,
            parse_response=parse_combined_json,
        )

    def _generate(
        self,
        prompt: str,
        *,
        json_schema: dict,
        json_instruction: str,
        parse_response: Any,
    ) -> dict[str, Any]:
        use_grounding = self._settings.use_grounding
        contents = f"{prompt}\n\n{json_instruction}" if use_grounding else prompt

        config_kwargs: dict[str, Any] = {
            "system_instruction": system_instruction(self._settings.window_hours),
            "temperature": self._settings.temperature,
        }

        if use_grounding:
            config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        else:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_json_schema"] = json_schema

        config = types.GenerateContentConfig(**config_kwargs)

        response = self._client.models.generate_content(
            model=self._settings.model,
            contents=contents,
            config=config,
        )

        text = response.text or ""
        parsed: dict[str, Any] | None = None
        if text:
            parsed = parse_response(text) if use_grounding else json.loads(text)
            if isinstance(parsed, dict):
                parsed = normalize_gemini_parsed(parsed)

        return {
            "model": self._settings.model,
            "use_grounding": use_grounding,
            "text": text,
            "parsed": parsed,
            "usage_metadata": _usage_to_dict(response.usage_metadata),
        }


def parse_combined_json(answer_text: str) -> dict[str, Any]:
    if not answer_text.strip():
        raise ValueError("Empty response from Gemini")

    last_error: Exception | None = None
    for candidate in _json_candidates(answer_text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(data, dict):
            continue
        if _valid_combined_sections(data):
            return normalize_gemini_parsed(data)

    raise ValueError(
        "Could not parse combined stock JSON from Gemini response. "
        f"Last error: {last_error}"
    )


def _valid_combined_sections(data: dict[str, Any]) -> bool:
    from wsb_monitor.prompts import GEMINI_SECTION_IDS

    for key in GEMINI_SECTION_IDS:
        section = data.get(key)
        if not isinstance(section, dict) or "stocks" not in section:
            return False
    return True


def _json_candidates(text: str) -> list[str]:
    from wsb_monitor.parser import _extract_json_candidates

    candidates = [text.strip()]
    candidates.extend(_extract_json_candidates(text))
    return candidates


def _usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {"raw": str(usage)}
