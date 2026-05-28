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
BLOB_PATH_REPORT = "wsb-report/latest.json"
DEFAULT_LOCAL_REPORT = Path("data/reports/latest.json")


def save_latest_report(report: dict[str, Any]) -> dict[str, Any]:
    """Persist report JSON for fast reads. Uses Vercel Blob on Vercel, else local file."""
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if token:
        return _save_to_vercel_blob(report, token)
    return _save_to_local_files(report)


def load_latest_report() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (report, metadata) or (None, None) if no cached report exists."""
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
        store_id = store_id[len("store_"):]
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


def _save_to_vercel_blob(report: dict[str, Any], token: str) -> dict[str, Any]:
    _blob_put(token, BLOB_PATH_REPORT, json.dumps(report).encode("utf-8"), "application/json")
    return {"generated_at": report.get("generated_at", "")}


def _load_from_vercel_blob(token: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        data = _blob_fetch(token, BLOB_PATH_REPORT)
        report = json.loads(data.decode("utf-8"))
        return report, {"generated_at": report.get("generated_at", "")}
    except (requests.HTTPError, json.JSONDecodeError, KeyError, ValueError):
        return None, None


def _save_to_local_files(report: dict[str, Any]) -> dict[str, Any]:
    DEFAULT_LOCAL_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_LOCAL_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"generated_at": report.get("generated_at", "")}


def _load_from_local_files() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not DEFAULT_LOCAL_REPORT.exists():
        return None, None
    report = json.loads(DEFAULT_LOCAL_REPORT.read_text(encoding="utf-8"))
    return report, {"generated_at": report.get("generated_at", "")}


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
