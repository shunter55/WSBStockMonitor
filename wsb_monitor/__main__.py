from __future__ import annotations

import argparse
import http.server
import socketserver
import sys
import webbrowser
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from wsb_monitor.client import create_gemini_client
from wsb_monitor.config import AppSettings, load_settings
from wsb_monitor.html_report import html_from_json_file
from wsb_monitor.config import load_window_hours
from wsb_monitor.prompts import gemini_queries
from wsb_monitor.reddit import collect_wsb_data
from wsb_monitor.report import (
    build_gemini_section,
    build_reddit_section,
    print_summary,
    write_report,
)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="WSB stock mention monitor (Reddit + optional Gemini)."
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Fetch data and generate report (default)")
    _add_run_args(run_parser)

    serve_parser = subparsers.add_parser("serve", help="View reports in your browser")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument(
        "--open",
        action="store_true",
        help="Open latest report in browser",
    )

    html_parser = subparsers.add_parser(
        "html",
        help="Convert an existing JSON report to HTML",
    )
    html_parser.add_argument("json_file", type=Path, help="Path to wsb_report_*.json")

    args = parser.parse_args(argv)
    command = args.command or "run"

    if command == "serve":
        return cmd_serve(args)
    if command == "html":
        return cmd_html(args)

    return cmd_run(args)


def _add_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned work only; do not call APIs.",
    )
    parser.add_argument("--reddit-only", action="store_true")
    parser.add_argument("--gemini-only", action="store_true")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the HTML report in your browser after run",
    )


def cmd_run(args: argparse.Namespace) -> int:
    if getattr(args, "reddit_only", False) and getattr(args, "gemini_only", False):
        print("Error: use only one of --reddit-only or --gemini-only.", file=sys.stderr)
        return 1

    if args.dry_run:
        window_hours = load_window_hours()
        print(f"Would run with configured sources ({window_hours}h window):")
        print("  - Reddit: scan r/wallstreetbets (OAuth if configured, else public JSON)")
        if not args.reddit_only:
            print("  - Gemini: AI estimates for comparison")
            for _, title, query in gemini_queries(window_hours):
                print(f"\n--- Gemini: {title} ---\n{query}\n")
        return 0

    settings = load_settings(
        require_reddit=args.reddit_only,
        require_gemini=args.gemini_only,
    )

    if args.reddit_only:
        settings = _with_only_reddit(settings)
    elif args.gemini_only:
        settings = _with_only_gemini(settings)

    sources: dict[str, dict] = {}
    window_hours = settings.window_hours
    window_label = f"{window_hours}h"

    if settings.reddit:
        mode = settings.reddit.auth_mode
        print(
            f"Scanning r/{settings.reddit.subreddit} via Reddit ({mode})...",
            flush=True,
        )
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
            print(f"Querying Gemini ({settings.gemini.model}): {title}...", flush=True)
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

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subreddit": settings.reddit.subreddit if settings.reddit else "wallstreetbets",
        "window_hours": window_hours,
        "sources": sources,
    }

    json_path, html_path = write_report(settings.output_dir, report)
    print_summary(report)
    print(f"\nJSON report: {json_path}")
    print(f"HTML report: {html_path}")
    print(f"Quick link:  {settings.output_dir / 'latest.html'}")

    if args.open:
        webbrowser.open(html_path.resolve().as_uri())

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        settings = load_settings()
        output_dir = settings.output_dir
    except ValueError:
        output_dir = Path("data/reports")

    output_dir.mkdir(parents=True, exist_ok=True)
    latest = output_dir / "latest.html"
    if not latest.exists():
        print(
            f"No report yet. Run first:\n  python -m wsb_monitor run --reddit-only",
            file=sys.stderr,
        )
        return 1

    handler = functools_partial_handler(output_dir)
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}/latest.html"
        print(f"Serving {output_dir.resolve()}")
        print(f"Open: {url}")
        if args.open:
            webbrowser.open(url)
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


def cmd_html(args: argparse.Namespace) -> int:
    html_path = html_from_json_file(args.json_file)
    print(f"Wrote: {html_path}")
    return 0


def functools_partial_handler(directory: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *handler_args, **kwargs):
            super().__init__(*handler_args, directory=str(directory.resolve()), **kwargs)

    return Handler


def _with_only_reddit(settings: AppSettings) -> AppSettings:
    if settings.reddit is None:
        raise ValueError(
            "Reddit not configured. Use REDDIT_AUTH_MODE=public (no API key needed)."
        )
    return replace(settings, gemini=None)


def _with_only_gemini(settings: AppSettings) -> AppSettings:
    if settings.gemini is None:
        raise ValueError("Gemini API key not configured.")
    return replace(settings, reddit=None)


if __name__ == "__main__":
    # `python -m wsb_monitor --reddit-only` → same as `python -m wsb_monitor run --reddit-only`
    if len(sys.argv) <= 1 or sys.argv[1] not in {"run", "serve", "html"}:
        sys.argv.insert(1, "run")

    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
