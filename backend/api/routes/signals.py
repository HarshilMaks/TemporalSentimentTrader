"""Trading signals API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.config import get_db
from backend.models.trading_signal import TradingSignal

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/active")
async def get_active_signals(db: AsyncSession = Depends(get_db)):
    """All currently active trading signals."""
    result = await db.execute(
        select(TradingSignal)
        .where(TradingSignal.is_active == 1)
        .order_by(TradingSignal.generated_at.desc())
    )
    signals = result.scalars().all()
    return {
        "count": len(signals),
        "signals": [_serialize_signal(s) for s in signals],
    }


@router.get("/history")
async def get_signal_history(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Closed signals with P&L."""
    result = await db.execute(
        select(TradingSignal)
        .where(TradingSignal.is_active == 0)
        .order_by(TradingSignal.closed_at.desc())
        .limit(limit)
    )
    signals = result.scalars().all()
    return {
        "count": len(signals),
        "signals": [_serialize_signal(s, include_pnl=True) for s in signals],
    }


@router.get("/ticker/{ticker}")
async def get_signals_by_ticker(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """All signals (active + closed) for a specific ticker."""
    result = await db.execute(
        select(TradingSignal)
        .where(TradingSignal.ticker == ticker.upper())
        .order_by(TradingSignal.generated_at.desc())
    )
    signals = result.scalars().all()
    if not signals:
        raise HTTPException(404, f"No signals found for {ticker.upper()}")
    return {"ticker": ticker.upper(), "signals": [_serialize_signal(s, include_pnl=True) for s in signals]}


@router.get("/daily-report")
async def get_daily_report(db: AsyncSession = Depends(get_db)):
    """Today's generated signals."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(TradingSignal)
        .where(TradingSignal.generated_at >= today_start)
        .order_by(TradingSignal.confidence.desc())
    )
    signals = result.scalars().all()
    return {
        "date": today_start.date().isoformat(),
        "count": len(signals),
        "signals": [_serialize_signal(s) for s in signals],
    }


@router.post("/{signal_id}/close")
async def close_signal(
    signal_id: int,
    exit_price: float = Query(..., gt=0),
    exit_reason: str = Query("manual"),
    db: AsyncSession = Depends(get_db),
):
    """Manually close a signal."""
    result = await db.execute(
        select(TradingSignal).where(TradingSignal.id == signal_id, TradingSignal.is_active == 1)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Active signal not found")

    signal.is_active = 0
    signal.exit_price = exit_price
    signal.exit_reason = exit_reason
    signal.closed_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "closed", "signal": _serialize_signal(signal, include_pnl=True)}


def _serialize_signal(s: TradingSignal, include_pnl: bool = False) -> dict:
    data = {
        "id": s.id,
        "ticker": s.ticker,
        "signal": s.signal.value if s.signal else None,
        "confidence": s.confidence,
        "entry_price": s.entry_price,
        "target_price": s.target_price,
        "stop_loss": s.stop_loss,
        "risk_reward_ratio": s.risk_reward_ratio,
        "position_size_pct": s.position_size_pct,
        "rsi_value": s.rsi_value,
        "macd_value": s.macd_value,
        "sentiment_score": s.sentiment_score,
        "is_active": bool(s.is_active),
        "generated_at": s.generated_at.isoformat() if s.generated_at else None,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
    }
    if include_pnl and s.exit_price and s.entry_price:
        data["exit_price"] = s.exit_price
        data["exit_reason"] = s.exit_reason
        data["closed_at"] = s.closed_at.isoformat() if s.closed_at else None
        data["pnl_pct"] = round((s.exit_price - s.entry_price) / s.entry_price * 100, 2)
    return data
