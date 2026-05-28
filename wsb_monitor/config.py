from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

RedditAuthMode = Literal["auto", "oauth", "public"]
ResolvedRedditAuthMode = Literal["oauth", "public"]

DEFAULT_USER_AGENT = "wsbstockmonitor:1.0 (personal/non-commercial WSB monitor)"


@dataclass(frozen=True)
class RedditSettings:
    auth_mode: ResolvedRedditAuthMode
    user_agent: str
    subreddit: str
    max_posts: int
    max_comments_per_post: int
    window_hours: int
    request_delay_sec: float
    client_id: str | None = None
    client_secret: str | None = None


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str
    model: str
    use_grounding: bool
    window_hours: int
    temperature: float = 0.0


@dataclass(frozen=True)
class AppSettings:
    output_dir: Path
    window_hours: int
    reddit: RedditSettings | None
    gemini: GeminiSettings | None


def load_window_hours() -> int:
    return int(os.getenv("WSB_WINDOW_HOURS", "48"))


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


def load_settings(*, require_reddit: bool = False, require_gemini: bool = False) -> AppSettings:
    reddit = _load_reddit_settings()
    gemini = _load_gemini_settings()

    if require_reddit and reddit is None:
        raise ValueError(
            "Reddit is required but not configured. Set REDDIT_AUTH_MODE=public "
            "(no API key) or add REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET for OAuth."
        )
    if require_gemini and gemini is None:
        raise ValueError(
            "Gemini API key required. Set GEMINI_API_KEY from https://aistudio.google.com/apikey"
        )
    if reddit is None and gemini is None:
        raise ValueError(
            "Configure at least one data source: Reddit (public or OAuth) and/or Gemini."
        )

    window_hours = load_window_hours()

    return AppSettings(
        output_dir=Path(os.getenv("WSB_OUTPUT_DIR", "data/reports")),
        window_hours=window_hours,
        reddit=reddit,
        gemini=gemini,
    )


def _load_reddit_settings() -> RedditSettings | None:
    if _env_bool("REDDIT_DISABLED"):
        return None

    mode = os.getenv("REDDIT_AUTH_MODE", "auto").strip().lower()
    if mode not in {"auto", "oauth", "public"}:
        raise ValueError("REDDIT_AUTH_MODE must be auto, oauth, or public")

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", DEFAULT_USER_AGENT)

    if mode == "oauth":
        resolved: ResolvedRedditAuthMode = "oauth"
    elif mode == "public":
        resolved = "public"
    elif client_id and client_secret:
        resolved = "oauth"
    else:
        resolved = "public"

    if resolved == "oauth":
        if not client_id or not client_secret:
            raise ValueError(
                "OAuth mode requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET."
            )
    else:
        client_id = None
        client_secret = None

    max_posts = int(os.getenv("REDDIT_MAX_POSTS", "800" if resolved == "public" else "2000"))
    max_comments = int(
        os.getenv(
            "REDDIT_MAX_COMMENTS_PER_POST",
            "0" if resolved == "public" else "30",
        )
    )

    return RedditSettings(
        auth_mode=resolved,
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        subreddit=os.getenv("REDDIT_SUBREDDIT", "wallstreetbets"),
        max_posts=max_posts,
        max_comments_per_post=max_comments,
        window_hours=load_window_hours(),
        request_delay_sec=float(os.getenv("REDDIT_REQUEST_DELAY_SEC", "2.0")),
    )


def _load_gemini_settings() -> GeminiSettings | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    return GeminiSettings(
        api_key=api_key,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        use_grounding=_env_bool("GEMINI_USE_GROUNDING"),
        window_hours=load_window_hours(),
        temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.0")),
    )
