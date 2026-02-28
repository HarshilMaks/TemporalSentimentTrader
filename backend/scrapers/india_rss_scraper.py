"""India market hype/sentiment scraper via RSS feeds.

Sources: Yahoo Finance India, Moneycontrol, Economic Times Markets.
Zero credentials needed — pure RSS via feedparser.
"""
import re
import time
import feedparser
from datetime import datetime, timezone
from typing import Any

from backend.utils.logger import get_logger
from backend.utils.sentiment import analyze_sentiment

logger = get_logger(__name__)

# NSE tickers we track — top Nifty 50 names
INDIA_WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN",
    "SUNPHARMA", "BAJFINANCE", "WIPRO", "HCLTECH", "ULTRACEMCO",
    "NESTLEIND", "TATAMOTORS", "TATASTEEL", "POWERGRID", "NTPC",
    "ONGC", "JSWSTEEL", "ADANIENT", "ADANIPORTS", "TECHM",
]

# RSS feeds — free, no auth
_FEEDS = [
    "https://feeds.feedburner.com/NDTV-LatestNews",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://www.moneycontrol.com/rss/results.xml",
    "https://finance.yahoo.com/news/rssindex",
]

# Map common company names → NSE ticker
_NAME_TO_TICKER = {
    "reliance": "RELIANCE", "ril": "RELIANCE", "jio": "RELIANCE",
    "tcs": "TCS", "tata consultancy": "TCS",
    "hdfc bank": "HDFCBANK", "hdfc": "HDFCBANK",
    "infosys": "INFY", "infy": "INFY",
    "icici bank": "ICICIBANK", "icici": "ICICIBANK",
    "hindustan unilever": "HINDUNILVR", "hul": "HINDUNILVR",
    "itc": "ITC",
    "sbi": "SBIN", "state bank": "SBIN",
    "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL",
    "kotak": "KOTAKBANK", "kotak mahindra": "KOTAKBANK",
    "larsen": "LT", "l&t": "LT",
    "axis bank": "AXISBANK", "axis": "AXISBANK",
    "asian paints": "ASIANPAINT",
    "maruti": "MARUTI", "maruti suzuki": "MARUTI",
    "titan": "TITAN",
    "sun pharma": "SUNPHARMA", "sun pharmaceutical": "SUNPHARMA",
    "bajaj finance": "BAJFINANCE", "bajaj finserv": "BAJFINANCE",
    "wipro": "WIPRO",
    "hcl tech": "HCLTECH", "hcl technologies": "HCLTECH",
    "ultratech": "ULTRACEMCO", "ultratech cement": "ULTRACEMCO",
    "nestle": "NESTLEIND", "nestle india": "NESTLEIND",
    "tata motors": "TATAMOTORS",
    "tata steel": "TATASTEEL",
    "power grid": "POWERGRID",
    "ntpc": "NTPC",
    "ongc": "ONGC",
    "jsw steel": "JSWSTEEL", "jsw": "JSWSTEEL",
    "adani enterprises": "ADANIENT", "adani": "ADANIENT",
    "adani ports": "ADANIPORTS",
    "tech mahindra": "TECHM",
    "nifty": None, "sensex": None,  # index mentions — skip
}

_TICKER_PATTERN = re.compile(r"\b(" + "|".join(re.escape(t) for t in INDIA_WATCHLIST) + r")\b")


def _short_id(raw: str) -> str:
    """Create a stable short ID (max 50 chars) from a URL or entry ID."""
    import hashlib
    return "rss_" + hashlib.md5(raw.encode()).hexdigest()[:46]


def _extract_india_tickers(text: str) -> list[str]:
    """Extract NSE tickers from text via direct match + company name mapping."""
    found = set()
    text_lower = text.lower()

    # Direct ticker match (e.g. "RELIANCE", "TCS")
    for m in _TICKER_PATTERN.finditer(text):
        found.add(m.group(1))

    # Company name match
    for name, ticker in _NAME_TO_TICKER.items():
        if ticker and name in text_lower:
            found.add(ticker)

    return sorted(found)


class IndiaRssScraper:
    """Scrapes Indian financial RSS feeds for market sentiment."""

    def scrape_feeds(self, max_entries: int = 200) -> list[dict[str, Any]]:
        """Fetch and parse all RSS feeds, extract ticker mentions + sentiment.

        Returns list of dicts matching RedditPost-compatible schema:
        post_id, subreddit (=source), title, body, sentiment_score, tickers, etc.
        """
        articles: list[dict[str, Any]] = []

        for feed_url in _FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                source = feed.feed.get("title", feed_url)[:50]

                for entry in feed.entries[:50]:  # cap per feed
                    title = entry.get("title", "")
                    body = entry.get("summary", "")
                    text = f"{title} {body}"

                    tickers = _extract_india_tickers(text)
                    if not tickers:
                        continue

                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                    articles.append({
                        "post_id": _short_id(entry.get("id") or entry.get("link", "")),
                        "subreddit": f"rss:{source}",
                        "title": title,
                        "body": body[:2000],
                        "author": entry.get("author", source),
                        "score": 0,
                        "num_comments": 0,
                        "upvote_ratio": 0.5,
                        "is_self": True,
                        "link_flair_text": "India RSS",
                        "created_at": published or datetime.now(timezone.utc),
                        "url": entry.get("link", ""),
                        "tickers": tickers,
                        "sentiment_score": analyze_sentiment(text),
                    })

                    if len(articles) >= max_entries:
                        break

                logger.info(f"RSS: {len(feed.entries)} entries from {source}")
                time.sleep(0.5)  # polite delay between feeds

            except Exception as e:
                logger.error(f"RSS feed failed ({feed_url}): {e}")
                continue

        logger.info(f"India RSS: {len(articles)} articles with ticker mentions")
        return articles
