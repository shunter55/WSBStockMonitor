"""Vercel Python entrypoint (FastAPI). Routes: GET /api/run"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, RedirectResponse

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wsb_monitor.runner import generate_report_html

app = FastAPI(title="WSB Stock Monitor")


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url="/index.html", status_code=302)


@app.get("/api/run", response_class=HTMLResponse)
def run_report(
    reddit_only: bool = Query(default=False),
    gemini_only: bool = Query(default=False),
) -> HTMLResponse:
    try:
        if os.getenv("VERCEL") and not os.getenv("VERCEL_ALLOW_FULL_REDDIT_SCAN"):
            os.environ.setdefault("REDDIT_MAX_POSTS", "200")
            os.environ.setdefault("REDDIT_REQUEST_DELAY_SEC", "1")

        html = generate_report_html(
            reddit_only=reddit_only,
            gemini_only=gemini_only,
        )
        return HTMLResponse(
            content=html,
            headers={"Cache-Control": "s-maxage=3600, stale-while-revalidate=600"},
        )
    except Exception:
        return HTMLResponse(
            content=f"<pre>Report failed:\n{traceback.format_exc()}</pre>",
            status_code=500,
        )
