"""Sentiment & insider activity API routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.config import get_db
from backend.models.insider_trade import InsiderTrade
from backend.models.reddit import RedditPost

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("/trending")
async def get_trending(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Top tickers by mention count + average sentiment."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.unnest(RedditPost.tickers).label("ticker"),
            func.count().label("mentions"),
            func.avg(RedditPost.sentiment_score).label("avg_sentiment"),
        )
        .where(RedditPost.created_at >= since)
        .group_by("ticker")
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = result.all()
    return {
        "period_days": days,
        "tickers": [
            {
                "ticker": r.ticker,
                "mentions": r.mentions,
                "avg_sentiment": round(float(r.avg_sentiment or 0), 4),
            }
            for r in rows
        ],
    }


@router.get("/ticker/{ticker}")
async def get_sentiment_history(
    ticker: str,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Daily sentiment aggregates for a ticker."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc("day", RedditPost.created_at).label("day"),
            func.avg(RedditPost.sentiment_score).label("avg_sentiment"),
            func.count().label("mentions"),
        )
        .where(
            RedditPost.tickers.any(ticker.upper()),
            RedditPost.created_at >= since,
        )
        .group_by("day")
        .order_by("day")
    )
    rows = result.all()
    if not rows:
        raise HTTPException(404, f"No sentiment data for {ticker.upper()}")
    return {
        "ticker": ticker.upper(),
        "history": [
            {
                "date": r.day.date().isoformat(),
                "avg_sentiment": round(float(r.avg_sentiment or 0), 4),
                "mentions": r.mentions,
            }
            for r in rows
        ],
    }


@router.get("/insider/{ticker}")
async def get_insider_activity(
    ticker: str,
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Insider trading activity for a ticker."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    result = await db.execute(
        select(InsiderTrade)
        .where(InsiderTrade.ticker == ticker.upper(), InsiderTrade.transaction_date >= since)
        .order_by(InsiderTrade.transaction_date.desc())
    )
    trades = result.scalars().all()
    if not trades:
        raise HTTPException(404, f"No insider trades for {ticker.upper()}")
    return {
        "ticker": ticker.upper(),
        "trades": [
            {
                "insider_name": t.insider_name,
                "insider_title": t.insider_title,
                "transaction_type": t.transaction_type,
                "shares": t.shares,
                "dollar_value": t.dollar_value,
                "transaction_date": t.transaction_date.isoformat(),
                "filing_url": t.filing_url,
            }
            for t in trades
        ],
    }
