"""Reddit scraper using the public .json endpoint — no API keys needed.

Hits reddit.com/r/{subreddit}/hot.json with rotating User-Agents.
Rate limited to 1 request per 2 seconds to avoid 429s.
Drop-in replacement for the PRAW-based RedditScraper.
"""
import random
import time
import requests
from datetime import datetime, timezone
from typing import Any, Literal

from backend.utils.logger import get_logger

logger = get_logger(__name__)

PostType = Literal["hot", "new", "rising", "top"]

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
]

_LAST_REQUEST_TIME = 0.0


def _rate_limit():
    """Enforce minimum 2 seconds between requests."""
    global _LAST_REQUEST_TIME
    elapsed = time.time() - _LAST_REQUEST_TIME
    if elapsed < 2.0:
        time.sleep(2.0 - elapsed)
    _LAST_REQUEST_TIME = time.time()


class RedditJsonScraper:
    """Scrapes Reddit via public .json endpoints. No API keys required."""

    def __init__(self):
        self.session = requests.Session()

    def scrape_posts(
        self,
        subreddit_name: str,
        limit: int = 100,
        post_type: PostType = "hot",
        time_filter: str = "day",
    ) -> list[dict[str, Any]]:
        """Fetch posts from a subreddit. Same interface as RedditScraper."""
        posts: list[dict[str, Any]] = []
        after = None
        per_page = min(limit, 100)

        while len(posts) < limit:
            _rate_limit()
            batch = self._fetch_page(subreddit_name, post_type, time_filter, per_page, after)
            if not batch:
                break

            for child in batch["data"]["children"]:
                if len(posts) >= limit:
                    break
                d = child["data"]
                if d.get("stickied"):
                    continue
                posts.append({
                    "post_id": d["id"],
                    "subreddit": subreddit_name,
                    "title": d.get("title", ""),
                    "body": d.get("selftext", ""),
                    "author": d.get("author", "[deleted]"),
                    "score": d.get("score", 0),
                    "num_comments": d.get("num_comments", 0),
                    "upvote_ratio": d.get("upvote_ratio", 0.5),
                    "is_self": d.get("is_self", True),
                    "link_flair_text": d.get("link_flair_text") or "",
                    "created_at": datetime.fromtimestamp(d["created_utc"], tz=timezone.utc),
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                })

            after = batch["data"].get("after")
            if not after:
                break

        logger.info(f"Scraped {len(posts)} posts from r/{subreddit_name} via .json")
        return posts

    def _fetch_page(self, subreddit: str, post_type: str, time_filter: str, limit: int, after: str | None) -> dict | None:
        url = f"https://www.reddit.com/r/{subreddit}/{post_type}.json"
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        if post_type == "top":
            params["t"] = time_filter

        headers = {"User-Agent": random.choice(_USER_AGENTS)}
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 429:
                retry = int(resp.headers.get("Retry-After", 5))
                logger.warning(f"Reddit 429 — sleeping {retry}s")
                time.sleep(retry)
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Reddit .json fetch failed for r/{subreddit}: {e}")
            return None
