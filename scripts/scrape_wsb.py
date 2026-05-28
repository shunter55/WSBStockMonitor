#!/usr/bin/env python3
"""POC: scrape latest r/wallstreetbets posts directly, no API key required."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REDDIT_BASE = "https://www.reddit.com"
USER_AGENT = "wsbstockmonitor-scraper:0.1 (poc)"


def fetch_posts(subreddit: str, limit: int) -> list[dict]:
    posts: list[dict] = []
    after: str | None = None
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    while len(posts) < limit:
        batch = min(100, limit - len(posts))
        params: dict = {"limit": batch, "raw_json": 1}
        if after:
            params["after"] = after

        url = f"{REDDIT_BASE}/r/{subreddit}/new.json"
        response = session.get(url, params=params, timeout=30)

        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 10))
            print(f"Rate limited — waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue

        response.raise_for_status()
        data = response.json()
        children = data["data"]["children"]
        if not children:
            break

        for child in children:
            p = child["data"]
            upvote_ratio = p.get("upvote_ratio") or 1.0
            score = p.get("score") or 0
            try:
                est_downvotes = round(score / upvote_ratio * (1 - upvote_ratio))
            except ZeroDivisionError:
                est_downvotes = 0

            posts.append({
                "title": p.get("title", ""),
                "score": score,
                "upvote_ratio": upvote_ratio,
                "estimated_downvotes": est_downvotes,
                "num_comments": p.get("num_comments", 0),
                "created_utc": int(p.get("created_utc", 0)),
                "permalink": p.get("permalink", ""),
                "url": p.get("url", ""),
            })

        after = data["data"].get("after")
        if not after:
            break

        time.sleep(1)

    return posts


def print_table(posts: list[dict]) -> None:
    print(f"\n{'#':<4} {'Score':>6}  {'↑%':>5}  {'↓est':>6}  {'Cmts':>5}  Title")
    print("-" * 90)
    for i, p in enumerate(posts, 1):
        title = p["title"][:55] + "…" if len(p["title"]) > 55 else p["title"]
        print(
            f"{i:<4} {p['score']:>6}  {p['upvote_ratio']*100:>4.0f}%  "
            f"{p['estimated_downvotes']:>6}  {p['num_comments']:>5}  {title}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape r/wallstreetbets posts (no API key)")
    parser.add_argument("--limit", type=int, default=25, help="Number of posts to fetch (default: 25)")
    parser.add_argument("--subreddit", default="wallstreetbets")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "output")
    parser.add_argument("--no-save", action="store_true", help="Skip writing JSON file")
    args = parser.parse_args()

    print(f"Fetching {args.limit} posts from r/{args.subreddit}...", file=sys.stderr)
    posts = fetch_posts(args.subreddit, args.limit)
    print(f"Got {len(posts)} posts.", file=sys.stderr)

    print_table(posts)

    if not args.no_save:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = args.output_dir / f"wsb_scrape_{ts}.json"
        payload = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "subreddit": args.subreddit,
            "posts_fetched": len(posts),
            "posts": posts,
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nSaved → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
