"""Regime Filter — determines BULL/BEAR market regime using SPY vs SMA200."""

import logging
from dataclasses import dataclass
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class RegimeResult:
    regime: str  # "BULL" or "BEAR"
    spy_price: float
    sma200: float


class RegimeFilter:
    """Market regime detection: SPY close vs 200-day SMA."""

    def get_market_regime(self) -> RegimeResult:
        """Fetch SPY data and determine current market regime.

        Returns BULL if SPY close > SMA200, BEAR otherwise.
        """
        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(period="1y")

            if hist.empty or len(hist) < 200:
                logger.warning("Insufficient SPY data, defaulting to BEAR")
                return RegimeResult(regime="BEAR", spy_price=0.0, sma200=0.0)

            sma200 = hist["Close"].rolling(200).mean().iloc[-1]
            spy_price = hist["Close"].iloc[-1]
            regime = "BULL" if spy_price > sma200 else "BEAR"

            logger.info(f"Market regime: {regime} (SPY={spy_price:.2f}, SMA200={sma200:.2f})")
            return RegimeResult(regime=regime, spy_price=spy_price, sma200=sma200)

        except Exception as e:
            logger.error(f"Regime detection failed: {e}, defaulting to BEAR")
            return RegimeResult(regime="BEAR", spy_price=0.0, sma200=0.0)
