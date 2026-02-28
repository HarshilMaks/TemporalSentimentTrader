"""Prediction ORM model — stores ensemble ML predictions."""

from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.sql import func

from backend.database.config import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False)
    signal = Column(String(10), nullable=False)  # BUY / HOLD / SELL
    confidence = Column(Float, nullable=False)

    # Per-model confidence breakdown
    xgb_confidence = Column(Float, nullable=True)
    lgb_confidence = Column(Float, nullable=True)
    tft_confidence = Column(Float, nullable=True)

    # Traceability
    feature_snapshot_id = Column(String(36), nullable=True)

    predicted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_prediction_ticker_date", "ticker", "predicted_at"),
    )

    def __repr__(self):
        return f"<Prediction {self.signal} {self.ticker} conf={self.confidence:.2f}>"
