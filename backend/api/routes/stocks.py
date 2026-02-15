from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from backend.models.stock import StockPrice
from backend.services.stock_service import StockService
from backend.database.config import get_db
from backend.cache.redis_client import RedisCache, get_redis
from backend.utils.logger import logger
from backend.api.middleware.rate_limit import check_rate_limit
from backend.config.rate_limits import RATE_LIMITS, get_period_seconds

router = APIRouter(prefix="/stocks", tags=["stocks"])


# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMIT DEPENDENCY FUNCTIONS (Stocks Endpoints)
# ═══════════════════════════════════════════════════════════════════════════════


async def rate_limit_stocks_fetch(request: Request):
    """
    Rate limit: POST /stocks/fetch/{ticker}
    
    Limit: 20 requests per minute per IP
    
    Rationale:
    - Calls external API (yfinance)
    - Network latency involved
    - Moderate resource usage
    - Not critical for real-time updates
    
    Cost: 🟠 MEDIUM-HIGH (external API)
    """
    config = RATE_LIMITS["stocks:fetch"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="stocks:fetch",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_stocks_prices(request: Request):
    """
    Rate limit: GET /stocks/prices/{ticker}
    
    Limit: 100 requests per minute per IP
    
    Rationale:
    - Reads from database with date range filter
    - Indexed query (ticker, date)
    - Fast query, no external dependencies
    - Users frequently query historical prices
    
    Cost: 🟢 LOW (indexed reads)
    """
    config = RATE_LIMITS["stocks:prices"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="stocks:prices",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_stocks_latest(request: Request):
    """
    Rate limit: GET /stocks/latest/{ticker}
    
    Limit: 200 requests per minute per IP (HIGHEST!)
    
    Rationale:
    - Cached for 5 minutes in Redis
    - Hits cache 99% of the time (Redis is O(1))
    - Database hit maybe once per 5 minutes, rest from cache
    - Very cheap operation
    
    Cost: 🟢 VERY LOW (cached)
    """
    config = RATE_LIMITS["stocks:latest"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="stocks:latest",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_stocks_signals(request: Request):
    """
    Rate limit: GET /stocks/signals/{ticker}
    
    Limit: 100 requests per minute per IP
    
    Rationale:
    - Cached for 5 minutes
    - Calculations (RSI, MACD, SMA) done once, cached
    - Most requests hit cache
    - Medium cost vs latest (more calculations)
    
    Cost: 🟢 LOW (cached)
    """
    config = RATE_LIMITS["stocks:signals"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="stocks:signals",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_stocks_health(request: Request):
    """
    Rate limit: GET /stocks/health
    
    Limit: 30 requests per minute per IP
    
    Rationale:
    - COUNT(*) on large table (expensive scan)
    - COUNT(DISTINCT) also expensive
    - Not meant to be called frequently by users
    - Mostly for monitoring/dashboards
    
    Cost: 🟡 MEDIUM (aggregation)
    """
    config = RATE_LIMITS["stocks:health"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="stocks:health",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_tasks_fetch_trending(request: Request):
    """
    Rate limit: POST /stocks/tasks/fetch-trending
    
    Limit: 5 requests per hour per IP
    
    Rationale:
    - Triggers Celery background job
    - Job calls external APIs (Reddit, yfinance) multiple times
    - Expensive operation, runs in background
    - No need to call frequently
    
    Cost: 🔴 HIGH (external APIs + background job)
    """
    config = RATE_LIMITS["tasks:fetch_trending"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="tasks:fetch_trending",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_tasks_fetch_single(request: Request):
    """
    Rate limit: POST /stocks/tasks/fetch-single/{ticker}
    
    Limit: 10 requests per hour per IP
    
    Rationale:
    - Triggers external API call (yfinance)
    - Background job, resource intensive
    - Higher than trending (single call vs batch)
    - But still should be infrequent
    
    Cost: 🔴 HIGH (external API)
    """
    config = RATE_LIMITS["tasks:fetch_single"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="tasks:fetch_single",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_tasks_cleanup(request: Request):
    """
    Rate limit: POST /stocks/tasks/cleanup
    
    Limit: 2 requests per day per IP
    
    Rationale:
    - DELETE operations on database
    - Locks affected rows/tables
    - Destructive operation
    - Only needs to run once per day
    - Should never be called by users more than a few times
    
    Cost: 🔴 VERY HIGH (destructive)
    """
    config = RATE_LIMITS["tasks:cleanup"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="tasks:cleanup",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_tasks_status(request: Request):
    """
    Rate limit: GET /stocks/tasks/{task_id}
    
    Limit: 50 requests per minute per IP
    
    Rationale:
    - Read-only status check
    - Hits Celery's AsyncResult (cheap lookup)
    - Users frequently poll for job status
    - No side effects, relatively cheap
    
    Cost: 🟢 LOW (lookup)
    """
    config = RATE_LIMITS["tasks:status"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="tasks:status",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_cache_stats(request: Request):
    """
    Rate limit: GET /stocks/cache/stats
    
    Limit: 100 requests per minute per IP
    
    Rationale:
    - Redis INFO command (O(1))
    - Monitoring endpoint
    - Very cheap operation
    - Users might poll frequently
    
    Cost: 🟢 VERY LOW (Redis O(1))
    """
    config = RATE_LIMITS["cache:stats"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="cache:stats",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_cache_invalidate(request: Request):
    """
    Rate limit: DELETE /stocks/cache/{ticker}
    
    Limit: 20 requests per minute per IP
    
    Rationale:
    - Redis DELETE operation (cheap)
    - But deletion is destructive (clears cache)
    - Lower than stats because it modifies state
    - Shouldn't need to call often
    
    Cost: 🟡 LOW (delete)
    """
    config = RATE_LIMITS["cache:invalidate"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="cache:invalidate",
        limit=config.requests,
        period_seconds=period_seconds
    )



@router.post("/fetch/{ticker}", status_code=status.HTTP_200_OK)
async def fetch_stock_data(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    period: str = Query("3mo", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$"),
    _rate_limit = Depends(rate_limit_stocks_fetch)  # ← Rate limit check (20/minute)
) -> Dict[str, Any]:
    """
    Manually trigger stock data fetch with momentum indicators.
    
    Rate limited: 20 requests per minute per IP
    
    Args:
        ticker: Stock symbol (e.g., AAPL, TSLA)
        period: Historical period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
    
    Returns:
        Stats: saved, skipped, errors
    """
    logger.info(f"API fetch triggered for {ticker}")
    
    service = StockService()
    result = await service.fetch_and_save_stock_data(ticker.upper(), db, period)
    
    if result['errors'] > 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch data for {ticker}"
        )
    
    return {
        "success": True,
        "ticker": ticker.upper(),
        "stats": result
    }


@router.post("/fetch/batch", status_code=status.HTTP_200_OK)
async def fetch_multiple_stocks(
    tickers: List[str],
    db: AsyncSession = Depends(get_db),
    period: str = Query("3mo", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$"),
    _rate_limit = Depends(rate_limit_stocks_fetch)  # ← Rate limit check (20/minute)
) -> Dict[str, Any]:
    """
    Fetch multiple tickers in parallel using hybrid optimization.
    
    Args:
        tickers: List of stock symbols (max 50)
        period: Historical period
    
    Returns:
        Results for each ticker with stats
    """
    if len(tickers) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 tickers per request"
        )
    
    if not tickers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tickers list cannot be empty"
        )
    
    logger.info(f"Batch fetch triggered for {len(tickers)} tickers")
    
    service = StockService()
    results = await service.fetch_and_save_multiple(
        [t.upper() for t in tickers],
        db,
        period
    )
    
    success_count = sum(1 for r in results.values() if r['errors'] == 0)
    
    return {
        "success": True,
        "total_tickers": len(tickers),
        "successful": success_count,
        "failed": len(tickers) - success_count,
        "results": results
    }


@router.get("/prices/{ticker}", status_code=status.HTTP_200_OK)
async def get_stock_prices(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days of historical data"),
    _rate_limit = Depends(rate_limit_stocks_prices)  # ← Rate limit check (100/minute)
) -> Dict[str, Any]:
    """
    Get historical prices with momentum indicators for a ticker.
    
    Args:
        ticker: Stock symbol
        days: Number of days (1-365)
    
    Returns:
        Historical price data with technical indicators
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = await db.execute(
        select(StockPrice)
        .where(
            StockPrice.ticker == ticker.upper(),
            StockPrice.date >= cutoff
        )
        .order_by(StockPrice.date.asc())
    )
    
    prices = result.scalars().all()
    
    if not prices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No price data found for {ticker}"
        )
    
    return {
        "ticker": ticker.upper(),
        "count": len(prices),
        "period_days": days,
        "prices": [
            {
                "date": p.date.isoformat(),
                "open": p.open_price,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "adjusted_close": p.adjusted_close,
                "volume": p.volume,
                # Momentum indicators
                "rsi": p.rsi,
                "macd": p.macd,
                "macd_signal": p.macd_signal,
                "sma_50": p.sma_50,
                "sma_200": p.sma_200,
                "volume_ratio": p.volume_ratio,
                "bb_upper": p.bb_upper,
                "bb_lower": p.bb_lower
            }
            for p in prices
        ]
    }


@router.get("/latest/{ticker}", status_code=status.HTTP_200_OK)
async def get_latest_price(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_redis),
    _rate_limit = Depends(rate_limit_stocks_latest)  # ← Rate limit check (200/minute - cached!)
) -> Dict[str, Any]:
    """
    Get most recent closing price for a ticker.
    
    Uses Redis cache (5-min TTL) for fast responses.
    Falls back to DB on cache miss.
    
    Args:
        ticker: Stock symbol
    
    Returns:
        Latest closing price, timestamp, and cache source
    """
    ticker = ticker.upper()
    
    # Check cache first (Write-Through pattern)
    cached_price = await cache.get_stock_price(ticker)
    if cached_price is not None:
        return {
            "ticker": ticker,
            "close": cached_price,
            "source": "cache",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # Cache miss - query DB
    service = StockService()
    price = await service.get_latest_price(ticker, db)
    
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No price data found for {ticker}"
        )
    
    # Update cache (Write-Through)
    await cache.set_stock_price(ticker, price)
    
    return {
        "ticker": ticker,
        "close": price,
        "source": "database",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/signals/{ticker}", status_code=status.HTTP_200_OK)
async def get_momentum_signals(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_redis),
    _rate_limit = Depends(rate_limit_stocks_signals)  # ← Rate limit check (100/minute - cached!)
) -> Dict[str, Any]:
    """
    Get momentum indicators and trading signals for a ticker.
    
    Uses Redis cache (5-min TTL) for fast responses.
    
    Args:
        ticker: Stock symbol
    
    Returns:
        Latest momentum indicators with crossover signals
    """
    ticker = ticker.upper()
    
    # Check cache first
    cached_signals = await cache.get_stock_signals(ticker)
    if cached_signals is not None:
        return {
            "ticker": ticker,
            "signals": cached_signals,
            "source": "cache",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # Cache miss - compute from DB
    service = StockService()
    signals = await service.get_momentum_signals(ticker, db)
    
    if signals is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No signal data found for {ticker}"
        )
    
    # Update cache
    await cache.set_stock_signals(ticker, signals)
    
    return {
        "ticker": ticker,
        "signals": signals,
        "source": "database",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/health", status_code=status.HTTP_200_OK)
async def stock_health_check(
    db: AsyncSession = Depends(get_db),
    _rate_limit = Depends(rate_limit_stocks_health)  # ← Rate limit check (30/minute)
) -> Dict[str, Any]:
    """
    Health check for stock data system.
    
    Returns:
        System status and stock data count
    """
    try:
        # Efficient counts
        total_records = (
            await db.execute(
                select(func.count()).select_from(StockPrice)
            )
        ).scalar_one()
        
        unique_tickers = (
            await db.execute(
                select(func.count(distinct(StockPrice.ticker)))
            )
        ).scalar_one()
        
        return {
            "status": "healthy",
            "total_records": total_records,
            "unique_tickers": unique_tickers,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        logger.error(f"Stock health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stock data system unavailable"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Task Management Endpoints (Background Job Triggers)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/tasks/fetch-trending", status_code=status.HTTP_202_ACCEPTED)
async def trigger_fetch_trending(
    request: Request,
    _rate_limit = Depends(rate_limit_tasks_fetch_trending)  # ← Rate limit check (5/hour)
) -> Dict[str, Any]:
    """
    Trigger background task to fetch stock data for trending tickers.
    
    This queues a Celery task that:
    1. Finds top 20 trending tickers from Reddit mentions (last 7 days)
    2. Fetches 5-day price history for each
    3. Calculates momentum indicators
    
    Returns immediately with task ID for tracking.
    
    Returns:
        Task ID and queue status
    """
    from backend.tasks.scraping_tasks import fetch_stocks_scheduled
    
    task = fetch_stocks_scheduled.delay()
    
    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Trending stocks fetch task queued",
        "check_status": f"/api/stocks/tasks/{task.id}"
    }


@router.post("/tasks/fetch-single/{ticker}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_fetch_single(
    ticker: str,
    request: Request,
    _rate_limit = Depends(rate_limit_tasks_fetch_single)  # ← Rate limit check (10/hour)
) -> Dict[str, Any]:
    """
    Trigger background task to fetch a single stock.
    
    Useful for adding new tickers to watchlist without blocking.
    
    Args:
        ticker: Stock symbol to fetch
    
    Returns:
        Task ID for tracking
    """
    from backend.tasks.scraping_tasks import fetch_single_stock
    
    task = fetch_single_stock.delay(ticker.upper())
    
    return {
        "task_id": task.id,
        "status": "queued",
        "ticker": ticker.upper(),
        "message": f"Fetch task queued for {ticker.upper()}",
        "check_status": f"/api/stocks/tasks/{task.id}"
    }


@router.post("/tasks/cleanup", status_code=status.HTTP_202_ACCEPTED)
async def trigger_cleanup(
    request: Request,
    retention_days: int = Query(90, ge=30, le=365),
    _rate_limit = Depends(rate_limit_tasks_cleanup)  # ← Rate limit check (2/day - DESTRUCTIVE!)
) -> Dict[str, Any]:
    """
    Trigger background cleanup of old data.
    
    Removes data older than retention period to manage DB size.
    
    Args:
        retention_days: Days to keep (30-365, default 90)
    
    Returns:
        Task ID for tracking
    """
    from backend.tasks.maintenance_tasks import cleanup_old_data
    
    task = cleanup_old_data.delay(retention_days)
    
    return {
        "task_id": task.id,
        "status": "queued",
        "retention_days": retention_days,
        "message": f"Cleanup task queued (keeping {retention_days} days)"
    }


@router.get("/tasks/{task_id}", status_code=status.HTTP_200_OK)
async def get_task_status(
    task_id: str,
    request: Request,
    _rate_limit = Depends(rate_limit_tasks_status)  # ← Rate limit check (50/minute)
) -> Dict[str, Any]:
    """
    Check status of a background task.
    
    Args:
        task_id: Celery task ID
    
    Returns:
        Task status, result if complete
    """
    from backend.celery_app import app as celery_app
    
    result = celery_app.AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": result.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        "ready": result.ready(),
    }
    
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)
    
    return response


@router.get("/cache/stats", status_code=status.HTTP_200_OK)
async def get_cache_stats(
    cache: RedisCache = Depends(get_redis),
    request: Request = None,
    _rate_limit = Depends(rate_limit_cache_stats)  # ← Rate limit check (100/minute)
) -> Dict[str, Any]:
    """
    Get Redis cache statistics.
    
    Returns:
        Cache hit rate, memory usage, connection status
    """
    stats = await cache.get_stats()
    
    return {
        "cache": stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.delete("/cache/{ticker}", status_code=status.HTTP_200_OK)
async def invalidate_ticker_cache(
    ticker: str,
    cache: RedisCache = Depends(get_redis),
    request: Request = None,
    _rate_limit = Depends(rate_limit_cache_invalidate)  # ← Rate limit check (20/minute)
) -> Dict[str, Any]:
    """
    Invalidate cache for a specific ticker.
    
    Use after manual data corrections or to force fresh data.
    
    Args:
        ticker: Stock symbol
    
    Returns:
        Invalidation status
    """
    ticker = ticker.upper()
    
    # Delete all cache keys for this ticker
    deleted = await cache.delete_pattern(f"stock:*:{ticker}")
    deleted += await cache.delete_pattern(f"sentiment:*:{ticker}")
    
    return {
        "ticker": ticker,
        "keys_deleted": deleted,
        "message": f"Cache invalidated for {ticker}"
    }

