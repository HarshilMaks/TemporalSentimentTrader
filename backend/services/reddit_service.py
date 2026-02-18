from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Literal
import asyncio
from backend.models.reddit import RedditPost
from backend.scrapers.reddit_scraper import RedditScraper, PostType
from backend.utils.ticker_extractor import extract_tickers
from backend.utils.sentiment import analyze_sentiment
from backend.utils.logger import logger
from backend.services.quality_scorer import QualityScorer


class RedditService:
    """
    Service layer for Reddit data operations.
    Handles business logic: scraping → extraction → storage.
    Targets: r/wallstreetbets, r/stocks, r/options
    """
    
    # Target subreddits for stock discussion
    DEFAULT_SUBREDDITS = ['wallstreetbets', 'stocks', 'options']
    
    def __init__(self, min_quality: int = 50):
        self.scraper = RedditScraper()
        self.quality_scorer = QualityScorer(min_quality=min_quality)
        self.min_quality = min_quality
    
    async def scrape_and_save(
        self, 
        db: AsyncSession, 
        subreddits: Optional[list[str]] = None,
        limit: int = 100,
        post_type: PostType = 'hot',
        time_filter: str = 'day'
    ) -> dict[str, int | dict[str, dict[str, int]]]:
        """
        Scrape Reddit posts from multiple subreddits using hybrid approach.
        
        Args:
            db: Database session
            subreddits: List of subreddits to scrape (defaults to wallstreetbets, stocks, options)
            limit: Number of posts to fetch per subreddit
            post_type: Type of posts ('hot', 'new', 'rising', 'top')
            time_filter: For 'top' posts ('hour', 'day', 'week', 'month', 'year', 'all')
        
        Returns:
            Dictionary with stats: saved, skipped, failed, by_subreddit
            
        Hybrid Approach:
        Phase 1: Scrape all subreddits in parallel (fast network I/O)
        Phase 2: Process and save to DB sequentially (safe transactions)
        """
        if subreddits is None:
            subreddits = self.DEFAULT_SUBREDDITS
        
        logger.info(f"Scraping {len(subreddits)} subreddits in parallel...")
        
        # ⚡ PHASE 1: PARALLEL SCRAPING (fast)
        scrape_tasks = [
            asyncio.to_thread(
                self.scraper.scrape_posts,
                subreddit, limit, post_type, time_filter
            )
            for subreddit in subreddits
        ]
        
        scrape_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
        
        # Map results to subreddits
        all_posts = {}
        for subreddit, result in zip(subreddits, scrape_results):
            if isinstance(result, Exception):
                logger.error(f"Failed to scrape r/{subreddit}: {result}")
                all_posts[subreddit] = []
            else:
                all_posts[subreddit] = result
                logger.info(f"Fetched {len(result)} posts from r/{subreddit}")
        
        # 🔒 PHASE 2: SEQUENTIAL PROCESSING & SAVING (safe)
        total_saved = 0
        total_skipped = 0
        total_failed = 0
        total_fetched = 0
        subreddit_stats = {}
        
        # Enhanced tracking of skip reasons
        skip_reasons = {
            'no_tickers': 0,
            'duplicate': 0,
            'low_quality': 0,
            'other': 0
        }
        
        for subreddit in subreddits:
            posts = all_posts.get(subreddit, [])
            saved_count = 0
            skipped_count = 0
            failed_count = 0
            
            # Per-subreddit skip tracking
            sub_skip_reasons = {
                'no_tickers': 0,
                'duplicate': 0,
                'low_quality': 0,
                'other': 0
            }
            
            for post_data in posts:
                try:
                    # Extract tickers from title + body
                    text = f"{post_data['title']} {post_data['body']}"
                    tickers = extract_tickers(text)
                    
                    # Skip posts with no stock mentions
                    if not tickers:
                        skipped_count += 1
                        sub_skip_reasons['no_tickers'] += 1
                        skip_reasons['no_tickers'] += 1
                        continue
                    
                    # Check if post already exists (avoid duplicates)
                    result = await db.execute(
                        select(RedditPost).where(RedditPost.post_id == post_data['post_id'])
                    )
                    if result.scalar_one_or_none():
                        skipped_count += 1
                        sub_skip_reasons['duplicate'] += 1
                        skip_reasons['duplicate'] += 1
                        continue
                    
                    # Score post quality before processing
                    quality_result = self.quality_scorer.score_post(
                        title=post_data['title'],
                        body=post_data['body'],
                        upvotes=post_data['score'],
                        downvotes=int(post_data['score'] * (1 - post_data.get('upvote_ratio', 0.5))),
                        comment_count=post_data['num_comments'],
                        upvote_ratio=post_data.get('upvote_ratio', 0.5),
                        created_at=post_data['created_at']
                    )
                    
                    # Skip low-quality posts
                    if not quality_result.is_quality:
                        logger.debug(
                            f"Skipping low-quality post {post_data['post_id']} "
                            f"(score: {quality_result.overall_score}, tier: {quality_result.quality_tier}). "
                            f"Flags: {quality_result.flags}"
                        )
                        skipped_count += 1
                        sub_skip_reasons['low_quality'] += 1
                        skip_reasons['low_quality'] += 1
                        continue
                    
                    # Calculate sentiment score
                    sentiment_score = analyze_sentiment(text)
                    
                    # Create database record with enhanced metadata
                    db_post = RedditPost(
                        post_id=post_data['post_id'],
                        subreddit=post_data['subreddit'],
                        title=post_data['title'],
                        body=post_data['body'],
                        author=post_data['author'],
                        score=post_data['score'],
                        num_comments=post_data['num_comments'],
                        upvote_ratio=post_data.get('upvote_ratio', 0.0),  # NEW
                        is_self=post_data.get('is_self', True),  # NEW
                        link_flair_text=post_data.get('link_flair_text', ''),  # NEW
                        tickers=tickers,
                        sentiment_score=sentiment_score,
                        quality_score=quality_result.overall_score,  # NEW
                        quality_tier=quality_result.quality_tier,  # NEW
                        is_quality=quality_result.is_quality,  # NEW: Mark as quality post
                        created_at=post_data['created_at'],
                        url=post_data['url']
                    )
                    
                    db.add(db_post)
                    saved_count += 1
                    
                except Exception as e:
                    print(f"Error processing post {post_data.get('post_id')}: {e}")
                    failed_count += 1
                    continue
            
            # Commit per subreddit (transaction boundary)
            try:
                await db.commit()
                logger.info(f"r/{subreddit}: {saved_count} saved, {skipped_count} skipped, {failed_count} failed")
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to commit r/{subreddit}: {e}")
            
            # Track stats per subreddit
            subreddit_stats[subreddit] = {
                'saved': saved_count,
                'skipped': skipped_count,
                'failed': failed_count,
                'fetched': len(posts),
                'skip_reasons': {
                    'no_tickers': sub_skip_reasons['no_tickers'],
                    'duplicate': sub_skip_reasons['duplicate'],
                    'low_quality': sub_skip_reasons['low_quality'],
                    'other': sub_skip_reasons['other']
                }
            }
            
            total_saved += saved_count
            total_skipped += skipped_count
            total_failed += failed_count
            total_fetched += len(posts)
        
        return {
            'saved': total_saved,
            'skipped': total_skipped,
            'failed': total_failed,
            'total_fetched': total_fetched,
            'quality_threshold': self.min_quality,
            'skip_reasons': skip_reasons,
            'acceptance_rate': (total_saved / total_fetched * 100) if total_fetched > 0 else 0,
            'by_subreddit': subreddit_stats
        }
    
    async def get_quality_analytics(
        self,
        db: AsyncSession,
        hours: int = 24,
        quality_threshold: Optional[int] = None
    ) -> dict:
        """
        Get quality analytics for posts within a time window.
        
        Args:
            db: Database session
            hours: Time window in hours (default 24)
            quality_threshold: Optional quality filter (default: self.min_quality)
        
        Returns:
            Dictionary with analytics:
            - total: Total post count
            - avg_quality: Average quality score
            - high_quality_pct: % of posts with quality >= threshold
            - low_quality_pct: % of posts with quality < threshold
            - quality_distribution: Count by tier (poor/fair/good/excellent)
        """
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func, case
        
        threshold = quality_threshold if quality_threshold is not None else self.min_quality
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Get aggregate stats
        result = await db.execute(
            select(
                func.count(RedditPost.id).label('total'),
                func.avg(RedditPost.quality_score).label('avg_quality'),
                func.sum(case((RedditPost.quality_score >= threshold, 1), else_=0)).label('high_quality_count'),
                func.sum(case((RedditPost.quality_score < threshold, 1), else_=0)).label('low_quality_count')
            ).where(RedditPost.created_at >= cutoff_time)
        )
        
        row = result.first()
        total = row.total or 0
        avg_quality = float(row.avg_quality) if row.avg_quality else 0.0
        high_quality_count = row.high_quality_count or 0
        low_quality_count = row.low_quality_count or 0
        
        # Get quality distribution by tier
        tier_result = await db.execute(
            select(
                RedditPost.quality_tier,
                func.count(RedditPost.id).label('count')
            )
            .where(RedditPost.created_at >= cutoff_time)
            .group_by(RedditPost.quality_tier)
        )
        
        tier_rows = tier_result.all()
        quality_distribution = {tier: count for tier, count in tier_rows}
        
        # Ensure all tiers are present
        for tier in ['poor', 'fair', 'good', 'excellent']:
            if tier not in quality_distribution:
                quality_distribution[tier] = 0
        
        return {
            'total': total,
            'avg_quality': round(avg_quality, 2),
            'high_quality_pct': round((high_quality_count / total * 100) if total > 0 else 0, 2),
            'low_quality_pct': round((low_quality_count / total * 100) if total > 0 else 0, 2),
            'quality_distribution': quality_distribution,
            'quality_threshold': threshold,
            'time_window_hours': hours
        }
