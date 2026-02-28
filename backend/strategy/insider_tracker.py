"""Insider Tracker — fetches SEC Form 4 filings and scores insider activity."""

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

SEC_FULL_INDEX_URL = "https://efts.sec.gov/LATEST/search-index?q=%224%22&dateRange=custom&startdt={start}&enddt={end}&forms=4"
SEC_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4&dateb=&owner=include&count=100&search_text=&action=getcompany&output=atom"
SEC_HEADERS = {"User-Agent": "TFT-Trader/1.0 research@tft-trader.dev", "Accept-Encoding": "gzip, deflate"}

# Title keywords for scoring
C_SUITE = {"ceo", "cfo", "coo", "cto", "chief", "president"}
DIRECTOR = {"director", "dir"}


class InsiderTracker:
    """Fetch SEC Form 4 filings and calculate insider conviction scores."""

    def fetch_sec_form4(self, days_back: int = 7) -> List[Dict]:
        """Scrape recent Form 4 filings from SEC EDGAR full-text search.

        Returns list of dicts ready to be inserted as InsiderTrade rows.
        Only BUY (acquisition) transactions are returned.
        """
        end = date.today()
        start = end - timedelta(days=days_back)
        results: List[Dict] = []

        try:
            filings = self._fetch_filings_list(start, end)
            for filing in filings:
                parsed = self._parse_filing(filing)
                if parsed:
                    results.extend(parsed)
        except Exception as e:
            logger.error(f"SEC Form 4 fetch failed: {e}", exc_info=True)

        logger.info(f"Fetched {len(results)} insider BUY transactions (last {days_back} days)")
        return results

    def _fetch_filings_list(self, start: date, end: date) -> List[Dict]:
        """Get list of recent Form 4 filings from EDGAR full-text search API."""
        url = f"https://efts.sec.gov/LATEST/search-index?q=%224%22&forms=4&dateRange=custom&startdt={start.isoformat()}&enddt={end.isoformat()}"
        try:
            resp = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={
                    "q": '"4"',
                    "forms": "4",
                    "dateRange": "custom",
                    "startdt": start.isoformat(),
                    "enddt": end.isoformat(),
                },
                headers=SEC_HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("hits", {}).get("hits", [])
        except Exception:
            # Fallback: use the EDGAR ATOM feed
            return self._fetch_from_atom_feed()

    def _fetch_from_atom_feed(self) -> List[Dict]:
        """Fallback: parse the EDGAR Atom RSS feed for Form 4."""
        try:
            resp = requests.get(SEC_FEED_URL, headers=SEC_HEADERS, timeout=30)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            results = []
            for entry in entries[:100]:
                link_el = entry.find("atom:link", ns)
                if link_el is not None:
                    results.append({"url": link_el.get("href", "")})
            return results
        except Exception as e:
            logger.error(f"EDGAR Atom feed failed: {e}")
            return []

    def _parse_filing(self, filing: Dict) -> Optional[List[Dict]]:
        """Parse a single Form 4 filing into InsiderTrade dicts.

        Attempts to fetch the XML filing and extract transaction details.
        Returns only BUY (acquisition) transactions.
        """
        filing_url = filing.get("url") or filing.get("_source", {}).get("file_url", "")
        if not filing_url:
            return None

        # Ensure we get the XML version
        if not filing_url.endswith(".xml"):
            return None

        try:
            resp = requests.get(filing_url, headers=SEC_HEADERS, timeout=15)
            resp.raise_for_status()
            return self._parse_form4_xml(resp.content, filing_url)
        except Exception as e:
            logger.debug(f"Could not parse filing {filing_url}: {e}")
            return None

    def _parse_form4_xml(self, xml_content: bytes, filing_url: str) -> List[Dict]:
        """Parse Form 4 XML and extract BUY transactions."""
        trades: List[Dict] = []
        try:
            root = ET.fromstring(xml_content)

            # Issuer (company) info
            issuer = root.find(".//issuer")
            ticker = ""
            if issuer is not None:
                ticker_el = issuer.find("issuerTradingSymbol")
                ticker = ticker_el.text.strip().upper() if ticker_el is not None and ticker_el.text else ""

            if not ticker:
                return []

            # Reporting owner info
            owner = root.find(".//reportingOwner")
            insider_name = ""
            insider_title = ""
            if owner is not None:
                name_el = owner.find(".//rptOwnerName")
                insider_name = name_el.text.strip() if name_el is not None and name_el.text else ""
                title_el = owner.find(".//officerTitle")
                insider_title = title_el.text.strip() if title_el is not None and title_el.text else ""

            # Non-derivative transactions
            for txn in root.findall(".//nonDerivativeTransaction"):
                code_el = txn.find(".//transactionCoding/transactionCode")
                if code_el is None or code_el.text != "P":  # P = Purchase
                    continue

                shares_el = txn.find(".//transactionAmounts/transactionShares/value")
                price_el = txn.find(".//transactionAmounts/transactionPricePerShare/value")
                date_el = txn.find(".//transactionDate/value")

                shares = int(float(shares_el.text)) if shares_el is not None and shares_el.text else 0
                price = float(price_el.text) if price_el is not None and price_el.text else 0.0
                txn_date_str = date_el.text if date_el is not None and date_el.text else None

                if shares <= 0:
                    continue

                txn_date = date.today()
                if txn_date_str:
                    try:
                        txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                trades.append({
                    "ticker": ticker,
                    "insider_name": insider_name,
                    "insider_title": insider_title,
                    "transaction_type": "BUY",
                    "shares": shares,
                    "dollar_value": round(shares * price, 2),
                    "transaction_date": txn_date,
                    "filing_date": date.today(),
                    "filing_url": filing_url,
                    "source": "SEC",
                })

        except ET.ParseError as e:
            logger.debug(f"XML parse error: {e}")

        return trades

    def calculate_insider_score(
        self, insider_trades: List[Dict], lookback_days: int = 30
    ) -> int:
        """Calculate insider conviction score (0-30) for a ticker.

        Args:
            insider_trades: List of InsiderTrade dicts for this ticker
            lookback_days: How far back to look

        Returns:
            Score 0-30.
        """
        if not insider_trades:
            return 0

        cutoff = date.today() - timedelta(days=lookback_days)
        recent_7d = date.today() - timedelta(days=7)

        score = 0
        buyer_count = 0

        for trade in insider_trades:
            txn_date = trade.get("transaction_date")
            if isinstance(txn_date, str):
                txn_date = datetime.strptime(txn_date, "%Y-%m-%d").date()
            if txn_date < cutoff:
                continue
            if trade.get("transaction_type") != "BUY":
                continue

            buyer_count += 1
            title = (trade.get("insider_title") or "").lower()

            if txn_date >= recent_7d:
                # Recent buys score higher
                if any(kw in title for kw in C_SUITE):
                    score = max(score, 30)
                elif any(kw in title for kw in DIRECTOR):
                    score = max(score, 20)
                else:
                    score = max(score, 15)
            else:
                # Older buys within lookback
                if any(kw in title for kw in C_SUITE):
                    score = max(score, 20)
                elif any(kw in title for kw in DIRECTOR):
                    score = max(score, 10)

        # Cluster buying bonus: multiple insiders = stronger conviction
        if buyer_count >= 3:
            score = min(score + 5, 30)

        return score
