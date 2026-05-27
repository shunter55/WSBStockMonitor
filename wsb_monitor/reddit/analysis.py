from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from wsb_monitor.reddit.sentiment import aggregate_ticker_sentiment, score_text
from wsb_monitor.reddit.tickers import extract_tickers


@dataclass
class WindowCounts:
    mention_counts: Counter[str] = field(default_factory=Counter)
    sentiment_scores: dict[str, list[tuple[float, float]]] = field(
        default_factory=lambda: defaultdict(list)
    )


@dataclass
class ScanStats:
    posts_scanned: int = 0
    comments_scanned: int = 0
    posts_in_recent_window: int = 0
    posts_in_prior_window: int = 0
    data_source: str = ""


def window_for_timestamp(
    created_utc: float,
    *,
    recent_cutoff: float,
    prior_cutoff: float,
) -> str | None:
    if created_utc >= recent_cutoff:
        return "recent"
    if created_utc >= prior_cutoff:
        return "prior"
    return None


def record_text(window: WindowCounts, text: str) -> None:
    tickers = extract_tickers(text)
    if not tickers:
        return

    bull, bear = score_text(text)
    for ticker in tickers:
        window.mention_counts[ticker] += 1
        window.sentiment_scores[ticker].append((bull, bear))


def ingest_posts(
    posts: Iterable[tuple[float, list[str]]],
    *,
    recent_cutoff: float,
    prior_cutoff: float,
    max_posts: int,
    stats: ScanStats,
) -> tuple[WindowCounts, WindowCounts]:
    recent = WindowCounts()
    prior = WindowCounts()

    for created_utc, texts in posts:
        if stats.posts_scanned >= max_posts:
            break

        window_name = window_for_timestamp(
            created_utc,
            recent_cutoff=recent_cutoff,
            prior_cutoff=prior_cutoff,
        )
        if window_name is None:
            break

        stats.posts_scanned += 1
        if window_name == "recent":
            stats.posts_in_recent_window += 1
            target = recent
        else:
            stats.posts_in_prior_window += 1
            target = prior

        for text in texts:
            record_text(target, text)

    return recent, prior


def build_report(
    recent: WindowCounts,
    prior: WindowCounts,
    *,
    subreddit: str,
    window_hours: int,
    stats: ScanStats,
    source_label: str,
) -> dict[str, Any]:
    return {
        "top_mentions": _build_top_mentions(
            recent, window_hours, subreddit=subreddit, source_label=source_label
        ),
        "mention_momentum": _build_momentum(
            recent, prior, window_hours, subreddit=subreddit
        ),
        "stats": {
            "posts_scanned": stats.posts_scanned,
            "comments_scanned": stats.comments_scanned,
            "posts_in_recent_window": stats.posts_in_recent_window,
            "posts_in_prior_window": stats.posts_in_prior_window,
            "subreddit": subreddit,
            "window_hours": window_hours,
            "data_source": stats.data_source,
        },
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def _build_top_mentions(
    recent: WindowCounts,
    window_hours: int,
    *,
    subreddit: str,
    source_label: str,
) -> dict[str, Any]:
    stocks = []
    for rank, (ticker, count) in enumerate(recent.mention_counts.most_common(10), start=1):
        bullish, bearish, notes = aggregate_ticker_sentiment(
            recent.sentiment_scores[ticker]
        )
        stocks.append(
            {
                "rank": rank,
                "ticker": ticker,
                "company_name": "",
                "mention_metric": f"mentions (last {window_hours}h)",
                "mention_value": count,
                "bullish_pct": bullish,
                "bearish_pct": bearish,
                "sentiment_notes": notes,
            }
        )

    return {
        "stocks": stocks,
        "sources_summary": (
            f"r/{subreddit} via {source_label} ({window_hours}h window)"
        ),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def _build_momentum(
    recent: WindowCounts,
    prior: WindowCounts,
    window_hours: int,
    *,
    subreddit: str,
) -> dict[str, Any]:
    growth: list[tuple[str, int, int, float]] = []
    all_tickers = set(recent.mention_counts) | set(prior.mention_counts)

    for ticker in all_tickers:
        recent_count = recent.mention_counts[ticker]
        prior_count = prior.mention_counts[ticker]
        delta = recent_count - prior_count
        if delta <= 0:
            continue
        pct = round((delta / max(prior_count, 1)) * 100, 1)
        growth.append((ticker, delta, prior_count, pct))

    growth.sort(key=lambda row: (row[1], row[3]), reverse=True)

    stocks = []
    for rank, (ticker, delta, prior_count, pct) in enumerate(growth[:10], start=1):
        bullish, bearish, notes = aggregate_ticker_sentiment(
            recent.sentiment_scores.get(ticker, [])
        )
        stocks.append(
            {
                "rank": rank,
                "ticker": ticker,
                "company_name": "",
                "mention_metric": f"mention increase vs prior {window_hours}h",
                "mention_value": delta,
                "mention_growth_pct": pct,
                "prior_mentions": prior_count,
                "recent_mentions": recent.mention_counts[ticker],
                "bullish_pct": bullish,
                "bearish_pct": bearish,
                "sentiment_notes": notes,
            }
        )

    return {
        "stocks": stocks,
        "sources_summary": (
            f"r/{subreddit} mention growth: last {window_hours}h vs prior {window_hours}h"
        ),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
