from __future__ import annotations

import time
from typing import Any

from wsb_monitor.config import RedditSettings
from wsb_monitor.reddit.analysis import ScanStats, build_report, ingest_posts
from wsb_monitor.reddit import praw_source, public_source


def collect_wsb_data(settings: RedditSettings) -> dict[str, Any]:
    now = time.time()
    window_seconds = settings.window_hours * 3600
    recent_cutoff = now - window_seconds
    prior_cutoff = now - (2 * window_seconds)

    if settings.auth_mode == "oauth":
        posts = praw_source.iter_posts(settings, prior_cutoff)
        source_label = "Reddit OAuth API (PRAW)"
        data_source = "reddit_oauth"
    else:
        posts = public_source.iter_posts(settings, prior_cutoff)
        source_label = "Reddit public JSON (no API key)"
        data_source = "reddit_public_json"

    stats = ScanStats(data_source=data_source)

    def counted_posts():
        for created_utc, texts in posts:
            comment_count = max(0, len(texts) - 1)
            stats.comments_scanned += comment_count
            yield created_utc, texts

    recent, prior = ingest_posts(
        counted_posts(),
        recent_cutoff=recent_cutoff,
        prior_cutoff=prior_cutoff,
        max_posts=settings.max_posts,
        stats=stats,
    )

    return build_report(
        recent,
        prior,
        subreddit=settings.subreddit,
        window_hours=settings.window_hours,
        stats=stats,
        source_label=source_label,
    )
