from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from wsb_monitor.client import create_gemini_client
from wsb_monitor.config import AppSettings, load_settings
from wsb_monitor.html_report import render_html
from wsb_monitor.prompts import gemini_queries
from wsb_monitor.reddit import collect_wsb_data
from wsb_monitor.report import build_gemini_section, build_reddit_section


def build_report(
    settings: AppSettings,
    *,
    reddit_only: bool = False,
    gemini_only: bool = False,
) -> dict[str, Any]:
    if reddit_only:
        settings = _with_only_reddit(settings)
    elif gemini_only:
        settings = _with_only_gemini(settings)

    sources: dict[str, dict] = {}
    window_hours = settings.window_hours
    window_label = f"{window_hours}h"

    if settings.reddit:
        reddit_data = collect_wsb_data(settings.reddit)
        sources["reddit"] = {
            "sections": [
                build_reddit_section(
                    section_id="top_mentions",
                    title=f"Top 10 most mentioned ({window_label}) — Reddit",
                    parsed=reddit_data["top_mentions"],
                    stats=reddit_data["stats"],
                ),
                build_reddit_section(
                    section_id="mention_momentum",
                    title=f"Top 10 fastest mention growth ({window_label}) — Reddit",
                    parsed=reddit_data["mention_momentum"],
                    stats=reddit_data["stats"],
                ),
            ],
            "scan_stats": reddit_data["stats"],
        }

    if settings.gemini:
        client = create_gemini_client(settings.gemini)
        gemini_sections = []
        for section_id, title, query in gemini_queries(window_hours):
            raw = client.query(query)
            gemini_sections.append(
                build_gemini_section(
                    section_id=section_id,
                    title=f"{title} — Gemini",
                    query=query,
                    raw_payload=raw,
                )
            )
        sources["gemini"] = {
            "model": settings.gemini.model,
            "use_grounding": settings.gemini.use_grounding,
            "sections": gemini_sections,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subreddit": settings.reddit.subreddit if settings.reddit else "wallstreetbets",
        "window_hours": window_hours,
        "sources": sources,
    }


def generate_report_html(
    *,
    reddit_only: bool = False,
    gemini_only: bool = False,
) -> str:
    settings = load_settings(
        require_reddit=reddit_only,
        require_gemini=gemini_only,
    )
    report = build_report(
        settings,
        reddit_only=reddit_only,
        gemini_only=gemini_only,
    )
    return render_html(report)


def _with_only_reddit(settings: AppSettings) -> AppSettings:
    if settings.reddit is None:
        raise ValueError("Reddit not configured.")
    return replace(settings, gemini=None)


def _with_only_gemini(settings: AppSettings) -> AppSettings:
    if settings.gemini is None:
        raise ValueError("Gemini API key not configured.")
    return replace(settings, reddit=None)
