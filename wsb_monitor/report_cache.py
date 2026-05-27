from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

BLOB_PATH_HTML = "wsb-report/latest.html"
BLOB_PATH_META = "wsb-report/meta.json"
DEFAULT_LOCAL_HTML = Path("data/reports/latest.html")
DEFAULT_LOCAL_META = Path("data/reports/latest.meta.json")


def save_latest_report(html: str, *, generated_at: str | None = None) -> dict[str, Any]:
    """Persist HTML report for fast reads. Uses Vercel Blob on Vercel, else local file."""
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    token = os.getenv("BLOB_READ_WRITE_TOKEN")

    if token:
        meta = _save_to_vercel_blob(html, token, generated_at)
    else:
        meta = _save_to_local_files(html, generated_at)

    return meta


def load_latest_report() -> tuple[str | None, dict[str, Any] | None]:
    """Return (html, metadata) or (None, None) if no cached report exists."""
    token = os.getenv("BLOB_READ_WRITE_TOKEN")

    if token:
        return _load_from_vercel_blob(token)
    return _load_from_local_files()


def _save_to_vercel_blob(html: str, token: str, generated_at: str) -> dict[str, Any]:
    html_resp = _blob_put(token, BLOB_PATH_HTML, html.encode("utf-8"), "text/html")
    meta = {
        "generated_at": generated_at,
        "html_url": html_resp.get("url"),
        "html_pathname": html_resp.get("pathname", BLOB_PATH_HTML),
    }
    _blob_put(
        token,
        BLOB_PATH_META,
        json.dumps(meta).encode("utf-8"),
        "application/json",
    )
    return meta


def _load_from_vercel_blob(token: str) -> tuple[str | None, dict[str, Any] | None]:
    try:
        meta_bytes = _blob_get(token, BLOB_PATH_META)
        meta = json.loads(meta_bytes.decode("utf-8"))
    except (requests.HTTPError, json.JSONDecodeError, KeyError):
        return None, None

    html_url = meta.get("html_url")
    if not html_url:
        return None, meta

    response = requests.get(html_url, timeout=60)
    response.raise_for_status()
    return response.text, meta


def _save_to_local_files(html: str, generated_at: str) -> dict[str, Any]:
    DEFAULT_LOCAL_HTML.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_LOCAL_HTML.write_text(html, encoding="utf-8")
    meta = {"generated_at": generated_at, "html_path": str(DEFAULT_LOCAL_HTML)}
    DEFAULT_LOCAL_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _load_from_local_files() -> tuple[str | None, dict[str, Any] | None]:
    if not DEFAULT_LOCAL_HTML.exists():
        return None, None
    meta: dict[str, Any] | None = None
    if DEFAULT_LOCAL_META.exists():
        meta = json.loads(DEFAULT_LOCAL_META.read_text(encoding="utf-8"))
    return DEFAULT_LOCAL_HTML.read_text(encoding="utf-8"), meta


def _blob_put(
    token: str,
    pathname: str,
    data: bytes,
    content_type: str,
) -> dict[str, Any]:
    response = requests.put(
        f"https://blob.vercel-storage.com/?pathname={quote(pathname, safe='')}",
        headers={
            "Authorization": f"Bearer {token}",
            "x-api-version": "10",
            "x-content-type": content_type,
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
            "x-access": "public",
        },
        data=data,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def _blob_get(token: str, pathname: str) -> bytes:
    response = requests.get(
        f"https://blob.vercel-storage.com/?pathname={quote(pathname, safe='')}",
        headers={
            "Authorization": f"Bearer {token}",
            "x-api-version": "10",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.content
