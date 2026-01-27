from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from backend.models.stock import StockPrice
from backend.services.stock_service import StockService
from backend.database.config import get_db
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
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get most recent closing price for a ticker.
    
    Args:
        ticker: Stock symbol
    
    Returns:
        Latest closing price and timestamp
    """
    service = StockService()
    price = await service.get_latest_price(ticker.upper(), db)
    
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No price data found for {ticker}"
        )
    
    return {
        "ticker": ticker.upper(),
        "close": price,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/signals/{ticker}", status_code=status.HTTP_200_OK)
async def get_momentum_signals(
    ticker: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get momentum indicators and trading signals for a ticker.
    
    Args:
        ticker: Stock symbol
    
    Returns:
        Latest momentum indicators with crossover signals
    """
    service = StockService()
    signals = await service.get_momentum_signals(ticker.upper(), db)
    
    if signals is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No signal data found for {ticker}"
        )
    
    return {
        "ticker": ticker.upper(),
        "signals": signals,
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
