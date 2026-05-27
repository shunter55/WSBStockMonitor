"""Vercel FastAPI entrypoint: scheduled refresh + cached report for visitors."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wsb_monitor.runner import get_cached_report_html, refresh_cached_report

app = FastAPI(title="WSB Stock Monitor")

CACHE_HEADERS = {"Cache-Control": "public, max-age=300, stale-while-revalidate=600"}


def _apply_vercel_limits() -> None:
    if os.getenv("VERCEL") and not os.getenv("VERCEL_ALLOW_FULL_REDDIT_SCAN"):
        os.environ.setdefault("REDDIT_MAX_POSTS", "200")
        os.environ.setdefault("REDDIT_REQUEST_DELAY_SEC", "1")


def _verify_cron_secret(authorization: str | None) -> None:
    secret = os.getenv("CRON_SECRET")
    if not secret:
        return
    if authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def _resolve_cron_modes(
    *,
    reddit_only: bool,
    gemini_only: bool,
) -> tuple[bool, bool, str | None]:
    """Pick data sources for scheduled runs. Reddit public JSON is blocked from Vercel IPs."""
    if reddit_only and gemini_only:
        raise HTTPException(status_code=400, detail="Use only one of reddit_only or gemini_only")

    if reddit_only:
        return True, False, None
    if gemini_only:
        return False, True, None

    mode = os.getenv("CRON_MODE", "").strip().lower()
    if mode == "reddit_only":
        return True, False, None
    if mode == "gemini_only":
        return False, True, None
    if mode == "both":
        return False, False, None

    # Default on Vercel: Gemini only (Reddit returns 403 from datacenter IPs without OAuth)
    if os.getenv("VERCEL") and not os.getenv("REDDIT_CLIENT_ID"):
        return (
            False,
            True,
            "Reddit public API blocked from Vercel; using Gemini only. "
            "Run Reddit scans on your Pi, or add REDDIT_CLIENT_ID for OAuth.",
        )

    return False, False, None


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url="/api/latest", status_code=302)


@app.get("/api/latest", response_class=HTMLResponse)
def latest_report() -> HTMLResponse:
    """Serve the pre-generated report (fast, no API calls)."""
    html, meta = get_cached_report_html()
    if not html:
        return HTMLResponse(
            content=(
                "<!DOCTYPE html><html><body style='font-family:sans-serif;padding:2rem'>"
                "<h1>WSB Stock Monitor</h1>"
                "<p>No report has been generated yet. Wait for the next scheduled run, "
                "or trigger <code>/api/cron</code> manually.</p>"
                "</body></html>"
            ),
            status_code=503,
        )

    headers = dict(CACHE_HEADERS)
    if meta and meta.get("generated_at"):
        headers["X-Report-Generated-At"] = meta["generated_at"]
    return HTMLResponse(content=html, headers=headers)


@app.get("/api/cron")
def cron_refresh(
    authorization: str | None = Header(default=None),
    reddit_only: bool = Query(default=False),
    gemini_only: bool = Query(default=False),
) -> JSONResponse:
    """Generate report once and cache it. Called by Vercel Cron (daily)."""
    _verify_cron_secret(authorization)
    try:
        _apply_vercel_limits()
        use_reddit_only, use_gemini_only, note = _resolve_cron_modes(
            reddit_only=reddit_only,
            gemini_only=gemini_only,
        )
        result = refresh_cached_report(
            reddit_only=use_reddit_only,
            gemini_only=use_gemini_only,
        )
        if note:
            result["note"] = note
        result["modes"] = {
            "reddit_only": use_reddit_only,
            "gemini_only": use_gemini_only,
        }
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc), "trace": traceback.format_exc()},
            status_code=500,
        )


@app.get("/api/run")
def run_report_legacy() -> RedirectResponse:
    """Legacy URL — visitors should use cached /api/latest instead."""
    return RedirectResponse(url="/api/latest", status_code=307)
