# TFT Trader — Post-Sprint Next Steps

The GOD MODE 2-day sprint is complete. The system is built end-to-end and smoke tested. These steps bring it from "built" to "running in production."

---

## Table of Contents

1. [Populate Data](#1-populate-data)
2. [Train the ML Models](#2-train-the-ml-models)
3. [Lower Thresholds for Testing](#3-lower-thresholds-for-testing)
4. [Expand the Watchlist](#4-expand-the-watchlist)
5. [Docker Production Setup](#5-docker-production-setup)
6. [Fix Stale Scripts](#6-fix-stale-scripts)
7. [Clean Up pyproject.toml](#7-clean-up-pyprojecttoml)
8. [Add .dockerignore](#8-add-dockerignore)
9. [Create data/models Directory Structure](#9-create-datamodels-directory-structure)
10. [Frontend Production Build](#10-frontend-production-build)
11. [Logging & Monitoring](#11-logging--monitoring)
12. [Backfill Historical Insider Data](#12-backfill-historical-insider-data)
13. [End-to-End Smoke Test Checklist](#13-end-to-end-smoke-test-checklist)

---

## 1. Populate Data

Before anything else, the database needs real data. Currently: 504 stock rows (4 tickers), 100 stale Reddit posts, 0 insider trades, 0 signals, 0 predictions.

### 1a. Fetch Stock Data for All Watchlist Tickers

```bash
uv run python -c "
import asyncio
from backend.scrapers.stock_scraper import StockScraper

async def fetch():
    scraper = StockScraper()
    tickers = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',
        'NVDA', 'META', 'AMD', 'NFLX', 'DIS',
        'BABA', 'INTC', 'CSCO', 'ADBE', 'PYPL',
        'CRM', 'ORCL', 'UBER', 'SPOT', 'SQ',
    ]
    for t in tickers:
        rows = await scraper.fetch_and_store(t, period='1y')
        print(f'{t}: {rows} rows')

asyncio.run(fetch())
"
```

### 1b. Scrape Reddit Data (Works Without API Credentials)

`RedditService` automatically falls back to `MockRedditScraper` when Reddit API
credentials are missing or invalid. No code changes needed — just run:

```bash
uv run python -c "
import asyncio
from backend.services.reddit_service import RedditService
from backend.database.config import AsyncSessionLocal

async def scrape():
    service = RedditService()
    print(f'Using mock: {service.using_mock}')
    async with AsyncSessionLocal() as session:
        stats = await service.scrape_and_save(session, limit=100)
        print(f'{stats[\"saved\"]} saved, {stats[\"skipped\"]} skipped')

asyncio.run(scrape())
"
```

The mock generates posts with varied bullish/bearish/neutral sentiment across all
20 watchlist tickers. When Reddit eventually approves your API access, just set
`REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `.env` — the system switches to
real data automatically with zero code changes.

### 1c. Ingest SEC Form 4 Insider Trades

```bash
uv run python -c "
import asyncio
from backend.strategy.insider_tracker import InsiderTracker
from backend.database.config import AsyncSessionLocal

async def ingest():
    tracker = InsiderTracker()
    trades = await tracker.fetch_sec_form4(days_back=30)
    print(f'Fetched {len(trades)} insider trades from SEC EDGAR')

    async with AsyncSessionLocal() as session:
        for trade in trades:
            session.add(trade)
        await session.commit()
        print(f'Stored {len(trades)} trades')

asyncio.run(ingest())
"
```

### 1d. Verify Data Populated

```bash
uv run python -c "
import asyncio
from sqlalchemy import func, select
from backend.database.config import AsyncSessionLocal
from backend.models.stock import StockPrice
from backend.models.reddit import RedditPost
from backend.models.insider_trade import InsiderTrade
from backend.models.trading_signal import TradingSignal
from backend.models.prediction import Prediction

async def check():
    async with AsyncSessionLocal() as s:
        for model, name in [
            (StockPrice, 'stock_prices'),
            (RedditPost, 'reddit_posts'),
            (InsiderTrade, 'insider_trades'),
            (TradingSignal, 'trading_signals'),
            (Prediction, 'predictions'),
        ]:
            count = (await s.execute(select(func.count()).select_from(model))).scalar()
            print(f'{name}: {count} rows')

asyncio.run(check())
"
```

---

## 2. Train the ML Models

The ensemble returns HOLD with 0.333 confidence for everything because no model has been trained. All training scripts exist.

### 2a. Build Feature Snapshots

```bash
uv run python -c "
import asyncio
from backend.ml.features.build import FeatureBuilder

async def build():
    fb = FeatureBuilder()
    snapshots = await fb.build_all_snapshots()
    print(f'Built {len(snapshots)} feature snapshots')

asyncio.run(build())
"
```

### 2b. Train the Ensemble

`EnsembleTrainer` trains XGBoost + LightGBM with MLflow logging. TFT/LSTM trains separately via `TFTTrainer`.

```bash
# Train XGBoost + LightGBM
uv run python -c "
from backend.ml.training.train_ensemble import EnsembleTrainer
from backend.ml.features.build import FeatureBuilder
import asyncio, numpy as np

async def main():
    fb = FeatureBuilder()
    snapshots = await fb.build_all_snapshots()

    X = np.array([s['features'] for s in snapshots])
    y = np.array([s['label'] for s in snapshots])  # 0=BUY, 1=HOLD, 2=SELL

    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    trainer = EnsembleTrainer()
    results = trainer.train_ensemble(X_train, y_train, X_test, y_test)
    trainer.end_experiment()
    print('Done. Models saved to data/models/')

asyncio.run(main())
"
```

### 2c. Where Models Get Saved

The `Predictor` loads from `data/models/ensemble_latest/`:

```
data/models/ensemble_latest/
├── xgboost_model.json
├── lightgbm_model.txt
└── lstm_model.pt        (if LSTM trained)
```

Create this directory before training:

```bash
mkdir -p data/models/ensemble_latest
```

### 2d. Retraining Cadence

Retrain weekly or after accumulating 2+ weeks of new data. The models degrade as market conditions shift. A simple cron or manual trigger is fine for now.

---

## 3. Lower Thresholds for Testing

With sparse data and untrained models, nothing passes the production gates. Lower them temporarily to verify the full pipeline flows.

### 3a. Triangulation Score Threshold

File: `backend/strategy/signal_engine.py`, line 203:

```python
# Production:
if tri.total_score < 60:
    return None

# Testing — change to:
if tri.total_score < 20:
    return None
```

### 3b. ML Confidence Threshold

File: `backend/strategy/signal_engine.py`, line 230:

```python
# Production:
if result["signal"] != "BUY" or result["confidence"] < 0.7:
    return None

# Testing — change to:
if result["signal"] != "BUY" or result["confidence"] < 0.3:
    return None
```

File: `backend/ml/models/ensemble.py`, line 17:

```python
# Production:
CONFIDENCE_THRESHOLD = 0.70

# Testing — change to:
CONFIDENCE_THRESHOLD = 0.30
```

### 3c. Test Signal Generation

```bash
uv run python -c "
import asyncio
from backend.strategy.signal_engine import SignalEngine

async def test():
    engine = SignalEngine()
    signals = await engine.generate_signals()
    print(f'Generated {len(signals)} signals')
    for s in signals:
        print(f'  {s.ticker}: {s.signal.value} @ \${s.entry_price:.2f} '
              f'(conf={s.confidence:.2f}, R/R={s.risk_reward_ratio:.1f})')

asyncio.run(test())
"
```

### 3d. Restore Production Thresholds

After verifying signals flow, revert all three changes back to production values (60, 0.7, 0.70).

---

## 4. Expand the Watchlist

The default 20 tickers are mega-cap tech-heavy. Insider trading signals are more meaningful in mid-caps where information asymmetry is higher.

### Current Watchlist

File: `backend/strategy/signal_engine.py`, line 28:

```python
DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "AMD", "NFLX", "DIS",
    "BABA", "INTC", "CSCO", "ADBE", "PYPL",
    "CRM", "ORCL", "UBER", "SPOT", "SQ",
]
```

### Suggested Additions

```python
DEFAULT_WATCHLIST = [
    # Mega-cap tech (existing)
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "AMD", "NFLX", "DIS",
    "BABA", "INTC", "CSCO", "ADBE", "PYPL",
    "CRM", "ORCL", "UBER", "SPOT", "SQ",
    # Financials (insider buying common)
    "JPM", "BAC", "GS", "MS", "C",
    # Healthcare / Biotech (high insider signal value)
    "JNJ", "PFE", "MRNA", "ABBV", "BMY",
    # Energy
    "XOM", "CVX", "OXY", "SLB",
    # Industrials
    "CAT", "DE", "BA", "RTX",
    # Mid-cap tech (higher info asymmetry)
    "CRWD", "DDOG", "NET", "ZS", "SNOW",
    "PLTR", "RBLX", "U", "COIN", "HOOD",
]
```

After expanding, fetch data for new tickers (same command as Step 1a with the new ticker list).

Performance note: ~2-3 seconds per ticker during signal generation. 50 tickers ≈ 2-3 minutes. Fine for EOD batch.

---

## 5. Docker Production Setup

The current `docker-compose.yml` runs Celery worker + beat + Flower but is missing the API server and frontend.

### 5a. Add API Server to docker-compose.yml

Add this service block to `docker-compose.yml` under `services:`:

```yaml
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    container_name: tft-api
    command: python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - PYTHONUNBUFFERED=1
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    networks:
      - tft-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### 5b. Add Frontend to docker-compose.yml (Optional)

For production, build the Next.js app and serve it:

```yaml
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: tft-frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    networks:
      - tft-network
    restart: unless-stopped
    depends_on:
      - api
```

This requires a `frontend/Dockerfile` (see Step 10).

### 5c. Alembic Directory Missing from Dockerfile

The Dockerfile copies `backend/`, `scripts/`, `alembic.ini`, `pyproject.toml` — but NOT the `alembic/` directory. Migrations won't run inside the container.

Add to both `development` and `production` stages in `Dockerfile`:

```dockerfile
COPY alembic/ ./alembic/
```

Right after the existing `COPY alembic.ini ./` line.

### 5d. Run Migrations on Startup

Add a one-shot migration service or run before starting:

```bash
docker compose run --rm api alembic upgrade head
```

---

## 6. Fix Stale Scripts

Several files in `scripts/` are empty (0 bytes) or outdated from the pre-Triangulation architecture:

| File | Status | Action |
|------|--------|--------|
| `scripts/train_models.py` | Empty (0 bytes) | Write a working training script |
| `scripts/backtest.py` | Empty (0 bytes) | Write or delete |
| `scripts/query_db.py` | Empty (0 bytes) | Write or delete |
| `scripts/scrape_reddit.py` | Empty (0 bytes) | Write or delete |
| `scripts/scheduled_scraper.py` | 152 lines | Outdated — Celery beat handles this now. Delete or archive |
| `scripts/setup.sh` | 105 lines | Review — may reference old structure |
| `scripts/verify_docker_setup.sh` | 255 lines | Review — may reference old structure |

### Recommended: Write `scripts/train_models.py`

```python
#!/usr/bin/env python3
"""One-shot training script for the ML ensemble."""
import asyncio
import numpy as np
from pathlib import Path
from backend.ml.features.build import FeatureBuilder
from backend.ml.training.train_ensemble import EnsembleTrainer

async def main():
    print("Building feature snapshots...")
    fb = FeatureBuilder()
    snapshots = await fb.build_all_snapshots()
    if not snapshots:
        print("No snapshots built. Populate stock data first.")
        return

    X = np.array([s["features"] for s in snapshots])
    y = np.array([s["label"] for s in snapshots])
    print(f"Training on {len(X)} samples, {X.shape[1]} features")

    split = int(len(X) * 0.8)
    trainer = EnsembleTrainer()
    Path("data/models/ensemble_latest").mkdir(parents=True, exist_ok=True)
    trainer.train_ensemble(X[:split], y[:split], X[split:], y[split:])
    trainer.end_experiment()
    print("Done. Models saved to data/models/")

if __name__ == "__main__":
    asyncio.run(main())
```

Run with: `uv run python scripts/train_models.py`

---

## 7. Clean Up pyproject.toml

The `pyproject.toml` has stale metadata and unused dependencies from the pre-Triangulation era:

### 7a. Update Project Metadata

```toml
[project]
name = "tft-trader"
version = "1.0.0"
description = "Triangulation Swing Trading Platform — Legal Insider Trading via Information Arbitrage"
```

### 7b. Remove Unused Auth Dependencies

These were for the auth system we skipped:

```
python-jose[cryptography]>=3.3.0    # JWT — not used
passlib[bcrypt]>=1.7.4              # password hashing — not used
```

### 7c. Remove pytorch-forecasting

```
pytorch-forecasting>=1.0.0    # Not used — we use raw LSTM, not the TFT library
```

This is a heavy dependency that pulls in many sub-packages. The `TFTModel` in `backend/ml/models/tft_model.py` uses plain PyTorch LSTM, not the pytorch-forecasting library.

---

## 8. Add .dockerignore

There's no `.dockerignore` file. Without it, Docker copies everything (including `.git/`, `node_modules/`, `.venv/`, `data/`) into the build context, making builds slow and images bloated.

Create `.dockerignore`:

```
.git
.gitignore
.env
.env.*
.venv
venv
__pycache__
*.pyc
.pytest_cache
.ruff_cache
htmlcov
.coverage

# Frontend (built separately)
frontend/node_modules
frontend/.next
frontend/out

# Data (mounted as volumes, not baked into image)
data/
mlruns/
mlartifacts/
logs/

# Docs
docs/
*.md
LICENSE

# IDE
.vscode
.idea
.qodo
.kiro
```

---

## 9. Create data/models Directory Structure

The `Predictor` expects `data/models/ensemble_latest/` but it doesn't exist. Create it with `.gitkeep` files:

```bash
mkdir -p data/models/ensemble_latest
touch data/models/ensemble_latest/.gitkeep
```

Also update `.gitignore` — currently it ignores `*.json` and `*.txt` model files but not the `ensemble_latest/` directory pattern. The current rules are fine; just make sure `.gitkeep` files are committed.

---

## 10. Frontend Production Build

The frontend runs in dev mode (`npm run dev`). For production:

### 10a. Create `frontend/Dockerfile`

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

### 10b. Enable Standalone Output

Add to `frontend/next.config.ts`:

```typescript
output: 'standalone',
```

### 10c. Build and Run

```bash
cd frontend
npm run build        # Creates .next/standalone
npm run start        # Production server on :3000
```

---

## 11. Logging & Monitoring

### 11a. Structured Logging

The backend uses Python's `logging` module but output is unstructured. For production, consider adding to `backend/api/main.py`:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
```

### 11b. Flower Dashboard

Already configured in docker-compose at `http://localhost:5555`. Use it to monitor:
- Task success/failure rates
- Queue depths
- Worker status

### 11c. Health Check Endpoint

Already exists at `GET /health` returning `{"status":"healthy","database":"connected"}`. Wire this into your monitoring (uptime checks, Docker healthcheck, etc.).

---

## 12. Backfill Historical Insider Data

The SEC EDGAR scraper defaults to `days_back=7`. For training, you want months of insider data:

```bash
uv run python -c "
import asyncio
from backend.strategy.insider_tracker import InsiderTracker
from backend.database.config import AsyncSessionLocal

async def backfill():
    tracker = InsiderTracker()
    # Fetch 90 days of insider trades
    trades = await tracker.fetch_sec_form4(days_back=90)
    print(f'Fetched {len(trades)} insider trades')

    async with AsyncSessionLocal() as session:
        for trade in trades:
            session.add(trade)
        await session.commit()
        print(f'Stored {len(trades)} trades')

asyncio.run(backfill())
"
```

Note: SEC EDGAR rate limits to 10 requests/second. The scraper respects this, but 90 days of data may take a few minutes.

---

## 13. End-to-End Smoke Test Checklist

Run through this after completing the steps above to verify everything works:

```
[ ] .env file exists with all credentials filled in
[ ] Database migrations applied: uv run alembic upgrade head
[ ] Stock data: 20+ tickers × 250+ rows each
[ ] Reddit data: 100+ recent posts with sentiment scores
[ ] Insider data: 50+ trades from last 90 days
[ ] ML models trained and saved to data/models/ensemble_latest/
[ ] API server starts: uv run uvicorn backend.api.main:app --port 8000
[ ] Health check passes: curl http://localhost:8000/health
[ ] GET /api/v1/stocks/prices/AAPL returns data
[ ] GET /api/v1/sentiment/trending returns tickers
[ ] GET /api/v1/sentiment/insider/AAPL returns trades
[ ] GET /api/v1/predictions/latest returns predictions (not empty after training)
[ ] POST /api/v1/predictions/run triggers Celery task
[ ] GET /api/v1/signals/active returns signals (after lowering thresholds or with trained models)
[ ] Frontend starts: cd frontend && npm run dev
[ ] Dashboard loads at http://localhost:3000
[ ] Ticker detail page loads: http://localhost:3000/ticker/AAPL
[ ] Signals page loads: http://localhost:3000/signals
[ ] Celery worker starts: celery -A backend.celery_app worker --queues=scraping,ml
[ ] Celery beat starts: celery -A backend.celery_app beat
[ ] Docker compose up works: docker compose up -d
[ ] Flower UI accessible: http://localhost:5555
```

---

## Recommended Order of Execution

| Step | What | Why First |
|------|------|-----------|
| 8 | Add `.dockerignore` | 10 seconds, prevents bloated Docker builds |
| 9 | Create `data/models/` dirs | 5 seconds, prevents runtime errors |
| 7 | Clean `pyproject.toml` | Remove dead deps before any installs |
| 1 | Populate data | Everything else depends on having data |
| 12 | Backfill insider data | Needed for meaningful triangulation scores |
| 3 | Lower thresholds + test | Verify pipeline flows before training |
| 2 | Train ML models | Needs accumulated data |
| 6 | Fix scripts | Write `train_models.py` for repeatable training |
| 4 | Expand watchlist | After pipeline is proven working |
| 5 | Docker production setup | Add API service, fix Dockerfile |
| 10 | Frontend production build | Standalone Next.js for deployment |
| 11 | Logging & monitoring | Polish for production |
| 13 | Full smoke test | Final verification |
