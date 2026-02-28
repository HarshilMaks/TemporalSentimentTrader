# TFT Trader — Complete System Analysis Document

**Generated:** 2026-02-28 19:01 UTC
**Author:** Kiro (AI Architect) + Harshil (Owner/Operator)
**Version:** 1.0.0 — Post-Refactor, Pre-Production

---

## Table of Contents

1. [What This System Is](#1-what-this-system-is)
2. [What This System Is NOT](#2-what-this-system-is-not)
3. [The Trading Mathematics](#3-the-trading-mathematics)
4. [System Architecture — The Sequential Pipeline](#4-system-architecture)
5. [Data Ingestion Layer — Every Source Explained](#5-data-ingestion-layer)
6. [The 5 Gates — How a Signal Gets Born](#6-the-5-gates)
7. [Machine Learning Pipeline](#7-machine-learning-pipeline)
8. [Database Schema & Current State](#8-database-schema)
9. [API Layer — Every Endpoint](#9-api-layer)
10. [Celery Task Scheduler](#10-celery-task-scheduler)
11. [Frontend Dashboard](#11-frontend-dashboard)
12. [Infrastructure & Deployment](#12-infrastructure)
13. [Complete File Map — Every File Explained](#13-file-map)
14. [Bug Fix History — All 29 Bugs](#14-bug-fix-history)
15. [What Is Done (Complete)](#15-what-is-done)
16. [What Is NOT Done (Remaining Work)](#16-what-is-not-done)
17. [Known Limitations & Honest Assessment](#17-known-limitations)
18. [Production Checklist](#18-production-checklist)

---

## 1. What This System Is

TFT Trader is an **End-of-Day (EOD) Signal Generator** that runs entirely on a local laptop. It acts as a junior quantitative analyst:

- Wakes up every morning (7:30 AM IST / 2:00 AM UTC)
- Ingests data from 5 independent sources (SEC, NSE, yfinance, Reddit, RSS)
- Scores every stock in a 35-ticker watchlist across 4 dimensions
- Validates survivors through an ML ensemble
- Applies strict risk management rules
- Sends a Telegram message to your phone with exact entry/stop/target
- You copy those 3 numbers into your broker app. No analysis. Just execute.

The system covers **two markets**: US (NYSE/NASDAQ) and India (NSE).

**Total cost to run: ₹0/month.** All data sources are free. Database and cache use free tiers. Compute is local.

---

## 2. What This System Is NOT

- **NOT an auto-trading bot.** It never connects to a brokerage. It never places orders.
- **NOT a price predictor.** The ML models don't predict where a stock will go. They validate whether a triangulation signal has enough momentum to succeed.
- **NOT an HFT system.** It runs once per day, after market close. Holds are 3-7 days.
- **NOT a magic money printer.** 55% of trades will lose. The edge comes from the 1:2 risk/reward ratio, not from prediction accuracy.

---

## 3. The Trading Mathematics

```
Win rate:     45% (we expect to lose 55% of trades)
Average win:  +10% (take profit target)
Average loss: -5%  (stop loss)

Expected Value per trade:
  EV = (0.45 × 10%) - (0.55 × 5%)
  EV = 4.5% - 2.75%
  EV = +1.75% per trade

Over 100 trades:
  100 × 1.75% = +175% cumulative return

The edge is NOT prediction accuracy.
The edge is the 1:2 Risk/Reward ratio.
Even a coin flip (50/50) with 1:2 R/R is profitable.
```

### Risk Rules (Hardcoded, Non-Negotiable)

| Rule | Value | Why |
|------|-------|-----|
| Stop Loss | -5% from entry | Caps maximum loss per trade |
| Take Profit | +10% from entry | 2x the risk = positive expected value |
| Position Size | 2% of portfolio | Single trade can't destroy the portfolio |
| Max Positions | 5 concurrent | Prevents over-diversification |
| Max Drawdown | 15% of portfolio | Circuit breaker — stops all trading |
| Min Confidence | 70% from ML | Only high-conviction signals pass |
| Min Triangulation | 60/100 | At least 2-3 data layers must align |

---

## 4. System Architecture

### Deployment Model (₹0 Hybrid-Local Stack)

```
┌─────────────────────────────────────────────────────────────┐
│  LOCAL (Lenovo Legion laptop via Docker)                    │
│                                                             │
│  FastAPI API server (:8000)                                 │
│  Celery Worker (scraping + ml queues)                       │
│  Celery Beat (scheduler)                                    │
│  Flower (:5555) — task monitoring                           │
│  Next.js Dashboard (:3000) — optional, verification only    │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│  CLOUD (free tiers only)                                    │
│                                                             │
│  PostgreSQL — Neon (free tier, 0.5 GB)                      │
│  Redis — Redis Cloud (free tier, 30 MB)                     │
│  Telegram Bot API — free, unlimited                         │
└─────────────────────────────────────────────────────────────┘
```

### The Sequential Pipeline (Core Design Principle)

Data flows through increasingly strict gates. Each gate reduces the candidate set. ML only evaluates stocks that already passed the fundamental screen.

```
35 tickers → Regime → Triangulation (≥60) → ML (≥70%) → Risk → Telegram
   35          35        typically 0-3        0-2         0-1     0-1
```

This is the exact architecture used by prop-trading desks. ML is a **validator**, not a **discoverer**.

---

## 5. Data Ingestion Layer

All sources are free. Zero API keys required for any of them.

### US Market Sources

| Source | File | Method | Schedule | Output |
|--------|------|--------|----------|--------|
| SEC EDGAR | `backend/strategy/insider_tracker.py` | HTTP GET → Form 4 XML parsing | Daily 2:00 AM UTC | `insider_trades` table |
| yfinance | `backend/scrapers/stock_scraper.py` | yfinance Python library | Hourly | `stock_prices` table (OHLCV + 8 indicators) |
| Reddit | `backend/scrapers/reddit_json_scraper.py` | `reddit.com/r/{sub}/hot.json` with rotating User-Agents | Every 30 min | `reddit_posts` table |

**Reddit .json backdoor:** Instead of using PRAW (which requires API keys and got denied), we hit the public `.json` endpoint directly. `https://www.reddit.com/r/wallstreetbets/hot.json` returns the same data as the API. Rotating User-Agents prevent blocks. 2-second rate limit between requests.

**SEC EDGAR:** Parses Form 4 XML filings from the EDGAR full-text search index. Extracts insider name, title, transaction type, shares, dollar value. 150ms delay between requests to respect SEC's 10 req/sec limit.

### India Market Sources

| Source | File | Method | Schedule | Output |
|--------|------|--------|----------|--------|
| NSE Bulk/Block Deals | `backend/scrapers/india_insider_scraper.py` | NSE public JSON API | Daily 2:00 AM UTC | `insider_trades` table |
| RSS Feeds | `backend/scrapers/india_rss_scraper.py` | feedparser on 5 RSS feeds | Every 30 min | `reddit_posts` table |
| yfinance (NSE) | `backend/scrapers/stock_scraper.py` | yfinance with `.NS` suffix | Hourly | `stock_prices` table |

**RSS Feeds parsed:** NDTV News, Economic Times Markets, Moneycontrol Market Reports, Moneycontrol Results, Yahoo Finance. Articles are matched against 30 NSE tickers via company name mapping (e.g., "Reliance" → RELIANCE, "SBI" → SBIN).

**Important limitation:** RSS feeds are institutional news, not retail hype. For India, Layer 1 (NSE block deals) and Layer 2 (volume) carry more weight than Layer 3 (sentiment). True retail hype requires Telegram group scraping via Telethon (future work).

### Watchlist (35 tickers)

**US (20):** AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, AMD, NFLX, DIS, BABA, INTC, CSCO, ADBE, PYPL, CRM, ORCL, UBER, SPOT, COIN

**India (15):** RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, ICICIBANK.NS, SBIN.NS, BHARTIARTL.NS, KOTAKBANK.NS, LT.NS, AXISBANK.NS, TATAMOTORS.NS, TATASTEEL.NS, BAJFINANCE.NS, TITAN.NS, ITC.NS

The `.NS` suffix is required by yfinance to fetch NSE data instead of US OTC equivalents.

---

## 6. The 5 Gates — How a Signal Gets Born

### Gate 1: Regime Filter

**File:** `backend/strategy/regime_filter.py` (44 lines)

Checks if SPY close > SMA200. If the broad market is in a downtrend (BEAR), the entire pipeline stops. No signals are generated in bear markets. This prevents buying into a falling market.

### Gate 2: Triangulation Scoring

**File:** `backend/strategy/signal_engine.py` → `calculate_triangulation_score()`

Every ticker is scored across 4 independent dimensions:

**Layer 1 — Insider Buying (0-30 points)**
- CEO/CFO purchase in last 30 days: 30 points
- Director purchase: 20 points
- Cluster of multiple insiders: +5 bonus
- Source: SEC Form 4 (US) + NSE bulk/block deals (India)
- Why it matters: Insiders know more than anyone. When they buy with their own money, it's the strongest signal.

**Layer 2 — Volume Flow (0-20 points)**
- Volume ratio > 2.0x (20-day average): 20 points
- Volume ratio > 1.5x: 10 points
- Source: yfinance OHLCV data
- Why it matters: Unusual volume = institutional accumulation. Smart money moves before news.

**Layer 3 — Retail Hype (0-20 points)**
- Average sentiment > 0.3 AND mention count > 20 in 7 days: 20 points
- Average sentiment > 0.3 (fewer mentions): 10 points
- Source: Reddit posts (US) + RSS articles (India)
- Sentiment: VADER analyzer with custom stock market lexicon (moon=4.0, crash=-3.5, etc.)
- Why it matters: Retail momentum amplifies institutional moves.

**Technicals (0-30 points)**
- RSI < 35 (oversold): 10 points
- MACD > MACD signal (bullish crossover): 10 points
- Close > SMA50 (uptrend): 10 points
- Source: pandas-ta indicators computed on stock_prices
- Why it matters: Technical confirmation that the stock is at a favorable entry point.

**Threshold: Total score ≥ 60 to pass.** This means at minimum 2-3 independent layers must align. A stock with only good technicals (30) won't pass. A stock with insider buying (30) + volume spike (20) + weak technicals (10) = 60 → passes.

### Gate 3: ML Ensemble Validation

**Files:** `backend/ml/models/ensemble.py`, `backend/ml/inference/predictor.py`

Only tickers that passed triangulation (typically 0-3 out of 35) reach the ML models. The ensemble answers: **"Given that triangulation flagged this stock, what is the probability this signal will succeed?"**

| Model | Weight | File | Size |
|-------|--------|------|------|
| XGBoost | 40% | `xgboost_model.pkl` | 972 KB |
| LightGBM | 30% | `lightgbm_model.pkl` | 760 KB |
| LSTM | 30% | `lstm_model.pt` | 219 KB |

Weighted probability averaging across 3 classes (BUY/HOLD/SELL).

**Threshold: BUY + confidence ≥ 0.70 to pass.**

**Known limitation (Dataset Shift):** Current models were trained on all stock data predicting 5-day forward returns. They should be retrained on triangulation survivors only, after 2 months of data accumulation. The 0.70 threshold compensates for this miscalibration.

### Gate 4: Risk Manager

**File:** `backend/services/risk_manager.py` (488 lines)

5 sequential validation rules. If any fails, the signal is rejected:

1. **Confidence ≥ 70%** — quality gate
2. **Price levels valid** — entry < target, entry > stop, all positive
3. **Risk/Reward ≥ 1:2** — stop=-5%, target=+10%
4. **Position size** — max 2% risk per trade, max 20% of portfolio
5. **Portfolio constraints** — max 5 concurrent positions, max 15% drawdown

The risk manager is the final safety gate. Even if triangulation + ML both say BUY, risk can reject.

### Gate 5: Telegram Alert

**File:** `backend/services/telegram_notifier.py`

Approved signals are immediately pushed to Telegram:

```
🚨 TRIANGULATION BUY SIGNAL

Ticker: $NVDA
Confidence: 82%

Action: BUY at Market Open
Entry: $142.50
Take Profit: $156.75 (+10%)
Stop Loss: $135.38 (-5%)
R/R: 1:2.0

Position Size: 2% ($2,000)
Expires: 2026-03-07

Copy entry, stop, target into broker. Do not analyze. Execute.
```

Uses raw HTTP POST to Telegram Bot API. No library. Gracefully returns False when credentials aren't configured.

---

## 7. Machine Learning Pipeline

### Training Data

- **Source:** 4,769 stock price rows across 19 US tickers (1 year each)
- **Features (11):** RSI, MACD, MACD signal, BB upper, BB lower, SMA50, SMA200, volume ratio, close, volume, high-low range
- **Labels:** 5-day forward return > +3% = BUY (1,240 samples), < -3% = SELL (1,113), else HOLD (2,321)
- **Split:** 80/20 train/test
- **Saved:** `data/X_train.npy` (4674, 11), `data/y_train.npy` (4674,)

### Models

| Model | Type | Objective | Key Params |
|-------|------|-----------|------------|
| XGBoost | `XGBClassifier` | `multi:softprob` (3-class) | 100 estimators, max_depth=6 |
| LightGBM | `LGBMClassifier` | `multiclass` | 100 estimators, 31 leaves |
| LSTM | PyTorch `nn.Module` | CrossEntropyLoss (3-class) | 2 layers, 64 hidden, seq_len=10 |

### Training Script

```bash
uv run python scripts/train_models.py
```

Builds data from DB → trains all 3 models → saves to `data/models/ensemble_latest/`.

### MLOps (Built but Frozen)

The following are built and functional but frozen until data pipes are proven:
- MLflow tracking (`backend/ml/tracking/mlflow_logger.py`)
- Model registry (`backend/ml/registry/model_registry.py`)
- Experiment comparison (`backend/ml/tracking/experiment_compare.py`)
- Feature importance tracking (`backend/ml/features/importance.py`)
- Backtesting engine (`backend/ml/backtesting/backtest_engine.py`)

---

## 8. Database Schema

PostgreSQL hosted on Neon (free tier, 0.5 GB). 6 tables, 12 Alembic migrations.

### stock_prices (4,769 rows)

| Column | Type | Description |
|--------|------|-------------|
| ticker | String(10) | Stock symbol (e.g., AAPL, RELIANCE.NS) |
| open_price, high, low, close | Float | OHLC prices |
| adjusted_close | Float | Split/dividend adjusted |
| volume | BigInteger | Daily volume |
| rsi | Float | Relative Strength Index (14-period) |
| macd, macd_signal | Float | MACD line and signal line |
| bb_upper, bb_lower | Float | Bollinger Bands (20,2) |
| sma_50, sma_200 | Float | Simple Moving Averages |
| volume_ratio | Float | Current volume / 20-day average |
| date | DateTime(tz) | Trading date |

Unique constraint: `(ticker, date)`. Index: `idx_ticker_date`.

### insider_trades (112 rows)

| Column | Type | Description |
|--------|------|-------------|
| ticker | String(10) | Stock symbol |
| insider_name | String(200) | Name of insider |
| insider_title | String(100) | CEO, CFO, Director, Bulk Deal, Block Deal |
| transaction_type | String(10) | BUY or SELL |
| shares | BigInteger | Number of shares |
| dollar_value | Float | Total transaction value |
| transaction_date | Date | When the trade happened |
| filing_url | String(500) | SEC filing URL or NSE deal ID |
| source | String(10) | SEC or NSE |

Index: `idx_insider_ticker_date`, `idx_insider_filing_url`.

### reddit_posts (32 rows — 22 Reddit + 10 India RSS)

| Column | Type | Description |
|--------|------|-------------|
| post_id | String(50) | Unique post identifier |
| subreddit | String(50) | Subreddit name or `rss:Source Name` |
| title, body | Text | Post content |
| score | Integer | Upvotes |
| num_comments | Integer | Comment count |
| upvote_ratio | Float | 0.0-1.0 |
| tickers | ARRAY(String) | Extracted stock tickers |
| sentiment_score | Numeric(5,4) | VADER compound score (-1 to +1) |
| quality_score | Float | 0-100 quality assessment |
| quality_tier | String(20) | poor/fair/good/excellent |
| is_quality | Boolean | True if quality_score ≥ 50 |

GIN index on `tickers` array. Composite index on `(is_quality, created_at)`.

### trading_signals (8 rows)

| Column | Type | Description |
|--------|------|-------------|
| ticker | String(10) | Stock symbol |
| signal | Enum | BUY, SELL, HOLD |
| confidence | Float | 0.0-1.0 ML confidence |
| entry_price | Float | Recommended entry |
| target_price | Float | +10% take profit |
| stop_loss | Float | -5% stop loss |
| risk_reward_ratio | Float | Target gain / stop distance |
| position_size_pct | Float | % of portfolio |
| is_active | Integer | 1=active, 0=closed |
| exit_price | Float | Actual exit price (when closed) |
| exit_reason | String(50) | target, stop_loss, expired |

### predictions (0 rows)

Stores ML ensemble predictions. Populated on-demand via `/api/v1/predictions/run`.

### feature_snapshots (0 rows)

Stores feature engineering snapshots for training reproducibility.

---

## 9. API Layer

FastAPI application with 30 routes across 5 route files + health/docs.

**Base URL:** `http://localhost:8000`

### Signal Routes (`/api/v1/signals/`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/active` | All signals where is_active=1 |
| GET | `/history?limit=50` | Closed signals with exit price/reason |
| GET | `/ticker/{ticker}` | Signals for a specific stock |
| GET | `/daily-report` | Today's generated signals |
| POST | `/{signal_id}/close` | Manually close a signal with exit price |

### Prediction Routes (`/api/v1/predictions/`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/latest` | Latest prediction per ticker |
| GET | `/ticker/{ticker}?limit=30` | Prediction history |
| POST | `/run` | Trigger manual prediction run (Celery task) |

### Sentiment Routes (`/api/v1/sentiment/`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/trending?days=7&limit=20` | Top tickers by mention count + avg sentiment |
| GET | `/ticker/{ticker}?days=30` | Daily sentiment aggregates |
| GET | `/insider/{ticker}?days=90` | Insider trading activity |

### Stock Routes (`/api/v1/stocks/`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/prices/{ticker}` | Historical OHLCV + indicators |
| GET | `/latest/{ticker}` | Most recent price |
| GET | `/signals/{ticker}` | Momentum signals (RSI, MACD) |
| GET | `/health` | Stock data freshness |
| POST | `/fetch/{ticker}` | Trigger stock data fetch |
| POST | `/fetch/batch` | Fetch multiple tickers |

### Post Routes (`/api/v1/posts/`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Paginated posts (Reddit + India RSS) |
| GET | `/ticker/{ticker}` | Posts mentioning a ticker |
| GET | `/trending` | Most mentioned tickers |
| GET | `/sentiment/{ticker}` | Aggregate sentiment for ticker |
| GET | `/analytics/quality` | Quality scoring analytics |
| POST | `/scrape/{subreddit}` | Trigger manual scrape |

### Infrastructure Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | DB + Redis + rate limiter status |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |

---

## 10. Celery Task Scheduler

8 scheduled tasks across 2 queues.

### Daily Schedule (IST-Friendly)

| UTC Time | IST Time | Task | Queue | What It Does |
|----------|----------|------|-------|-------------|
| Every 30 min | — | `scrape_reddit_scheduled` | scraping | Reddit JSON + India RSS → DB |
| Every hour | — | `fetch_stocks_scheduled` | scraping | yfinance OHLCV for 35 tickers |
| Every 5 min | — | `monitor_active_signals` | ml | Check target/stop/expiry on active signals |
| Every 10 min | — | `refresh_trending_cache` | scraping | Pre-warm Redis trending cache |
| 2:00 AM | 7:30 AM | `ingest_insider_trades` | scraping | SEC Form 4 + NSE bulk/block deals |
| 2:30 AM | 8:00 AM | `generate_daily_signals` | ml | Full pipeline: triangulate → ML → risk → Telegram |
| 6:00 AM | 11:30 AM | `generate_system_report` | scraping | DB counts + data freshness |
| Sunday 3 AM | Sunday 8:30 AM | `cleanup_old_data` | scraping | Purge data older than 90 days |

Signal generation runs at 8:00 AM IST — before Indian market open (9:15 AM) and well after US close (4:00 PM ET = 2:30 AM IST). This ensures the laptop is awake.

---

## 11. Frontend Dashboard

Next.js 16 with TypeScript + Tailwind CSS v4. **Optional** — the primary interface is Telegram. The dashboard exists for visual verification after receiving a signal.

### Pages

| Route | File | Purpose |
|-------|------|---------|
| `/` | `app/page.tsx` | Dashboard — watchlist prices, active signals, trending tickers |
| `/signals` | `app/signals/page.tsx` | Signal management — active, daily report, history tabs |
| `/ticker/[symbol]` | `app/ticker/[symbol]/page.tsx` | Ticker detail — price chart, ML confidence bars, insider activity |

### Components

`signal-card.tsx`, `price-chart.tsx`, `sentiment-chart.tsx`, `stock-card.tsx`, `badges.tsx`, `card.tsx`

### Build

- Development: `npm run dev` on `:3000`
- Production: `output: 'standalone'` in next.config.ts, multi-stage Dockerfile
- API proxy: `/api/v1/*` → `http://localhost:8000/api/v1/*`

---

## 12. Infrastructure

### Docker Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `api` | Dockerfile (production stage) | 8000 | FastAPI server |
| `celery_worker` | Dockerfile (development stage) | — | Task execution |
| `celery_beat` | Dockerfile (development stage) | — | Task scheduling |
| `flower` | mher/flower | 5555 | Task monitoring UI |

### Dependencies (39 Python packages)

**Core:** FastAPI, SQLAlchemy 2.0, Alembic, Celery, Redis, Pydantic
**ML:** PyTorch 2.9.1 (CUDA), XGBoost 3.1.2, LightGBM 4.6.0, scikit-learn 1.8.0
**Data:** yfinance, feedparser, pandas-ta, vaderSentiment, requests
**Infra:** uvicorn, psutil, MLflow 3.10.0

### Environment Variables

```
DATABASE_URL          — PostgreSQL connection (required)
REDIS_URL             — Redis connection (required)
TELEGRAM_BOT_TOKEN    — Telegram bot token (required for alerts)
TELEGRAM_CHAT_ID      — Telegram chat ID (required for alerts)
SEC_USER_AGENT        — SEC EDGAR User-Agent (recommended)
ENVIRONMENT           — development/production
LOG_LEVEL             — INFO/DEBUG/WARNING
CORS_ORIGINS          — Allowed CORS origins
```

---

## 13. Complete File Map

### backend/strategy/ — The Brain

| File | Lines | What It Does |
|------|-------|-------------|
| `signal_engine.py` | 310 | The core sequential pipeline. Regime → Triangulate ALL 35 tickers → ML on survivors → Risk → Telegram. Contains `DEFAULT_WATCHLIST`, `TRIANGULATION_THRESHOLD`, all 4 scoring functions, feature vector builder. |
| `regime_filter.py` | 44 | Checks SPY > SMA200. Returns BULL or BEAR. |
| `insider_tracker.py` | 248 | SEC EDGAR Form 4 XML parser. Fetches filing list from full-text search, parses each XML for transaction details. 150ms rate limit. `calculate_insider_score()` assigns 0-30 points. |

### backend/scrapers/ — Data Collection

| File | Lines | What It Does |
|------|-------|-------------|
| `reddit_json_scraper.py` | 95 | Reddit `.json` backdoor. Hits `hot.json` with rotating User-Agents. 2-second rate limit. Pagination via `after` token. No API keys. |
| `india_rss_scraper.py` | 140 | Parses 5 RSS feeds via feedparser. Maps company names → NSE tickers. Pre-computes sentiment. MD5 hashes URLs to fit 50-char post_id column. |
| `india_insider_scraper.py` | 155 | NSE bulk/block deals via public JSON API. Refreshes session cookies first (NSE requires it). Parses dates in multiple formats. |
| `stock_scraper.py` | 168 | yfinance wrapper. Fetches OHLCV, computes 8 technical indicators via pandas-ta (RSI, MACD, BB, SMA50, SMA200, volume ratio). |
| `reddit_scraper.py` | 255 | Legacy PRAW-based scraper. Still importable but unused. Kept for reference. |

### backend/ml/ — Machine Learning

| File | Lines | What It Does |
|------|-------|-------------|
| `models/ensemble.py` | 121 | Weighted voting: XGBoost (40%) + LightGBM (30%) + LSTM (30%). Confidence threshold 0.70. |
| `models/xgboost_model.py` | 73 | XGBClassifier wrapper. Train, predict, predict_proba, save/load. |
| `models/lightgbm_model.py` | 70 | LGBMClassifier wrapper. Same interface. |
| `models/tft_model.py` | 137 | PyTorch LSTM classifier. 2 layers, 64 hidden. Train with Adam + CrossEntropyLoss. |
| `inference/predictor.py` | 87 | Loads ensemble from disk. `predict_single()` and `predict_batch()`. |
| `training/train_ensemble.py` | 312 | EnsembleTrainer with MLflow logging. Trains XGBoost + LightGBM. |
| `training/tft_training.py` | 243 | TFTTrainer. PyTorch TFT with MultiheadAttention + LSTM. |
| `training/baseline_training.py` | 402 | BaselineTrainer for comparison experiments. |
| `features/build.py` | 617 | FeatureBuilder. Computes technical, sentiment, insider, volume features from DB. |
| `backtesting/backtest_engine.py` | 640 | Full backtesting with trade recording, metrics, baseline comparison. |
| `tracking/mlflow_logger.py` | 362 | MLflow wrapper. Log params, metrics, artifacts. |
| `registry/model_registry.py` | 549 | Model versioning, promotion, A/B testing, rollback. |

### backend/services/ — Business Logic

| File | Lines | What It Does |
|------|-------|-------------|
| `risk_manager.py` | 488 | 5-rule validation: confidence, prices, R/R, position sizing, portfolio constraints. |
| `reddit_service.py` | 190 | Orchestrates Reddit JSON + India RSS scraping. Parallel fetch, sequential save. Quality scoring. |
| `telegram_notifier.py` | 85 | Raw HTTP POST to Telegram Bot API. Formats execution tickets. |
| `ml_service.py` | 45 | Thin wrapper — delegates to SignalEngine. |
| `stock_service.py` | 227 | Stock data operations. Fetch, save, get latest price. |
| `quality_scorer.py` | 418 | Post quality scoring: engagement, content, spam detection, upvote ratio. |

### backend/tasks/ — Celery Background Jobs

| File | Lines | What It Does |
|------|-------|-------------|
| `scraping_tasks.py` | 138 | `scrape_reddit_scheduled`, `fetch_stocks_scheduled`, `fetch_single_stock` |
| `ml_tasks.py` | 163 | `generate_daily_signals` (uses SignalEngine), `monitor_active_signals`, `train_models` |
| `insider_tasks.py` | 51 | `ingest_insider_trades` — SEC + NSE, dedup by filing_url+shares+date |
| `maintenance_tasks.py` | 238 | `cleanup_old_data`, `generate_system_report`, `refresh_trending_cache` |

### backend/api/ — HTTP Layer

| File | Lines | What It Does |
|------|-------|-------------|
| `main.py` | 159 | FastAPI app, lifespan (Redis connect/disconnect), health check, router registration |
| `routes/signals.py` | 131 | 5 signal endpoints |
| `routes/predictions.py` | 71 | 3 prediction endpoints |
| `routes/sentiment.py` | 116 | 3 sentiment endpoints |
| `routes/stocks.py` | 768 | 12 stock endpoints (most complex route file) |
| `routes/posts.py` | 591 | 6 post endpoints |
| `middleware/rate_limit.py` | 314 | Redis-backed IP rate limiting |

### backend/models/ — Database ORM

| File | Lines | Model |
|------|-------|-------|
| `stock.py` | 45 | StockPrice — OHLCV + 8 indicators |
| `reddit.py` | 33 | RedditPost — posts + sentiment + quality |
| `insider_trade.py` | 32 | InsiderTrade — SEC/NSE filings |
| `trading_signal.py` | 49 | TradingSignal — BUY/SELL with entry/stop/target |
| `prediction.py` | 32 | Prediction — ML ensemble output |
| `feature_snapshot.py` | 86 | FeatureSnapshot — training data snapshots |

### scripts/

| File | Lines | What It Does |
|------|-------|-------------|
| `train_models.py` | 77 | One-shot training: build data from DB → train XGBoost + LightGBM + LSTM → save |
| `setup.sh` | 105 | Initial project setup script |
| `verify_docker_setup.sh` | 255 | Docker environment verification |

### frontend/

| File | Lines | What It Does |
|------|-------|-------------|
| `app/page.tsx` | 133 | Dashboard — watchlist, signals, trending |
| `app/signals/page.tsx` | 147 | Signals page — active, daily, history tabs |
| `app/ticker/[symbol]/page.tsx` | 190 | Ticker detail — chart, ML bars, insider |
| `lib/api.ts` | 113 | Typed API client with error handling |
| `components/*.tsx` | ~330 | 6 reusable components |

---

## 14. Bug Fix History (29 Bugs)

### Session 1 — GOD MODE Sprint Fixes

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `tft_training.py` | Missing `psutil` dependency | `uv add psutil` |
| 2 | `tft_training.py` | TensorFlow import crash (not installed) | Full rewrite to PyTorch |
| 3 | `tft_training.py` | `logger` used before definition | Reordered imports |
| 4 | `tft_training.py` | `-> tf.keras.Model` annotation evaluated at import | `from __future__ import annotations` |
| 5 | `api/main.py` | Redis `ssl=True` broken in redis-py 7.x | Use `rediss://` URL scheme |
| 6 | `ml/features/build.py` | String ticker to `.in_()` | Added `isinstance(tickers, str)` coercion |
| 7 | `insider_tracker.py` | EDGAR URL construction broken (0 trades) | Built URLs from `_id` + `_source.ciks` |
| 8 | `insider_tracker.py` | `None` transaction_date crash | Added None check |
| 9 | `insider_tracker.py` | "director" matched "cto" via substring | Word-level set intersection |
| 10 | `insider_tracker.py` | No rate limit delay | Added 150ms sleep |
| 11 | `mlflow_logger.py` | `log_params(**kwargs)` but callers pass dicts | Accept both |
| 12 | `mlflow_logger.py` | `log_metrics_final()` didn't exist | Added as alias |
| 13 | `train_ensemble.py` | XGBoost 3.x removed `eval_metric` from `.fit()` | Moved to constructor |
| 14 | `baseline_training.py` | Same XGBoost 3.x issue | Same fix |
| 15 | All 3 trainers | `get_mlflow_logger()` wrong signature | Fixed call sites |
| 16 | `train_ensemble.py` | `log_artifact()` → `log_artifact_file()` | Renamed |
| 17 | `train_ensemble.py` | Used Regressors instead of Classifiers | Switched to XGBClassifier/LGBMClassifier |
| 18 | `ensemble.py` | Model filenames didn't match trainer output | Aligned to `xgboost_model.pkl` |
| 19 | `signal_engine.py` | 10 features but model trained on 11 | Added close, volume, high-low |
| 20 | `train_ensemble.py` | `LGBMRegressor` return type annotation | Fixed to `LGBMClassifier` |

### Session 2 — Production Readiness Fixes

| # | File | Bug | Fix |
|---|------|-----|-----|
| 21 | `insider_trade.py` | `filing_url` unique constraint (multiple trades per filing) | Migration: dropped unique, added index |
| 22 | `maintenance_tasks.py` | `from backend.models.prediction import TradingSignal` (wrong module) | → `trading_signal` |
| 23 | `maintenance_tasks.py` | `TradingSignal.status` field doesn't exist | → `is_active == 0` |
| 24 | `api/routes/posts.py` | Imported PRAW-based `RedditScraper` | → `RedditJsonScraper` |
| 25 | `scraping_tasks.py` | Delisted `SQ` in watchlist | → `COIN` |
| 26 | `insider_tasks.py` | Dedup only by `filing_url` (skipped valid trades) | → Dedup by `filing_url + shares + date` |
| 27 | `ml_service.py` | Old parallel pipeline bypassing SignalEngine | → Delegates to SignalEngine |
| 28 | `india_rss_scraper.py` | `post_id` too long for String(50) column | → MD5 hash to 50 chars |
| 29 | `reddit_service.py` | RSS articles penalized by quality scorer (0 upvotes) | → Bypass for `rss:` sources |

---

## 15. What Is Done (Complete)

### Core Pipeline ✅
- [x] Sequential signal engine (Regime → Triangulate → ML → Risk → Telegram)
- [x] Regime filter (SPY > SMA200)
- [x] Triangulation scoring (4 dimensions, 0-100)
- [x] ML ensemble (XGBoost + LightGBM + LSTM, weighted voting)
- [x] Risk manager (5 rules, hardcoded -5%/+10%)
- [x] Telegram notifier (raw HTTP POST, baby-proof execution tickets)

### Data Ingestion ✅
- [x] SEC EDGAR Form 4 parser (US insider buying)
- [x] NSE bulk/block deal scraper (India insider buying)
- [x] Reddit .json backdoor scraper (US retail hype, no API keys)
- [x] India RSS scraper (ET, Moneycontrol, NDTV, Yahoo Finance)
- [x] yfinance stock scraper with pandas-ta indicators
- [x] VADER sentiment analyzer with stock market lexicon

### ML ✅
- [x] XGBoost classifier trained and saved
- [x] LightGBM classifier trained and saved
- [x] PyTorch LSTM trained and saved
- [x] Ensemble weighted voting (40/30/30)
- [x] Predictor loads from disk and runs inference
- [x] Training script (`scripts/train_models.py`)

### Infrastructure ✅
- [x] FastAPI with 30 API endpoints
- [x] PostgreSQL with 6 tables, 12 migrations
- [x] Redis caching + rate limiting
- [x] Celery with 8 scheduled tasks
- [x] Docker Compose (API + worker + beat + Flower)
- [x] Frontend Dockerfile (standalone Next.js)
- [x] .dockerignore, .env.example

### Frontend ✅
- [x] Dashboard page (watchlist + signals + trending)
- [x] Signals page (active/daily/history)
- [x] Ticker detail page (chart + ML + insider)
- [x] Builds with 0 errors

### Documentation ✅
- [x] README.md (full system overview)
- [x] docs/ARCHITECTURE.md (deep technical dive)
- [x] docs/COMPLETE_ANALYSIS.md (this document)
- [x] docs/NEXT_STEPS.md (status tracker)
- [x] docs/TRADING_STRATEGY.md
- [x] docs/GOD_MODE_MASTER_PLAN.md

---

## 16. What Is NOT Done (Remaining Work)

### Must Do Before Live Use

| # | Task | Why | Effort |
|---|------|-----|--------|
| 1 | **Set up Telegram bot** | No alerts without it | 5 min |
| 2 | **Fetch India stock data** | India tickers have 0 stock_prices rows — technicals and flow scores will be 0 | 10 min (run stock scraper for .NS tickers) |
| 3 | **Accumulate data for 1-2 weeks** | Triangulation needs data density. With 32 reddit posts and 112 insider trades, scores are too low to hit 60. | 7-14 days of Celery running |
| 4 | **Retrain models on real data** | Current models trained on initial data. After 2 weeks, retrain with `scripts/train_models.py` | 5 min |

### Should Do (Within 2 Months)

| # | Task | Why | Effort |
|---|------|-----|--------|
| 5 | **Retrain ML on triangulation survivors** | Models trained on all stocks, but only see survivors in production. Confidence scores are uncalibrated. | 1 day |
| 6 | **Telegram group scraping (Telethon)** | India Layer 3 is RSS (institutional news), not retail hype. Telethon scrapes actual retail Telegram groups. | 2-3 hours |
| 7 | **Expand US watchlist** | Add mid-caps (CRWD, DDOG, NET, PLTR, HOOD) where insider signals have higher information value. | 10 min |
| 8 | **Backtest on historical data** | Validate the triangulation strategy on past data before risking real money. | 2-3 hours |

### Nice to Have (No Rush)

| # | Task | Why |
|---|------|-----|
| 9 | Unfreeze MLOps (MLflow, registry) | After data pipes are proven clean |
| 10 | Add more RSS feeds for India | Livemint, Business Standard |
| 11 | Portfolio tracking in DB | Track actual P&L across signals |
| 12 | Signal performance dashboard | Win rate, avg return, drawdown charts |

---

## 17. Known Limitations & Honest Assessment

### The ML Dataset Shift Problem
Current models were trained on ALL stock data to predict 5-day forward returns. In production, they only see stocks that scored ≥ 60 on triangulation. The confidence scores are uncalibrated for this filtered population. The 0.70 threshold compensates, but proper fix requires retraining on triangulation survivors after 2 months.

### India RSS ≠ Retail Hype
Moneycontrol and ET Markets are institutional news sources, not retail sentiment. When a journalist writes about Reliance, it doesn't mean retail traders are hyping it. Layer 3 for India is weaker than for US (where Reddit IS retail hype). Mitigation: rely more on Layer 1 (NSE block deals) and Layer 2 (volume) for India.

### Data Sparsity (Right Now)
With only 32 reddit posts and 112 insider trades, no ticker can realistically score ≥ 60. The system needs 1-2 weeks of continuous data accumulation before it can generate real signals. This is expected and correct — the silence means the risk manager is protecting you.

### Single Point of Failure
Everything runs on one laptop. If the laptop sleeps, Celery Beat misfires. Mitigation: schedule shifted to IST morning hours (7:30-8:00 AM) when the laptop is guaranteed to be on. Long-term fix: move Celery to a $5/month VPS.

### No Backtesting Validation
The triangulation strategy has not been backtested on historical data. The backtesting engine exists (`backend/ml/backtesting/backtest_engine.py`) but hasn't been run against the current pipeline. This should be done before risking real money.

---

## 18. Production Checklist

```
SETUP (do once)
[ ] Fill in .env with DATABASE_URL, REDIS_URL
[ ] Set up Telegram bot → add TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID to .env
[ ] Run: uv run alembic upgrade head
[ ] Run: uv run python scripts/train_models.py
[ ] Fetch India stock data: run stock scraper for .NS tickers

LAUNCH
[ ] docker compose up -d
[ ] Verify: curl http://localhost:8000/health
[ ] Verify: Flower UI at http://localhost:5555
[ ] Send test Telegram message to confirm bot works

DAILY OPERATION
[ ] Keep laptop awake from 7:00 AM - 9:00 AM IST (signal generation window)
[ ] When Telegram signal arrives → copy entry/stop/target into broker
[ ] Do NOT lower the 60 threshold if no signals for days — that's the system working

WEEKLY
[ ] Check Flower for failed tasks
[ ] Review system report (generated daily at 11:30 AM IST)

MONTHLY
[ ] Retrain models: uv run python scripts/train_models.py
[ ] Review signal performance (win rate, avg return)

AFTER 2 MONTHS
[ ] Retrain ML on triangulation survivors only
[ ] Consider adding Telethon for India retail hype
[ ] Consider moving Celery to VPS for reliability
```

---

## Codebase Statistics

| Metric | Value |
|--------|-------|
| Python files | 82 |
| TypeScript/TSX files | 19 |
| Python lines of code | 13,894 |
| Frontend lines of code | 979 |
| Total lines of code | ~14,873 |
| Database tables | 6 |
| Alembic migrations | 12 |
| API endpoints | 30 |
| Celery scheduled tasks | 8 |
| ML models | 3 (XGBoost + LightGBM + LSTM) |
| Python dependencies | 39 |
| Docker services | 4 |
| Bugs found and fixed | 29 |
| Data sources | 5 (SEC, NSE, yfinance, Reddit, RSS) |
| Watchlist tickers | 35 (20 US + 15 India) |

---

*This document represents the complete state of TFT Trader as of 2026-02-28. It should be updated after each major change.*
