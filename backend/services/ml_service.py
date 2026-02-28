"""ML Service — orchestrates features → inference → risk → signal persistence."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ml.inference.predictor import Predictor
from backend.models.prediction import Prediction
from backend.models.trading_signal import TradingSignal, SignalType
from backend.services.risk_manager import (
    RiskManager,
    SignalValidationRequest,
    PortfolioState,
)
from backend.database.config import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Default portfolio state for signal generation
DEFAULT_PORTFOLIO = PortfolioState(
    portfolio_value=100_000.0,
    current_positions=0,
    portfolio_drawdown_pct=0.0,
)

STOP_LOSS_PCT = 0.05
TARGET_PCT = 0.10


class MLService:
    """Orchestrator: features → ensemble prediction → risk validation → signal."""

    def __init__(self, model_dir: Optional[str] = None):
        self.predictor = Predictor(model_dir)
        self.risk_manager = RiskManager()

    async def generate_daily_signals(
        self,
        features_by_ticker: Dict[str, Dict],
        portfolio: Optional[PortfolioState] = None,
        session: Optional[AsyncSession] = None,
    ) -> List[Dict]:
        """Run the full pipeline for all tickers.

        Args:
            features_by_ticker: {ticker: {feature_name: value, ...}}
            portfolio: Current portfolio state (uses default if None)
            session: DB session (creates one if None)

        Returns:
            List of approved signal dicts.
        """
        portfolio = portfolio or DEFAULT_PORTFOLIO
        own_session = session is None
        if own_session:
            session = AsyncSessionLocal()

        self.predictor.load_models()

        approved: List[Dict] = []

        try:
            # Build feature matrix from dict
            tickers = list(features_by_ticker.keys())
            if not tickers:
                logger.info("No tickers to predict")
                return []

            feature_keys = self._get_numeric_keys(features_by_ticker[tickers[0]])
            matrix = np.array(
                [[features_by_ticker[t].get(k, 0.0) or 0.0 for k in feature_keys] for t in tickers]
            )

            predictions = self.predictor.predict_batch(tickers, matrix)

            for pred in predictions:
                ticker = pred["ticker"]
                signal = pred["signal"]
                confidence = pred["confidence"]
                features = features_by_ticker[ticker]

                # Persist prediction
                db_pred = Prediction(
                    ticker=ticker,
                    signal=signal,
                    confidence=confidence,
                    xgb_confidence=pred.get("buy_prob"),
                    lgb_confidence=pred.get("hold_prob"),
                    tft_confidence=pred.get("sell_prob"),
                )
                session.add(db_pred)

                # Only validate BUY/SELL through risk manager
                if signal == "HOLD":
                    continue

                entry_price = features.get("close_price", 0.0) or 0.0
                if entry_price <= 0:
                    continue

                target_price = entry_price * (1 + TARGET_PCT)
                stop_loss = entry_price * (1 - STOP_LOSS_PCT)

                request = SignalValidationRequest(
                    ticker=ticker,
                    signal_type=signal,
                    confidence=confidence,
                    entry_price=entry_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    rsi_value=features.get("rsi"),
                    macd_value=features.get("macd"),
                    sentiment_score=features.get("sentiment_score"),
                )

                result = self.risk_manager.validate(request, portfolio)

                if result.passed:
                    trading_signal = TradingSignal(
                        ticker=ticker,
                        signal=SignalType.BUY if signal == "BUY" else SignalType.SELL,
                        confidence=confidence,
                        entry_price=entry_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        risk_reward_ratio=result.risk_reward_ratio,
                        position_size_pct=result.position_size_pct,
                        rsi_value=features.get("rsi"),
                        macd_value=features.get("macd"),
                        sentiment_score=features.get("sentiment_score"),
                        sentiment_trend=features.get("sentiment_trend"),
                    )
                    session.add(trading_signal)
                    portfolio.current_positions += 1

                    approved.append({
                        "ticker": ticker,
                        "signal": signal,
                        "confidence": confidence,
                        "entry_price": entry_price,
                        "target_price": target_price,
                        "stop_loss": stop_loss,
                        "position_size_pct": result.position_size_pct,
                    })
                    logger.info(f"Signal APPROVED: {signal} {ticker} @{entry_price:.2f} conf={confidence:.2f}")
                else:
                    logger.info(
                        f"Signal REJECTED: {signal} {ticker} — {result.rejection_reason}"
                    )

            await session.commit()
            logger.info(f"Daily signals complete: {len(approved)} approved out of {len(predictions)} predictions")

        except Exception as e:
            await session.rollback()
            logger.error(f"Signal generation failed: {e}", exc_info=True)
            raise
        finally:
            if own_session:
                await session.close()

        return approved

    @staticmethod
    def _get_numeric_keys(features: Dict) -> List[str]:
        """Extract keys that have numeric values (skip strings, None-heavy metadata)."""
        skip = {"ticker", "date", "data_quality", "snapshot_id"}
        return [
            k for k, v in features.items()
            if k not in skip and isinstance(v, (int, float))
        ]
