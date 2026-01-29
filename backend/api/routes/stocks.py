from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from backend.models.stock import StockPrice
from backend.services.stock_service import StockService
from backend.database.config import get_db
from backend.cache.redis_client import RedisCache, get_redis
from backend.utils.logger import logger

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.post("/fetch/{ticker}", status_code=status.HTTP_200_OK)
async def fetch_stock_data(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    period: str = Query("3mo", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$")
) -> Dict[str, Any]:
    """
    Manually trigger stock data fetch with momentum indicators.
    
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
    period: str = Query("3mo", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$")
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
    days: int = Query(30, ge=1, le=365, description="Number of days of historical data")
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
    cache: RedisCache = Depends(get_redis)
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
    cache: RedisCache = Depends(get_redis)
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
async def stock_health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
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
async def trigger_fetch_trending() -> Dict[str, Any]:
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
async def trigger_fetch_single(ticker: str) -> Dict[str, Any]:
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
async def trigger_cleanup(retention_days: int = Query(90, ge=30, le=365)) -> Dict[str, Any]:
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
async def get_task_status(task_id: str) -> Dict[str, Any]:
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
async def get_cache_stats(cache: RedisCache = Depends(get_redis)) -> Dict[str, Any]:
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
    cache: RedisCache = Depends(get_redis)
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

