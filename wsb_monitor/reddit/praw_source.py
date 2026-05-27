from __future__ import annotations

from typing import Any, Iterator

import praw

from wsb_monitor.config import RedditSettings


def iter_posts(settings: RedditSettings, prior_cutoff: float) -> Iterator[tuple[float, list[str]]]:
    reddit = praw.Reddit(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        user_agent=settings.user_agent,
    )
    subreddit = reddit.subreddit(settings.subreddit)

    for submission in subreddit.new(limit=None):
        if submission.created_utc < prior_cutoff:
            break

        texts = [f"{submission.title}\n{submission.selftext or ''}"]
        texts.extend(_comment_texts(submission, settings.max_comments_per_post))
        yield submission.created_utc, texts


def _comment_texts(submission: Any, max_comments: int) -> list[str]:
    if max_comments <= 0:
        return []

    submission.comments.replace_more(limit=0)
    texts: list[str] = []
    for comment in submission.comments.list()[:max_comments]:
        if getattr(comment, "body", None):
            texts.append(comment.body)
    return texts
