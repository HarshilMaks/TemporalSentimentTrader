"""
Maintenance tasks for data cleanup and system health.

These tasks run on schedule to:
1. Clean up old data (>90 days) to manage DB size
2. Refresh cache for frequently accessed data
3. Generate system health reports
"""
import asyncio
from datetime import datetime, timedelta, timezone
from celery import shared_task
from sqlalchemy import delete, select, func
from backend.database.config import AsyncSessionLocal
from backend.utils.logger import logger


@shared_task(
    name="backend.tasks.maintenance_tasks.cleanup_old_data",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def cleanup_old_data(self, retention_days: int = 90):
    """
    Clean up data older than retention period.
    
    Removes:
    - Reddit posts older than 90 days
    - Stock prices older than 90 days (keeps history manageable)
    - Closed trading signals older than 90 days
    
    Run: Weekly (Sunday 3 AM UTC)
    
    Args:
        retention_days: Number of days to keep (default 90)
    
    Returns:
        Dict with deletion counts
    """
    async def _cleanup():
        from backend.models.reddit import RedditPost
        from backend.models.stock import StockPrice
        from backend.models.prediction import TradingSignal
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        results = {
            "posts_deleted": 0,
            "prices_deleted": 0,
            "signals_deleted": 0,
            "cutoff_date": cutoff.isoformat(),
        }
        
        async with AsyncSessionLocal() as db:
            try:
                # Delete old Reddit posts
                result = await db.execute(
                    delete(RedditPost).where(RedditPost.created_at < cutoff)
                )
                results["posts_deleted"] = result.rowcount
                
                # Delete old stock prices
                result = await db.execute(
                    delete(StockPrice).where(StockPrice.date < cutoff)
                )
                results["prices_deleted"] = result.rowcount
                
                # Delete old closed signals (keep active ones)
                result = await db.execute(
                    delete(TradingSignal).where(
                        TradingSignal.created_at < cutoff,
                        TradingSignal.status.in_(["closed", "expired", "stopped"])
                    )
                )
                results["signals_deleted"] = result.rowcount
                
                await db.commit()
                
                logger.info(
                    f"🧹 Cleanup completed: {results['posts_deleted']} posts, "
                    f"{results['prices_deleted']} prices, {results['signals_deleted']} signals"
                )
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Cleanup failed: {e}")
                raise
        
        return results
    
    try:
        return asyncio.run(_cleanup())
    except Exception as e:
        logger.error(f"Maintenance task failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="backend.tasks.maintenance_tasks.generate_system_report",
    bind=True,
)
def generate_system_report(self):
    """
    Generate daily system health report.
    
    Collects:
    - Database record counts
    - Data freshness metrics
    - Cache hit rates
    - Task success rates
    
    Run: Daily at 6 AM UTC
    
    Returns:
        Dict with system metrics
    """
    async def _report():
        from backend.models.reddit import RedditPost
        from backend.models.stock import StockPrice
        from backend.models.prediction import TradingSignal
        
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": {},
            "data_freshness": {},
        }
        
        async with AsyncSessionLocal() as db:
            # Database counts
            report["database"]["reddit_posts"] = (
                await db.execute(select(func.count()).select_from(RedditPost))
            ).scalar_one()
            
            report["database"]["stock_prices"] = (
                await db.execute(select(func.count()).select_from(StockPrice))
            ).scalar_one()
            
            report["database"]["trading_signals"] = (
                await db.execute(select(func.count()).select_from(TradingSignal))
            ).scalar_one()
            
            # Data freshness (most recent record)
            latest_post = (
                await db.execute(
                    select(func.max(RedditPost.created_at))
                )
            ).scalar_one()
            
            latest_price = (
                await db.execute(
                    select(func.max(StockPrice.date))
                )
            ).scalar_one()
            
            now = datetime.now(timezone.utc)
            
            if latest_post:
                # Handle timezone-naive datetime from DB
                if latest_post.tzinfo is None:
                    latest_post = latest_post.replace(tzinfo=timezone.utc)
                hours_since_post = (now - latest_post).total_seconds() / 3600
                report["data_freshness"]["reddit_hours_ago"] = round(hours_since_post, 2)
            
            if latest_price:
                if latest_price.tzinfo is None:
                    latest_price = latest_price.replace(tzinfo=timezone.utc)
                hours_since_price = (now - latest_price).total_seconds() / 3600
                report["data_freshness"]["stocks_hours_ago"] = round(hours_since_price, 2)
        
        logger.info(f"📊 System report: {report['database']}")
        return report
    
    return asyncio.run(_report())


@shared_task(
    name="backend.tasks.maintenance_tasks.refresh_trending_cache",
    bind=True,
)
def refresh_trending_cache(self):
    """
    Pre-compute and cache trending tickers.
    
    This task pre-warms the cache with trending data
    so API requests get instant responses.
    
    Run: Every 10 minutes
    
    Returns:
        Dict with cache refresh status
    """
    async def _refresh():
        from backend.models.reddit import RedditPost
        from backend.cache.redis_client import get_redis, CacheKeys
        from sqlalchemy import func
        from collections import Counter
        
        result = {
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "tickers_cached": 0,
            "cache_status": "failed",
        }
        
        async with AsyncSessionLocal() as db:
            # Get posts from last 7 days
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
            posts = (
                await db.execute(
                    select(RedditPost.tickers)
                    .where(RedditPost.created_at >= cutoff)
                )
            ).scalars().all()
            
            # Count ticker mentions
            ticker_counts = Counter()
            for tickers in posts:
                if tickers:
                    ticker_counts.update(tickers)
            
            # Get top 20
            trending = [
                {"ticker": ticker, "mentions": count}
                for ticker, count in ticker_counts.most_common(20)
            ]
            
            # Cache it
            cache = await get_redis()
            if cache.is_connected:
                await cache.set_trending(trending)
                result["tickers_cached"] = len(trending)
                result["cache_status"] = "success"
                logger.info(f"🔥 Cached {len(trending)} trending tickers")
            else:
                result["cache_status"] = "cache_unavailable"
        
        return result
    
    return asyncio.run(_refresh())
