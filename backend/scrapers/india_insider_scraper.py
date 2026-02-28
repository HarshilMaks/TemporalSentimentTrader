"""India insider/promoter buying scraper via NSE public endpoints.

Scrapes NSE bulk deals, block deals, and insider trading (SAST) disclosures.
Zero credentials — public data from NSE website.
"""
import time
import requests
from datetime import date, timedelta, datetime, timezone
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

# NSE requires a session cookie — hit the homepage first
_BASE = "https://www.nseindia.com"


class IndiaInsiderScraper:
    """Scrapes NSE for bulk deals, block deals, and insider trading disclosures."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        self._cookie_refreshed = False

    def _refresh_cookies(self):
        """Hit NSE homepage to get session cookies (required before API calls)."""
        if self._cookie_refreshed:
            return
        try:
            self.session.get(_BASE, timeout=10)
            self._cookie_refreshed = True
            time.sleep(1)
        except Exception as e:
            logger.warning(f"NSE cookie refresh failed: {e}")

    def fetch_bulk_deals(self, days_back: int = 7) -> list[dict[str, Any]]:
        """Fetch NSE bulk deal data (large volume transactions).

        Returns list of dicts compatible with InsiderTrade model.
        """
        self._refresh_cookies()
        trades: list[dict[str, Any]] = []

        try:
            resp = self.session.get(
                f"{_BASE}/api/historical/bulk-deals",
                params={"from": _date_str(days_back), "to": _date_str(0)},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning(f"NSE bulk deals returned {resp.status_code}")
                return trades

            data = resp.json().get("data", [])
            for row in data:
                qty = _safe_int(row.get("qty"))
                price = _safe_float(row.get("avgPrice"))
                if not qty or not price:
                    continue

                buy_sell = row.get("buySell", "").upper()
                if buy_sell != "BUY":
                    continue

                trades.append({
                    "ticker": row.get("symbol", "").strip(),
                    "insider_name": row.get("clientName", "Unknown"),
                    "insider_title": "Bulk Deal",
                    "transaction_type": "BUY",
                    "shares": qty,
                    "dollar_value": qty * price,  # INR value
                    "transaction_date": _parse_date(row.get("dealDate")),
                    "filing_date": date.today(),
                    "filing_url": f"nse:bulk:{row.get('symbol')}:{row.get('dealDate')}",
                    "source": "NSE",
                })

            logger.info(f"NSE bulk deals: {len(trades)} BUY transactions")

        except Exception as e:
            logger.error(f"NSE bulk deals fetch failed: {e}")

        return trades

    def fetch_block_deals(self) -> list[dict[str, Any]]:
        """Fetch today's NSE block deals (institutional-size transactions)."""
        self._refresh_cookies()
        trades: list[dict[str, Any]] = []

        try:
            resp = self.session.get(f"{_BASE}/api/block-deal", timeout=15)
            if resp.status_code != 200:
                logger.warning(f"NSE block deals returned {resp.status_code}")
                return trades

            data = resp.json().get("data", [])
            for row in data:
                qty = _safe_int(row.get("qty"))
                price = _safe_float(row.get("price"))
                if not qty or not price:
                    continue

                trades.append({
                    "ticker": row.get("symbol", "").strip(),
                    "insider_name": row.get("clientName", "Unknown"),
                    "insider_title": "Block Deal",
                    "transaction_type": "BUY",
                    "shares": qty,
                    "dollar_value": qty * price,
                    "transaction_date": date.today(),
                    "filing_date": date.today(),
                    "filing_url": f"nse:block:{row.get('symbol')}:{date.today()}",
                    "source": "NSE",
                })

            logger.info(f"NSE block deals: {len(trades)} transactions")

        except Exception as e:
            logger.error(f"NSE block deals fetch failed: {e}")

        return trades

    def fetch_all(self, days_back: int = 7) -> list[dict[str, Any]]:
        """Fetch all NSE insider/institutional data."""
        trades = self.fetch_bulk_deals(days_back)
        time.sleep(1)
        trades.extend(self.fetch_block_deals())
        return trades


def _date_str(days_ago: int) -> str:
    d = date.today() - timedelta(days=days_ago)
    return d.strftime("%d-%m-%Y")


def _parse_date(s: str | None) -> date:
    if not s:
        return date.today()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return date.today()


def _safe_int(v: Any) -> int:
    try:
        return int(float(str(v).replace(",", "")))
    except (ValueError, TypeError):
        return 0


def _safe_float(v: Any) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0
