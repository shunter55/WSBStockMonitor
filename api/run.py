"""Vercel serverless entry: GET /api/run returns the HTML report."""

from __future__ import annotations

import os
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from wsb_monitor.runner import generate_report_html


def _query_flags(path: str) -> tuple[bool, bool]:
    parsed = urlparse(path)
    params = parse_qs(parsed.query)
    reddit_only = params.get("reddit_only", ["0"])[0] in {"1", "true", "yes"}
    gemini_only = params.get("gemini_only", ["0"])[0] in {"1", "true", "yes"}
    return reddit_only, gemini_only


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            reddit_only, gemini_only = _query_flags(self.path)
            if os.getenv("VERCEL") and not os.getenv("VERCEL_ALLOW_FULL_REDDIT_SCAN"):
                os.environ.setdefault("REDDIT_MAX_POSTS", "200")
                os.environ.setdefault("REDDIT_REQUEST_DELAY_SEC", "1")

            html = generate_report_html(
                reddit_only=reddit_only,
                gemini_only=gemini_only,
            )
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "s-maxage=3600, stale-while-revalidate=600")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            message = traceback.format_exc()
            body = f"<pre>Report failed:\n{message}</pre>".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
