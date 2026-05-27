from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import types

from wsb_monitor.config import GeminiSettings
from wsb_monitor.parser import parse_stocks_json
from wsb_monitor.prompts import (
    JSON_RESPONSE_INSTRUCTION,
    STOCKS_RESPONSE_SCHEMA,
    system_instruction,
)


class GeminiClient:
    def __init__(self, settings: GeminiSettings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.api_key)

    def query(self, prompt: str) -> dict[str, Any]:
        # Google Search grounding cannot be combined with response_mime_type JSON.
        use_grounding = self._settings.use_grounding
        contents = prompt
        if use_grounding:
            contents = f"{prompt}\n\n{JSON_RESPONSE_INSTRUCTION}"

        config_kwargs: dict[str, Any] = {
            "system_instruction": system_instruction(self._settings.window_hours),
        }

        if use_grounding:
            config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        else:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_json_schema"] = STOCKS_RESPONSE_SCHEMA

        config = types.GenerateContentConfig(**config_kwargs)

        response = self._client.models.generate_content(
            model=self._settings.model,
            contents=contents,
            config=config,
        )

        text = response.text or ""
        parsed: dict[str, Any] | None = None
        if text:
            parsed = (
                parse_stocks_json(text)
                if use_grounding
                else json.loads(text)
            )

        return {
            "model": self._settings.model,
            "use_grounding": use_grounding,
            "text": text,
            "parsed": parsed,
            "usage_metadata": _usage_to_dict(response.usage_metadata),
        }


def _usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {"raw": str(usage)}
