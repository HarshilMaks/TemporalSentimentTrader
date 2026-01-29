"""Background ML tasks for signal generation and monitoring."""
from backend.celery_app import app
from backend.database.config import AsyncSessionLocal
from backend.utils.logger import logger


@app.task(name="backend.tasks.ml_tasks.generate_daily_signals", bind=True)
def generate_daily_signals(self):
    """
    Generate trading signals for all watchlist stocks.
    Runs daily at market open (9:30 AM EST).
    
    NOTE: This is a placeholder until Week 4 when ML models are trained.
    """
    logger.info("Signal generation task triggered (Week 4 implementation pending)")
    
    # TODO Week 4: Implement actual signal generation
    # 1. Fetch latest stock data and sentiment
    # 2. Run feature engineering
    # 3. Run ensemble model (LSTM + XGBoost + LightGBM)
    # 4. Generate signals with confidence > 0.7
    # 5. Save to trading_signals table
    
    return {
        "status": "pending",
        "task_id": self.request.id,
        "message": "ML models not yet trained (Week 4)"
    }


@app.task(name="backend.tasks.ml_tasks.monitor_active_signals", bind=True)
def monitor_active_signals(self):
    """
    Monitor active trading signals and update their status.
    Runs every 5 minutes during market hours.
    
    Checks:
    - If target price reached -> Mark as closed with 'target' reason
    - If stop loss hit -> Mark as closed with 'stop_loss' reason
    - If signal expired -> Mark as closed with 'expired' reason
    """
    import asyncio
    from datetime import datetime, timezone
    from sqlalchemy import select, update
    from backend.models.trading_signal import TradingSignal
    from backend.services.stock_service import StockService
    
    async def _monitor():
        async with AsyncSessionLocal() as session:
            try:
                # Get all active signals
                result = await session.execute(
                    select(TradingSignal).where(TradingSignal.is_active == 1)
                )
                signals = result.scalars().all()
                
                if not signals:
                    logger.info("No active signals to monitor")
                    return {"monitored": 0, "closed": 0}
                
                stock_service = StockService()
                closed_count = 0
                
                for signal in signals:
                    try:
                        # Get current price
                        current_price = await stock_service.get_latest_price(
                            signal.ticker, session
                        )
                        
                        if current_price is None:
                            continue
                        
                        exit_reason = None
                        
                        # Check target reached
                        if signal.target_price and current_price >= signal.target_price:
                            exit_reason = "target"
                        
                        # Check stop loss hit
                        elif signal.stop_loss and current_price <= signal.stop_loss:
                            exit_reason = "stop_loss"
                        
                        # Check expiration
                        elif signal.expires_at and datetime.now(timezone.utc) >= signal.expires_at:
                            exit_reason = "expired"
                        
                        # Close signal if exit condition met
                        if exit_reason:
                            await session.execute(
                                update(TradingSignal)
                                .where(TradingSignal.id == signal.id)
                                .values(
                                    is_active=0,
                                    exit_price=current_price,
                                    exit_reason=exit_reason,
                                    closed_at=datetime.now(timezone.utc)
                                )
                            )
                            closed_count += 1
                            logger.info(
                                f"Closed signal {signal.id} for {signal.ticker}: "
                                f"{exit_reason} at ${current_price:.2f}"
                            )
                    
                    except Exception as e:
                        logger.error(f"Error monitoring signal {signal.id}: {e}")
                        continue
                
                await session.commit()
                
                return {
                    "monitored": len(signals),
                    "closed": closed_count
                }
            
            except Exception as e:
                logger.error(f"Signal monitoring failed: {e}")
                raise
    
    try:
        result = asyncio.run(_monitor())
        return {
            "status": "success",
            "task_id": self.request.id,
            "stats": result
        }
    except Exception as e:
        return {
            "status": "failed",
            "task_id": self.request.id,
            "error": str(e)
        }


@app.task(name="backend.tasks.ml_tasks.train_models")
def train_models(tickers: list = None):
    """
    Train ML models on historical data.
    This is a long-running task (Week 4 implementation).
    
    Args:
        tickers: List of tickers to train on. If None, uses all available data.
    """
    logger.info("Model training task triggered (Week 4 implementation pending)")
    
    # TODO Week 4: Implement model training
    # 1. Fetch training data (stock prices + sentiment)
    # 2. Engineer features
    # 3. Train LSTM, XGBoost, LightGBM models
    # 4. Save model checkpoints to data/models/
    # 5. Log training metrics
    
    return {
        "status": "pending",
        "message": "Model training not yet implemented (Week 4)"
    }
