from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

BLOB_API_URL = "https://vercel.com/api/blob"
BLOB_API_VERSION = "12"
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


def _blob_access() -> str:
    access = os.getenv("BLOB_ACCESS", "private").strip().lower()
    return access if access in ("public", "private") else "private"


def _parse_store_id(token: str) -> str:
    """Extract store id from BLOB_READ_WRITE_TOKEN (vercel_blob_rw_<storeId>_...)."""
    parts = token.split("_")
    if len(parts) < 4:
        raise ValueError("Invalid BLOB_READ_WRITE_TOKEN format")
    store_id = parts[3]
    if store_id.startswith("store_"):
        store_id = store_id[len("store_") :]
    return store_id


def _blob_headers(token: str, *, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-version": BLOB_API_VERSION,
        "x-vercel-blob-store-id": _parse_store_id(token),
    }
    if extra:
        headers.update(extra)
    return headers


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


def _blob_content_url(token: str, pathname: str) -> str:
    store_id = _parse_store_id(token)
    return f"https://{store_id}.{_blob_access()}.blob.vercel-storage.com/{pathname}"


def _blob_fetch(token: str, url_or_pathname: str) -> bytes:
    """Fetch blob bytes. Private stores require Authorization on the CDN URL."""
    url = (
        url_or_pathname
        if url_or_pathname.startswith("http")
        else _blob_content_url(token, url_or_pathname)
    )
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()
    return response.content


def _load_from_vercel_blob(token: str) -> tuple[str | None, dict[str, Any] | None]:
    try:
        meta_bytes = _blob_fetch(token, BLOB_PATH_META)
        meta = json.loads(meta_bytes.decode("utf-8"))
    except (requests.HTTPError, json.JSONDecodeError, KeyError, ValueError):
        return None, None

    html_ref = meta.get("html_pathname") or meta.get("html_url")
    if not html_ref:
        return None, meta

    try:
        html = _blob_fetch(token, html_ref).decode("utf-8")
    except requests.HTTPError:
        return None, meta
    return html, meta


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
    query = urlencode({"pathname": pathname})
    response = requests.put(
        f"{BLOB_API_URL}/?{query}",
        headers=_blob_headers(
            token,
            extra={
                "x-vercel-blob-access": _blob_access(),
                "x-content-type": content_type,
                "x-add-random-suffix": "0",
                "x-allow-overwrite": "1",
                "x-content-length": str(len(data)),
            },
        ),
        data=data,
        timeout=120,
    )
    if not response.ok:
        detail = response.text[:500] if response.text else response.reason
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {detail}",
            response=response,
        )
    return response.json()
