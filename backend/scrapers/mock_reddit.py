"""Mock Reddit scraper for development without API credentials.

Generates realistic-looking posts with varied sentiment for watchlist tickers.
Drop-in replacement for RedditScraper — same interface, no PRAW needed.
"""
from datetime import datetime, timedelta, timezone
import random
from typing import Any, Literal

PostType = Literal['hot', 'new', 'rising', 'top']

# Templates: (title_template, sentiment_bias)  — bias shifts random sentiment
_BULLISH = [
    "{ticker} earnings crushed estimates, guidance raised 🚀",
    "Why {ticker} is my biggest position right now",
    "{ticker} insider buying is through the roof lately",
    "Institutional accumulation on {ticker} — smart money loading",
    "{ticker} breakout above resistance, volume confirming",
    "DD: {ticker} is massively undervalued at these levels",
    "{ticker} short interest dropping fast — bears capitulating",
]

_BEARISH = [
    "{ticker} is overvalued at current levels, change my mind",
    "Why I sold all my {ticker} shares today",
    "{ticker} guidance was terrible, expecting more downside",
    "Insider selling on {ticker} — CEO dumped shares",
    "{ticker} losing market share fast, bearish outlook",
    "Technical breakdown on {ticker}, support failed",
]

_NEUTRAL = [
    "What's everyone's take on {ticker} at this price?",
    "{ticker} earnings next week — what are you expecting?",
    "Holding {ticker} long term, anyone else?",
    "Is {ticker} a buy at these levels or wait for a dip?",
    "{ticker} consolidating — could go either way",
]

_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "AMD", "NFLX", "DIS",
    "BABA", "INTC", "CSCO", "ADBE", "PYPL",
    "CRM", "ORCL", "UBER", "SPOT", "SQ",
]


class MockRedditScraper:
    """Generates synthetic Reddit posts for testing without API credentials."""

    def scrape_posts(
        self,
        subreddit_name: str,
        limit: int = 100,
        post_type: PostType = 'hot',
        time_filter: str = 'day',
    ) -> list[dict[str, Any]]:
        posts = []
        now = datetime.now(timezone.utc)

        for i in range(limit):
            ticker = random.choice(_TICKERS)
            roll = random.random()
            if roll < 0.45:
                template = random.choice(_BULLISH)
            elif roll < 0.75:
                template = random.choice(_NEUTRAL)
            else:
                template = random.choice(_BEARISH)

            title = template.format(ticker=ticker)
            score = random.randint(5, 8000)
            upvote_ratio = round(random.uniform(0.55, 0.98), 2)

            posts.append({
                'post_id': f'mock_{subreddit_name}_{i}_{random.randint(1000, 9999)}',
                'subreddit': subreddit_name,
                'title': title,
                'body': f'Position: 100 shares of ${ticker}. Been watching the charts and fundamentals.',
                'author': f'trader_{random.randint(100, 9999)}',
                'score': score,
                'num_comments': random.randint(3, 500),
                'upvote_ratio': upvote_ratio,
                'is_self': True,
                'link_flair_text': random.choice(['DD', 'Discussion', 'Technical Analysis', 'YOLO', '']),
                'created_at': now - timedelta(hours=random.randint(1, 48)),
                'url': f'https://reddit.com/r/{subreddit_name}/comments/mock_{i}',
            })

        return posts
