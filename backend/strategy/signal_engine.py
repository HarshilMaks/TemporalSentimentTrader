"""Signal Engine — Triangulation scoring and signal generation."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.config import AsyncSessionLocal
from backend.ml.inference.predictor import Predictor
from backend.models.insider_trade import InsiderTrade
from backend.models.reddit import RedditPost
from backend.models.stock import StockPrice
from backend.models.trading_signal import SignalType, TradingSignal
from backend.services.risk_manager import (
    PortfolioState,
    RiskManager,
    SignalValidationRequest,
)
from backend.strategy.insider_tracker import InsiderTracker
from backend.strategy.regime_filter import RegimeFilter

logger = logging.getLogger(__name__)

DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "AMD", "NFLX", "DIS",
    "BABA", "INTC", "CSCO", "ADBE", "PYPL",
    "CRM", "ORCL", "UBER", "SPOT", "COIN",
]

DEFAULT_PORTFOLIO_VALUE = 100_000.0


@dataclass
class TriangulationResult:
    ticker: str
    total_score: int
    insider_score: int
    flow_score: int
    sentiment_score: int
    technical_score: int


class SignalEngine:
    """Triangulation scoring: BUY only when 3+ independent data layers align."""

    def __init__(self):
        self.regime_filter = RegimeFilter()
        self.insider_tracker = InsiderTracker()
        self.risk_manager = RiskManager()
        self.predictor = Predictor()
        self.predictor.load_models()

    async def calculate_triangulation_score(
        self, ticker: str, session: AsyncSession
    ) -> TriangulationResult:
        """Score a ticker across 4 dimensions (0-100 total).

        - insider_score  (0-30): SEC Form 4 insider buying
        - flow_score     (0-20): institutional volume flow
        - sentiment_score(0-20): Reddit sentiment + mention count
        - technical_score(0-30): RSI, MACD crossover, price vs SMA50
        """
        insider = await self._score_insider(ticker, session)
        flow = await self._score_flow(ticker, session)
        sentiment = await self._score_sentiment(ticker, session)
        technical = await self._score_technical(ticker, session)

        return TriangulationResult(
            ticker=ticker,
            total_score=insider + flow + sentiment + technical,
            insider_score=insider,
            flow_score=flow,
            sentiment_score=sentiment,
            technical_score=technical,
        )

    async def generate_signals(
        self,
        tickers: Optional[List[str]] = None,
        portfolio_value: float = DEFAULT_PORTFOLIO_VALUE,
        current_positions: int = 0,
    ) -> List[TradingSignal]:
        """Full triangulation pipeline: regime → score → ML → risk → signal.

        Returns list of approved TradingSignal ORM objects (not yet committed).
        """
        # 1. Regime gate
        regime = self.regime_filter.get_market_regime()
        if regime.regime == "BEAR":
            logger.info("BEAR regime — no BUY signals generated")
            return []

        tickers = tickers or DEFAULT_WATCHLIST
        approved: List[TradingSignal] = []

        portfolio = PortfolioState(
            portfolio_value=portfolio_value,
            current_positions=current_positions,
            portfolio_drawdown_pct=0.0,
        )

        async with AsyncSessionLocal() as session:
            for ticker in tickers:
                try:
                    signal = await self._evaluate_ticker(ticker, session, portfolio)
                    if signal:
                        approved.append(signal)
                        portfolio.current_positions += 1
                except Exception as e:
                    logger.error(f"Error evaluating {ticker}: {e}")

        logger.info(f"Generated {len(approved)} approved signals from {len(tickers)} tickers")
        return approved

    # ── Private scoring helpers ──────────────────────────────────────────

    async def _score_insider(self, ticker: str, session: AsyncSession) -> int:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=30)
        rows = await session.execute(
            select(InsiderTrade).where(
                InsiderTrade.ticker == ticker,
                InsiderTrade.transaction_date >= cutoff,
            )
        )
        trades = [
            {
                "insider_title": r.insider_title,
                "transaction_type": r.transaction_type,
                "transaction_date": r.transaction_date,
            }
            for r in rows.scalars().all()
        ]
        return self.insider_tracker.calculate_insider_score(trades)

    async def _score_flow(self, ticker: str, session: AsyncSession) -> int:
        row = await session.execute(
            select(StockPrice.volume_ratio)
            .where(StockPrice.ticker == ticker)
            .order_by(StockPrice.date.desc())
            .limit(1)
        )
        vr = row.scalar_one_or_none()
        if vr is None:
            return 0
        if vr > 2.0:
            return 20
        if vr > 1.5:
            return 10
        return 0

    async def _score_sentiment(self, ticker: str, session: AsyncSession) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=7)
        row = await session.execute(
            select(
                func.avg(RedditPost.sentiment_score),
                func.count(RedditPost.id),
            ).where(
                RedditPost.tickers.any(ticker),
                RedditPost.created_at >= since,
            )
        )
        avg_sent, mention_count = row.one()
        if avg_sent is not None and float(avg_sent) > 0.3 and mention_count > 20:
            return 20
        if avg_sent is not None and float(avg_sent) > 0.3:
            return 10
        return 0

    async def _score_technical(self, ticker: str, session: AsyncSession) -> int:
        row = await session.execute(
            select(StockPrice)
            .where(StockPrice.ticker == ticker)
            .order_by(StockPrice.date.desc())
            .limit(1)
        )
        price = row.scalar_one_or_none()
        if price is None:
            return 0

        score = 0
        if price.rsi is not None and price.rsi < 35:
            score += 10
        if price.macd is not None and price.macd_signal is not None and price.macd > price.macd_signal:
            score += 10
        if price.sma_50 is not None and price.close > price.sma_50:
            score += 10
        return score

    # ── Ticker evaluation pipeline ───────────────────────────────────────

    async def _evaluate_ticker(
        self, ticker: str, session: AsyncSession, portfolio: PortfolioState
    ) -> Optional[TradingSignal]:
        """Score → ML validate → risk check → build TradingSignal."""
        tri = await self.calculate_triangulation_score(ticker, session)

        if tri.total_score < 60:  # Production threshold
            return None

        # Build feature vector from latest stock data for ML
        row = await session.execute(
            select(StockPrice)
            .where(StockPrice.ticker == ticker)
            .order_by(StockPrice.date.desc())
            .limit(1)
        )
        price = row.scalar_one_or_none()
        if price is None:
            return None

        features = np.array([
            price.rsi or 50.0,
            price.macd or 0.0,
            price.macd_signal or 0.0,
            price.bb_upper or price.close,
            price.bb_lower or price.close,
            price.sma_50 or price.close,
            price.sma_200 or price.close,
            price.volume_ratio or 1.0,
            price.close,
            price.volume or 0,
            price.high - price.low if price.high and price.low else 0.0,
        ], dtype=np.float32)

        result = self.predictor.predict_single(ticker, features)

        if result["signal"] != "BUY" or result["confidence"] < 0.7:  # Production threshold
            return None

        # Risk validation
        entry = price.close
        stop_loss = round(entry * 0.95, 2)
        target = round(entry * 1.10, 2)

        validation = self.risk_manager.validate(
            SignalValidationRequest(
                ticker=ticker,
                signal_type="BUY",
                confidence=result["confidence"],
                entry_price=entry,
                target_price=target,
                stop_loss=stop_loss,
                rsi_value=price.rsi,
                macd_value=price.macd,
                sentiment_score=float(tri.sentiment_score),
            ),
            portfolio,
        )

        if not validation.passed:
            return None

        return TradingSignal(
            ticker=ticker,
            signal=SignalType.BUY,
            confidence=result["confidence"],
            entry_price=entry,
            target_price=target,
            stop_loss=stop_loss,
            risk_reward_ratio=validation.risk_reward_ratio,
            position_size_pct=validation.position_size_pct,
            rsi_value=price.rsi,
            macd_value=price.macd,
            sentiment_score=float(tri.sentiment_score),
            is_active=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
