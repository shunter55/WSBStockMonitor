from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wsb_monitor.html_report import write_html_report
from wsb_monitor.parser import extract_answer_text, parse_stocks_payload


def build_gemini_section(
    *,
    section_id: str,
    title: str,
    query: str,
    raw_payload: dict[str, Any],
    parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    answer_text = extract_answer_text(raw_payload)
    if parsed is None:
        parsed = parse_stocks_payload(raw_payload)
    return {
        "id": section_id,
        "title": title,
        "query": query,
        "parsed": parsed,
        "answer_text": answer_text,
        "raw_provider_response": raw_payload,
    }


def build_reddit_section(
    *,
    section_id: str,
    title: str,
    parsed: dict[str, Any],
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": section_id,
        "title": title,
        "parsed": parsed,
        "stats": stats,
    }


def write_report(output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"wsb_report_{timestamp}.json"
    html_path = output_dir / f"wsb_report_{timestamp}.html"
    latest_path = output_dir / "latest.html"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_html_report(report, html_path)
    write_html_report(report, latest_path)
    return json_path, html_path


def print_summary(report: dict[str, Any]) -> None:
    sources = report.get("sources") or {}
    if not sources and report.get("sections"):
        sources = {"legacy": {"sections": report["sections"]}}

    for source_name, source_data in sources.items():
        print(f"\n{'=' * 8} {source_name.upper()} {'=' * 8}")
        for section in source_data.get("sections", []):
            print(f"\n--- {section['title']} ---")
            stocks = section.get("parsed", {}).get("stocks") or []
            for stock in stocks:
                ticker = stock.get("ticker", "?")
                bullish = stock.get("bullish_pct", "?")
                bearish = stock.get("bearish_pct", "?")
                metric = stock.get("mention_metric", "")
                value = stock.get("mention_value", "")
                extra = ""
                if growth := stock.get("mention_growth_pct"):
                    extra = f" (+{growth}% vs prior window)"
                print(
                    f"  #{stock.get('rank', '?'):>2} {ticker:6}  "
                    f"bull {bullish}% / bear {bearish}%  |  {metric}: {value}{extra}"
                )

            section_stats = section.get("stats")
            if section_stats:
                print(
                    f"  (scanned {section_stats.get('posts_scanned', '?')} posts, "
                    f"{section_stats.get('comments_scanned', '?')} comments)"
                )
