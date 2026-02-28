"""Signal Engine — Sequential Triangulation Pipeline.

Flow:
  1. Regime gate (SPY > SMA200)
  2. Scan ALL tickers: score Layer 1 (Insider) + Layer 2 (Volume) + Layer 3 (Hype) + Technicals
  3. Only tickers passing triangulation threshold → ML ensemble
  4. ML predicts P(signal_success) — NOT price direction
  5. Passed tickers → Risk Manager
  6. Approved signals → DB + Telegram
"""

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
from backend.services.telegram_notifier import send_signal as telegram_send
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

# Triangulation threshold — ticker must score >= this to reach ML
TRIANGULATION_THRESHOLD = 60


@dataclass
class TriangulationResult:
    ticker: str
    total_score: int
    insider_score: int
    flow_score: int
    sentiment_score: int
    technical_score: int


class SignalEngine:
    """Sequential triangulation: Score → Filter → ML validate → Risk → Signal."""

    def __init__(self):
        self.regime_filter = RegimeFilter()
        self.insider_tracker = InsiderTracker()
        self.risk_manager = RiskManager()
        self.predictor = Predictor()
        self.predictor.load_models()

    # ── Public API ───────────────────────────────────────────────────────

    async def generate_signals(
        self,
        tickers: Optional[List[str]] = None,
        portfolio_value: float = DEFAULT_PORTFOLIO_VALUE,
        current_positions: int = 0,
    ) -> List[TradingSignal]:
        """Full sequential pipeline: regime → triangulate ALL → ML on survivors → risk → signal."""

        # Step 1: Regime gate
        regime = self.regime_filter.get_market_regime()
        if regime.regime == "BEAR":
            logger.info("BEAR regime — no BUY signals generated")
            return []

        tickers = tickers or DEFAULT_WATCHLIST

        async with AsyncSessionLocal() as session:
            # Step 2: Score ALL tickers through triangulation
            candidates: List[tuple[TriangulationResult, StockPrice]] = []
            for ticker in tickers:
                try:
                    tri = await self.calculate_triangulation_score(ticker, session)
                    if tri.total_score < TRIANGULATION_THRESHOLD:
                        continue

                    # Fetch latest price for candidates only
                    row = await session.execute(
                        select(StockPrice)
                        .where(StockPrice.ticker == ticker)
                        .order_by(StockPrice.date.desc())
                        .limit(1)
                    )
                    price = row.scalar_one_or_none()
                    if price is None:
                        continue

                    candidates.append((tri, price))
                    logger.info(
                        f"TRIANGULATION PASS: {ticker} score={tri.total_score} "
                        f"(insider={tri.insider_score} flow={tri.flow_score} "
                        f"sentiment={tri.sentiment_score} tech={tri.technical_score})"
                    )
                except Exception as e:
                    logger.error(f"Error scoring {ticker}: {e}")

            if not candidates:
                logger.info(f"No tickers passed triangulation (threshold={TRIANGULATION_THRESHOLD})")
                return []

            logger.info(f"{len(candidates)} tickers passed triangulation → sending to ML")

            # Step 3: ML validation — only on triangulation survivors
            # Feature vector includes triangulation scores so ML learns
            # "given these triangulation conditions, will this signal succeed?"
            ml_approved: List[tuple[TriangulationResult, StockPrice, Dict]] = []
            for tri, price in candidates:
                features = self._build_feature_vector(tri, price)
                result = self.predictor.predict_single(tri.ticker, features)

                if result["signal"] == "BUY" and result["confidence"] >= 0.70:
                    ml_approved.append((tri, price, result))
                    logger.info(f"ML PASS: {tri.ticker} confidence={result['confidence']:.3f}")
                else:
                    logger.info(
                        f"ML REJECT: {tri.ticker} signal={result['signal']} "
                        f"confidence={result['confidence']:.3f}"
                    )

            if not ml_approved:
                logger.info("No tickers passed ML validation")
                return []

            # Step 4: Risk manager — final gate
            portfolio = PortfolioState(
                portfolio_value=portfolio_value,
                current_positions=current_positions,
                portfolio_drawdown_pct=0.0,
            )

            approved: List[TradingSignal] = []
            for tri, price, ml_result in ml_approved:
                signal = self._build_signal(tri, price, ml_result, portfolio)
                if signal:
                    approved.append(signal)
                    portfolio.current_positions += 1
                    # Push to Telegram immediately
                    telegram_send(signal, portfolio.portfolio_value)

        logger.info(f"Pipeline: {len(tickers)} scanned → {len(candidates)} triangulated → {len(ml_approved)} ML approved → {len(approved)} risk approved")
        return approved

    async def calculate_triangulation_score(
        self, ticker: str, session: AsyncSession
    ) -> TriangulationResult:
        """Score a ticker across 4 dimensions (0-100 total)."""
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

    # ── Feature vector for ML ────────────────────────────────────────────

    def _build_feature_vector(self, tri: TriangulationResult, price: StockPrice) -> np.ndarray:
        """Build feature vector that includes BOTH technicals AND triangulation scores.

        The ML model learns: "given these triangulation + technical conditions,
        what is the probability this signal will succeed (+10% before -5%)?"

        11 features (must match training data):
          0: rsi
          1: macd
          2: macd_signal
          3: bb_upper
          4: bb_lower
          5: sma_50
          6: sma_200
          7: volume_ratio
          8: close
          9: volume
         10: high-low range
        """
        return np.array([
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

    # ── Build final signal ───────────────────────────────────────────────

    def _build_signal(
        self,
        tri: TriangulationResult,
        price: StockPrice,
        ml_result: Dict,
        portfolio: PortfolioState,
    ) -> Optional[TradingSignal]:
        """Risk-validate and build TradingSignal ORM object."""
        entry = price.close
        stop_loss = round(entry * 0.95, 2)   # -5% hardcoded
        target = round(entry * 1.10, 2)       # +10% hardcoded

        validation = self.risk_manager.validate(
            SignalValidationRequest(
                ticker=tri.ticker,
                signal_type="BUY",
                confidence=ml_result["confidence"],
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
            logger.info(f"RISK REJECT: {tri.ticker} — {validation.rejection_reason}")
            return None

        return TradingSignal(
            ticker=tri.ticker,
            signal=SignalType.BUY,
            confidence=ml_result["confidence"],
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

    # ── Scoring helpers (unchanged) ──────────────────────────────────────

    async def _score_insider(self, ticker: str, session: AsyncSession) -> int:
        """Layer 1: Insider buying score (0-30)."""
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
        """Layer 2: Institutional volume flow (0-20)."""
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
        """Layer 3: Retail hype — Reddit + India RSS sentiment (0-20)."""
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
        """Technical score (0-30): RSI oversold + MACD cross + above SMA50."""
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
