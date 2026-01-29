"""Background scraping tasks for stock and Reddit data."""
from backend.celery_app import app
from backend.database.config import AsyncSessionLocal
from backend.services.stock_service import StockService
from backend.services.reddit_service import RedditService
from backend.utils.logger import logger
from typing import List


@app.task(name="backend.tasks.scraping_tasks.scrape_reddit_scheduled", bind=True)
def scrape_reddit_scheduled(self):
    """
    Scheduled task to scrape Reddit posts from multiple subreddits.
    Runs every 30 minutes during market hours.
    """
    import asyncio
    
    async def _scrape():
        async with AsyncSessionLocal() as session:
            service = RedditService()
            try:
                stats = await service.scrape_and_save(session)
                logger.info(f"Reddit scraping completed: {stats}")
                return stats
            except Exception as e:
                logger.error(f"Reddit scraping failed: {e}")
                raise
    
    try:
        result = asyncio.run(_scrape())
        return {
            "status": "success",
            "task_id": self.request.id,
            "stats": result
        }
    except Exception as e:
        logger.error(f"Celery task failed: {e}")
        return {
            "status": "failed",
            "task_id": self.request.id,
            "error": str(e)
        }


@app.task(name="backend.tasks.scraping_tasks.fetch_stocks_scheduled", bind=True)
def fetch_stocks_scheduled(self, tickers: List[str] = None):
    """
    Scheduled task to fetch stock data for watchlist tickers.
    Runs every hour during market hours.
    
    Args:
        tickers: List of stock symbols. If None, uses default watchlist.
    """
    import asyncio
    
    # Default watchlist (top 20 trending stocks)
    if tickers is None:
        tickers = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
            "NVDA", "META", "AMD", "NFLX", "DIS",
            "BABA", "INTC", "CSCO", "ADBE", "PYPL",
            "CRM", "ORCL", "UBER", "SPOT", "SQ"
        ]
    
    async def _fetch():
        async with AsyncSessionLocal() as session:
            service = StockService()
            try:
                results = await service.fetch_and_save_multiple(
                    tickers=tickers,
                    db=session,
                    period="1d"  # Fetch latest day only for scheduled updates
                )
                
                success_count = sum(1 for r in results.values() if r['errors'] == 0)
                logger.info(f"Stock fetching completed: {success_count}/{len(tickers)} successful")
                
                return {
                    "total": len(tickers),
                    "successful": success_count,
                    "failed": len(tickers) - success_count,
                    "results": results
                }
            except Exception as e:
                logger.error(f"Stock fetching failed: {e}")
                raise
    
    try:
        result = asyncio.run(_fetch())
        return {
            "status": "success",
            "task_id": self.request.id,
            "stats": result
        }
    except Exception as e:
        logger.error(f"Celery task failed: {e}")
        return {
            "status": "failed",
            "task_id": self.request.id,
            "error": str(e)
        }


@app.task(name="backend.tasks.scraping_tasks.fetch_single_stock")
def fetch_single_stock(ticker: str, period: str = "3mo"):
    """
    On-demand task to fetch a single stock's historical data.
    
    Args:
        ticker: Stock symbol
        period: Historical period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
    """
    import asyncio
    
    async def _fetch():
        async with AsyncSessionLocal() as session:
            service = StockService()
            try:
                result = await service.fetch_and_save_stock_data(ticker, session, period)
                logger.info(f"Fetched {ticker}: {result}")
                return result
            except Exception as e:
                logger.error(f"Failed to fetch {ticker}: {e}")
                raise
    
    try:
        result = asyncio.run(_fetch())
        return {
            "status": "success",
            "ticker": ticker,
            "stats": result
        }
    except Exception as e:
        return {
            "status": "failed",
            "ticker": ticker,
            "error": str(e)
        }
