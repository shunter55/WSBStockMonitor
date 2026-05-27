from __future__ import annotations

import time
from typing import Any, Iterator
from urllib.parse import urljoin

import requests

from wsb_monitor.config import RedditSettings

REDDIT_HOSTS = (
    "https://www.reddit.com",
    "https://old.reddit.com",
)


def iter_posts(settings: RedditSettings, prior_cutoff: float) -> Iterator[tuple[float, list[str]]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": settings.user_agent,
            "Accept": "application/json",
        }
    )

    after: str | None = None
    posts_yielded = 0

    while posts_yielded < settings.max_posts:
        listing = _fetch_listing(session, settings, after=after)
        children = listing.get("data", {}).get("children") or []
        if not children:
            break

        for child in children:
            post = child.get("data") or {}
            created = float(post.get("created_utc", 0))
            if created < prior_cutoff:
                return

            texts = [f"{post.get('title', '')}\n{post.get('selftext', '')}"]
            if settings.max_comments_per_post > 0:
                permalink = post.get("permalink") or ""
                texts.extend(
                    _fetch_comment_bodies(
                        session,
                        permalink,
                        settings.max_comments_per_post,
                        settings.request_delay_sec,
                    )
                )

            posts_yielded += 1
            yield created, texts

            if posts_yielded >= settings.max_posts:
                return

        after = listing.get("data", {}).get("after")
        if not after:
            break
        time.sleep(settings.request_delay_sec)


def _fetch_listing(
    session: requests.Session,
    settings: RedditSettings,
    *,
    after: str | None,
) -> dict[str, Any]:
    params: dict[str, str | int] = {"limit": 100, "raw_json": 1}
    if after:
        params["after"] = after
    last_error: Exception | None = None
    for host in REDDIT_HOSTS:
        url = f"{host}/r/{settings.subreddit}/new.json"
        try:
            return _get_json(session, url, params=params, settings=settings)
        except requests.HTTPError as exc:
            last_error = exc
            if exc.response is not None and exc.response.status_code in {403, 451}:
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("Could not fetch Reddit listing")


def _fetch_comment_bodies(
    session: requests.Session,
    permalink: str,
    max_comments: int,
    delay_sec: float,
) -> list[str]:
    if not permalink or max_comments <= 0:
        return []

    base = REDDIT_HOSTS[0]
    if permalink.startswith("http"):
        url = permalink.rstrip("/") + ".json"
    else:
        url = urljoin(base, permalink.rstrip("/") + ".json")
    time.sleep(delay_sec)
    payload = _get_json(session, url, params={"raw_json": 1, "limit": max_comments})

    bodies: list[str] = []
    if not isinstance(payload, list) or len(payload) < 2:
        return bodies

    comments_listing = payload[1].get("data", {}).get("children") or []
    for child in comments_listing:
        if len(bodies) >= max_comments:
            break
        data = child.get("data") or {}
        if data.get("body"):
            bodies.append(data["body"])
    return bodies


def _get_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None,
    settings: RedditSettings,
) -> dict[str, Any]:
    for attempt in range(3):
        response = session.get(url, params=params, timeout=45)
        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", settings.request_delay_sec * 5))
            time.sleep(max(wait, settings.request_delay_sec))
            continue
        response.raise_for_status()
        return response.json()

    raise RuntimeError(f"Reddit rate-limited after retries: {url}")
