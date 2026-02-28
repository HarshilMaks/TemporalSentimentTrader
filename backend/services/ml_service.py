"""ML Service — thin wrapper around SignalEngine for API/task callers."""

import logging
from typing import Dict, List, Optional

from backend.database.config import AsyncSessionLocal
from backend.ml.inference.predictor import Predictor
from backend.services.risk_manager import PortfolioState

logger = logging.getLogger(__name__)


class MLService:
    """Delegates to SignalEngine for the sequential triangulation pipeline."""

    def __init__(self, model_dir: Optional[str] = None):
        self.predictor = Predictor(model_dir)

    async def generate_daily_signals(
        self,
        features_by_ticker: Optional[Dict] = None,
        portfolio: Optional[PortfolioState] = None,
        session=None,
    ) -> List[Dict]:
        """Run the full sequential pipeline via SignalEngine.

        The features_by_ticker param is kept for backward compat but ignored —
        SignalEngine fetches its own data from DB.
        """
        from backend.strategy.signal_engine import SignalEngine

        engine = SignalEngine()
        pv = portfolio.portfolio_value if portfolio else 100_000.0
        cp = portfolio.current_positions if portfolio else 0

        signals = await engine.generate_signals(portfolio_value=pv, current_positions=cp)

        return [
            {
                "ticker": s.ticker,
                "signal": s.signal.value,
                "confidence": s.confidence,
                "entry_price": s.entry_price,
                "target_price": s.target_price,
                "stop_loss": s.stop_loss,
                "position_size_pct": s.position_size_pct,
            }
            for s in signals
        ]
