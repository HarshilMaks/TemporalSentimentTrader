"""Reddit + India RSS service layer.

Scrapes real data only — no mocks. Uses:
- Reddit .json backdoor (US hype) — zero API keys
- India RSS feeds (India hype) — zero credentials
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Literal
import asyncio

from backend.models.reddit import RedditPost
from backend.scrapers.reddit_json_scraper import RedditJsonScraper
from backend.scrapers.india_rss_scraper import IndiaRssScraper
from backend.utils.ticker_extractor import extract_tickers
from backend.utils.sentiment import analyze_sentiment
from backend.utils.logger import logger
from backend.services.quality_scorer import QualityScorer

PostType = Literal['hot', 'new', 'rising', 'top']


class RedditService:
    """Scrapes Reddit (US) + RSS (India) and stores to DB.

    No API keys needed. No mocks. Real data only.
    """

    DEFAULT_SUBREDDITS = ['wallstreetbets', 'stocks', 'options']

    def __init__(self, min_quality: int = 50):
        self.scraper = RedditJsonScraper()
        self.india_scraper = IndiaRssScraper()
        self.quality_scorer = QualityScorer(min_quality=min_quality)
        self.min_quality = min_quality
        self.using_mock = False  # kept for backward compat — always False now

    async def scrape_and_save(
        self,
        db: AsyncSession,
        subreddits: Optional[list[str]] = None,
        limit: int = 100,
        post_type: PostType = 'hot',
        time_filter: str = 'day',
        include_india: bool = True,
    ) -> dict:
        """Scrape Reddit + India RSS, extract tickers/sentiment, save to DB."""
        if subreddits is None:
            subreddits = self.DEFAULT_SUBREDDITS

        # Phase 1: Parallel scraping
        scrape_tasks = [
            asyncio.to_thread(self.scraper.scrape_posts, sub, limit, post_type, time_filter)
            for sub in subreddits
        ]
        if include_india:
            scrape_tasks.append(asyncio.to_thread(self.india_scraper.scrape_feeds, 200))

        results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

        # Collect all posts
        all_posts: list[dict] = []
        for i, sub in enumerate(subreddits):
            r = results[i]
            if isinstance(r, Exception):
                logger.error(f"Failed to scrape r/{sub}: {r}")
            else:
                all_posts.extend(r)

        # India RSS results (already have tickers + sentiment pre-computed)
        india_posts: list[dict] = []
        if include_india and len(results) > len(subreddits):
            r = results[-1]
            if isinstance(r, Exception):
                logger.error(f"India RSS failed: {r}")
            else:
                india_posts = r

        # Phase 2: Process and save
        saved, skipped, failed = 0, 0, 0
        skip_reasons = {'no_tickers': 0, 'duplicate': 0, 'low_quality': 0}

        # Process Reddit posts (need ticker extraction + sentiment)
        for post in all_posts:
            result = await self._process_and_save(db, post, extract=True, skip_reasons=skip_reasons)
            if result == 'saved':
                saved += 1
            elif result == 'skipped':
                skipped += 1
            else:
                failed += 1

        # Process India RSS posts (tickers + sentiment already computed)
        for post in india_posts:
            result = await self._process_and_save(db, post, extract=False, skip_reasons=skip_reasons)
            if result == 'saved':
                saved += 1
            elif result == 'skipped':
                skipped += 1
            else:
                failed += 1

        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Commit failed: {e}")

        total = saved + skipped + failed
        logger.info(f"Hype layer: {saved} saved, {skipped} skipped, {failed} failed (Reddit: {len(all_posts)}, India RSS: {len(india_posts)})")

        return {
            'saved': saved,
            'skipped': skipped,
            'failed': failed,
            'total_fetched': total,
            'quality_threshold': self.min_quality,
            'skip_reasons': skip_reasons,
            'acceptance_rate': (saved / total * 100) if total > 0 else 0,
        }

    async def _process_and_save(self, db: AsyncSession, post: dict, extract: bool, skip_reasons: dict) -> str:
        """Process a single post and save to DB. Returns 'saved', 'skipped', or 'failed'."""
        try:
            # Extract tickers + sentiment if not pre-computed (Reddit posts)
            if extract:
                text = f"{post['title']} {post.get('body', '')}"
                tickers = extract_tickers(text)
                if not tickers:
                    skip_reasons['no_tickers'] += 1
                    return 'skipped'
                sentiment = analyze_sentiment(text)
            else:
                tickers = post.get('tickers', [])
                sentiment = post.get('sentiment_score', 0.0)
                if not tickers:
                    skip_reasons['no_tickers'] += 1
                    return 'skipped'

            # Dedup
            exists = (await db.execute(
                select(RedditPost.id).where(RedditPost.post_id == post['post_id'])
            )).first()
            if exists:
                skip_reasons['duplicate'] += 1
                return 'skipped'

            # Quality scoring — skip for RSS (professional news sources)
            is_rss = post.get('subreddit', '').startswith('rss:')
            if is_rss:
                quality_score, quality_tier, is_quality = 75.0, 'good', True
            else:
                quality = self.quality_scorer.score_post(
                    title=post['title'],
                    body=post.get('body', ''),
                    upvotes=post.get('score', 0),
                    downvotes=int(post.get('score', 0) * (1 - post.get('upvote_ratio', 0.5))),
                    comment_count=post.get('num_comments', 0),
                    upvote_ratio=post.get('upvote_ratio', 0.5),
                    created_at=post.get('created_at'),
                )
                if not quality.is_quality:
                    skip_reasons['low_quality'] += 1
                    return 'skipped'
                quality_score, quality_tier, is_quality = quality.overall_score, quality.quality_tier, quality.is_quality

            db.add(RedditPost(
                post_id=post['post_id'],
                subreddit=post.get('subreddit', ''),
                title=post['title'],
                body=post.get('body', ''),
                author=post.get('author', ''),
                score=post.get('score', 0),
                num_comments=post.get('num_comments', 0),
                upvote_ratio=post.get('upvote_ratio', 0.0),
                is_self=post.get('is_self', True),
                link_flair_text=post.get('link_flair_text', ''),
                tickers=tickers,
                sentiment_score=sentiment,
                quality_score=quality_score,
                quality_tier=quality_tier,
                is_quality=is_quality,
                created_at=post.get('created_at'),
                url=post.get('url', ''),
            ))
            return 'saved'

        except Exception as e:
            logger.error(f"Error processing post {post.get('post_id')}: {e}")
            return 'failed'

    async def get_quality_analytics(self, db: AsyncSession, hours: int = 24, quality_threshold: Optional[int] = None) -> dict:
        """Get quality analytics for posts within a time window."""
        from datetime import timedelta
        from sqlalchemy import func, case

        threshold = quality_threshold or self.min_quality
        cutoff = __import__('datetime').datetime.now(__import__('datetime').timezone.utc) - timedelta(hours=hours)

        result = await db.execute(
            select(
                func.count(RedditPost.id).label('total'),
                func.avg(RedditPost.quality_score).label('avg_quality'),
                func.sum(case((RedditPost.quality_score >= threshold, 1), else_=0)).label('high'),
                func.sum(case((RedditPost.quality_score < threshold, 1), else_=0)).label('low'),
            ).where(RedditPost.created_at >= cutoff)
        )
        row = result.first()
        total = row.total or 0

        tier_result = await db.execute(
            select(RedditPost.quality_tier, func.count(RedditPost.id))
            .where(RedditPost.created_at >= cutoff)
            .group_by(RedditPost.quality_tier)
        )
        dist = {tier: cnt for tier, cnt in tier_result.all()}
        for t in ['poor', 'fair', 'good', 'excellent']:
            dist.setdefault(t, 0)

        return {
            'total': total,
            'avg_quality': round(float(row.avg_quality or 0), 2),
            'high_quality_pct': round((row.high or 0) / total * 100, 2) if total else 0,
            'low_quality_pct': round((row.low or 0) / total * 100, 2) if total else 0,
            'quality_distribution': dist,
            'quality_threshold': threshold,
            'time_window_hours': hours,
        }
