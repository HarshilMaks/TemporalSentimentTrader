"""Predictions API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.config import get_db
from backend.models.prediction import Prediction

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/latest")
async def get_latest_predictions(db: AsyncSession = Depends(get_db)):
    """Latest ensemble prediction per ticker."""
    # Subquery: max predicted_at per ticker
    sub = (
        select(Prediction.ticker, func.max(Prediction.predicted_at).label("latest"))
        .group_by(Prediction.ticker)
        .subquery()
    )
    result = await db.execute(
        select(Prediction).join(
            sub,
            (Prediction.ticker == sub.c.ticker) & (Prediction.predicted_at == sub.c.latest),
        )
    )
    preds = result.scalars().all()
    return {"count": len(preds), "predictions": [_serialize(p) for p in preds]}


@router.get("/ticker/{ticker}")
async def get_predictions_by_ticker(
    ticker: str,
    limit: int = Query(30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Prediction history for a ticker."""
    result = await db.execute(
        select(Prediction)
        .where(Prediction.ticker == ticker.upper())
        .order_by(Prediction.predicted_at.desc())
        .limit(limit)
    )
    preds = result.scalars().all()
    if not preds:
        raise HTTPException(404, f"No predictions for {ticker.upper()}")
    return {"ticker": ticker.upper(), "predictions": [_serialize(p) for p in preds]}


@router.post("/run")
async def trigger_prediction_run():
    """Trigger a manual prediction run via Celery."""
    from backend.celery_app import app as celery_app

    task = celery_app.send_task("backend.tasks.ml_tasks.generate_daily_signals")
    return {"status": "queued", "task_id": task.id}


def _serialize(p: Prediction) -> dict:
    return {
        "id": p.id,
        "ticker": p.ticker,
        "signal": p.signal,
        "confidence": p.confidence,
        "xgb_confidence": p.xgb_confidence,
        "lgb_confidence": p.lgb_confidence,
        "tft_confidence": p.tft_confidence,
        "feature_snapshot_id": p.feature_snapshot_id,
        "predicted_at": p.predicted_at.isoformat() if p.predicted_at else None,
    }
