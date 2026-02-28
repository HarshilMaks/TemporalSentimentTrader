"""Telegram notifier — pushes trading signals to your phone.

Uses the Telegram Bot API (free, no library needed — just HTTP POST).

Setup:
  1. Message @BotFather on Telegram → /newbot → get TELEGRAM_BOT_TOKEN
  2. Message your bot, then visit:
     https://api.telegram.org/bot<TOKEN>/getUpdates
     to find your TELEGRAM_CHAT_ID
  3. Add both to .env
"""
import os
import requests
import logging
from typing import Optional

from backend.models.trading_signal import TradingSignal

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_signal(signal: TradingSignal, portfolio_value: float = 100_000.0) -> bool:
    """Push a trading signal to Telegram as a strict execution ticket.

    Returns True if sent successfully, False otherwise.
    """
    if not _BOT_TOKEN or not _CHAT_ID:
        logger.warning("Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False

    position_dollars = portfolio_value * (signal.position_size_pct or 0.02)
    text = _format_signal(signal, position_dollars)

    try:
        resp = requests.post(
            _API_URL.format(token=_BOT_TOKEN),
            json={"chat_id": _CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info(f"Telegram: sent {signal.ticker} signal")
            return True
        else:
            logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def send_message(text: str) -> bool:
    """Send a raw text message to Telegram."""
    if not _BOT_TOKEN or not _CHAT_ID:
        return False
    try:
        resp = requests.post(
            _API_URL.format(token=_BOT_TOKEN),
            json={"chat_id": _CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _format_signal(signal: TradingSignal, position_dollars: float) -> str:
    """Format signal as a strict, baby-proof execution ticket."""
    return (
        "🚨 <b>TRIANGULATION BUY SIGNAL</b>\n"
        "\n"
        f"<b>Ticker:</b> ${signal.ticker}\n"
        f"<b>Confidence:</b> {signal.confidence:.0%}\n"
        f"<b>Triangulation Score:</b> {signal.sentiment_score}/100\n"
        "\n"
        f"<b>Action:</b> BUY at Market Open\n"
        f"<b>Entry:</b> ${signal.entry_price:.2f}\n"
        f"<b>Take Profit:</b> ${signal.target_price:.2f} (+10%)\n"
        f"<b>Stop Loss:</b> ${signal.stop_loss:.2f} (-5%)\n"
        f"<b>R/R:</b> 1:{signal.risk_reward_ratio:.1f}\n"
        "\n"
        f"<b>Position Size:</b> 2% (${position_dollars:,.0f})\n"
        f"<b>Expires:</b> {signal.expires_at.strftime('%Y-%m-%d') if signal.expires_at else '7 days'}\n"
        "\n"
        "Copy entry, stop, target into broker. Do not analyze. Execute."
    )
