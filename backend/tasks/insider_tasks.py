"""Celery tasks for insider trade ingestion."""

import asyncio
import logging

from backend.celery_app import app
from backend.database.config import AsyncSessionLocal
from backend.strategy.insider_tracker import InsiderTracker
from backend.models.insider_trade import InsiderTrade

logger = logging.getLogger(__name__)


@app.task(name="backend.tasks.insider_tasks.ingest_insider_trades", bind=True)
def ingest_insider_trades(self, days_back: int = 7):
    """Fetch SEC Form 4 + NSE bulk/block deals and upsert into insider_trades table."""

    async def _ingest():
        tracker = InsiderTracker()
        trades = tracker.fetch_sec_form4(days_back=days_back)

        # Also fetch India NSE deals
        try:
            from backend.scrapers.india_insider_scraper import IndiaInsiderScraper
            india = IndiaInsiderScraper()
            trades.extend(india.fetch_all(days_back=days_back))
        except Exception as e:
            logger.warning(f"India insider fetch failed (non-fatal): {e}")

        if not trades:
            logger.info("No insider trades found")
            return {"inserted": 0, "skipped": 0}

        inserted = 0
        skipped = 0

        async with AsyncSessionLocal() as session:
            for trade_data in trades:
                # Deduplicate by filing_url + shares + transaction_date
                from sqlalchemy import select
                existing = await session.execute(
                    select(InsiderTrade.id).where(
                        InsiderTrade.filing_url == trade_data["filing_url"],
                        InsiderTrade.shares == trade_data.get("shares"),
                        InsiderTrade.transaction_date == trade_data.get("transaction_date"),
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    skipped += 1
                    continue

                record = InsiderTrade(**trade_data)
                session.add(record)
                inserted += 1

            await session.commit()

        logger.info(f"Insider ingestion complete: {inserted} inserted, {skipped} skipped (dupes)")
        return {"inserted": inserted, "skipped": skipped}

    return asyncio.run(_ingest())
