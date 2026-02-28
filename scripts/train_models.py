#!/usr/bin/env python3
"""One-shot training script for the ML ensemble.

Usage: uv run python scripts/train_models.py
"""
import asyncio
import numpy as np
from pathlib import Path
from backend.database.config import AsyncSessionLocal
from backend.models.stock import StockPrice
from backend.ml.training.train_ensemble import EnsembleTrainer
from backend.ml.models.tft_model import TFTModel
from sqlalchemy import select


async def build_training_data():
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(StockPrice).order_by(StockPrice.ticker, StockPrice.date)
        )).scalars().all()

    by_ticker = {}
    for r in rows:
        by_ticker.setdefault(r.ticker, []).append(r)

    X_list, y_list = [], []
    for ticker, prices in by_ticker.items():
        for i in range(len(prices) - 5):
            r = prices[i]
            ret = (prices[i + 5].close - r.close) / r.close
            label = 0 if ret > 0.03 else (2 if ret < -0.03 else 1)
            X_list.append([
                r.rsi or 50, r.macd or 0, r.macd_signal or 0,
                r.bb_upper or r.close, r.bb_lower or r.close,
                r.sma_50 or r.close, r.sma_200 or r.close,
                r.volume_ratio or 1.0, r.close, r.volume or 0,
                r.high - r.low if r.high and r.low else 0,
            ])
            y_list.append(label)

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int64)


async def main():
    print("Building training data...")
    X, y = await build_training_data()
    print(f"Samples: {len(X)}, Features: {X.shape[1]}")
    print(f"Labels: BUY={sum(y==0)}, HOLD={sum(y==1)}, SELL={sum(y==2)}")

    split = int(len(X) * 0.8)
    save_dir = Path("data/models/ensemble_latest")
    save_dir.mkdir(parents=True, exist_ok=True)

    # XGBoost + LightGBM
    print("\nTraining XGBoost + LightGBM...")
    trainer = EnsembleTrainer()
    trainer.train_ensemble(X[:split], y[:split], X[split:], y[split:], save_dir=save_dir)
    trainer.end_experiment()

    # LSTM
    print("\nTraining LSTM...")
    seq_len = 10
    X_seq = np.array([X[i:i+seq_len] for i in range(len(X) - seq_len)])
    y_seq = np.array([y[i+seq_len] for i in range(len(y) - seq_len)])
    s = int(len(X_seq) * 0.8)
    model = TFTModel(n_features=X.shape[1], hidden=64, seq_length=seq_len)
    model.train(X_seq[:s], y_seq[:s], epochs=15, batch_size=64)
    model.save(str(save_dir / "lstm_model.pt"))

    print(f"\nAll models saved to {save_dir}")
    for f in sorted(save_dir.iterdir()):
        if not f.name.startswith("."):
            print(f"  {f.name} ({f.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
