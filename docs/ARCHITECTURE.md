# TFT Trader — Architecture Document

Last updated: 2026-02-28

---

## System Overview

TFT Trader is an EOD (End of Day) signal generator that runs entirely on a local machine. It is NOT an auto-trading bot. It acts as a junior quant analyst: ingests data, scores stocks, validates with ML, checks risk, and sends a Telegram message with exact entry/stop/target. The human copies those numbers into a broker app.

### Deployment Model (₹0 Hybrid-Local Stack)

```
┌─────────────────────────────────────────────────────────┐
│  LOCAL (Lenovo Legion laptop via Docker)                │
│                                                         │
│  FastAPI API server (:8000)                             │
│  Celery Worker (scraping + ml queues)                   │
│  Celery Beat (scheduler)                                │
│  Next.js Dashboard (:3000) — optional, verification     │
│  Flower (:5555) — task monitoring                       │
└──────────────┬──────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────┐
│  CLOUD (free tiers only)                                │
│                                                         │
│  PostgreSQL — Neon (free tier, 0.5 GB)                  │
│  Redis — Redis Cloud (free tier, 30 MB)                 │
│  Telegram Bot API — free, unlimited                     │
└─────────────────────────────────────────────────────────┘
```

No AWS/GCP/Azure compute. No paid APIs. Total monthly cost: $0.

---

## Sequential Pipeline Architecture

The core design principle: **data flows sequentially through increasingly strict gates.** Each gate reduces the candidate set. ML only evaluates stocks that already passed the fundamental screen.

```
20 tickers → Regime Gate → Triangulation (≥60) → ML (≥70% conf) → Risk → Telegram
   20            20           typically 0-3         0-2            0-1      0-1
```

### Gate 1: Regime Filter

File: `backend/strategy/regime_filter.py`

Checks if SPY close > SMA200. If BEAR regime, the entire pipeline stops. No signals generated in bear markets.

### Gate 2: Triangulation Scoring

File: `backend/strategy/signal_engine.py` → `calculate_triangulation_score()`

Every ticker in the watchlist is scored across 4 dimensions:

| Dimension | Max Score | Source | Logic |
|-----------|-----------|--------|-------|
| Insider Buying | 30 | SEC EDGAR Form 4 + NSE bulk/block | CEO/CFO buy=30, Director=20, cluster bonus=5 |
| Volume Flow | 20 | yfinance volume_ratio | >2.0x avg=20, >1.5x=10 |
| Retail Hype | 20 | Reddit JSON + India RSS | avg sentiment >0.3 AND mentions >20 = 20 |
| Technicals | 30 | pandas-ta indicators | RSI<35=10, MACD cross=10, close>SMA50=10 |

Total score range: 0-100. Threshold: **≥ 60 to pass.**

This means at minimum 2-3 layers must align. A stock with only good technicals (30) won't pass. A stock with insider buying (30) + volume spike (20) + weak technicals (10) = 60 → passes.

### Gate 3: ML Ensemble Validation

File: `backend/ml/models/ensemble.py` + `backend/ml/inference/predictor.py`

Only tickers that passed triangulation reach the ML models. The ensemble answers: **"Given that triangulation flagged this stock, what is the probability this signal will succeed (+10% before hitting -5%)?"**

| Model | Weight | Type |
|-------|--------|------|
| XGBoost | 40% | Gradient boosted trees (fast, handles tabular data well) |
| LightGBM | 30% | Gradient boosted trees (handles categorical features) |
| LSTM | 30% | PyTorch recurrent network (captures temporal patterns) |

Weighted probability averaging. Output: BUY/HOLD/SELL + confidence score.
Threshold: **BUY + confidence ≥ 0.70 to pass.**

### Gate 4: Risk Manager

File: `backend/services/risk_manager.py`

5 sequential validation rules:

1. **Confidence** — must be ≥ 70%
2. **Price levels** — entry, stop, target must be logically valid
3. **Risk/Reward** — minimum 1:2 (risk $1 to make $2)
4. **Position sizing** — max 2% risk per trade, max 20% position size
5. **Portfolio constraints** — max 5 concurrent positions, max 15% drawdown

If any rule fails, the signal is rejected. The risk manager is the final safety gate.

### Gate 5: Telegram Alert

File: `backend/services/telegram_notifier.py`

Approved signals are immediately pushed to Telegram as a strict execution ticket:

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

Uses raw HTTP POST to Telegram Bot API. No library dependency. Gracefully degrades when credentials aren't configured.

---

## Data Ingestion Layer

All data sources are free and require zero API keys.

### US Market

| Source | Scraper | Schedule | Data |
|--------|---------|----------|------|
| SEC EDGAR | `backend/strategy/insider_tracker.py` | Daily 10 PM UTC | Form 4 XML → insider_trades table |
| yfinance | `backend/scrapers/stock_scraper.py` | Hourly | OHLCV + 8 technical indicators → stock_prices table |
| Reddit .json | `backend/scrapers/reddit_json_scraper.py` | Every 30 min | Posts from r/wallstreetbets, r/stocks, r/options → reddit_posts table |

The Reddit scraper uses the public `.json` endpoint (`reddit.com/r/{sub}/hot.json`) with rotating User-Agents and a 2-second rate limit. No PRAW, no OAuth, no API keys.

### India Market

| Source | Scraper | Schedule | Data |
|--------|---------|----------|------|
| NSE Bulk/Block Deals | `backend/scrapers/india_insider_scraper.py` | Daily 10 PM UTC | Promoter/institutional buying → insider_trades table |
| RSS Feeds | `backend/scrapers/india_rss_scraper.py` | Every 30 min | ET Markets, Moneycontrol, NDTV, Yahoo Finance India → reddit_posts table |

India RSS articles are stored in the same `reddit_posts` table with `subreddit` prefixed as `rss:` for easy filtering.

---

## Database Schema

PostgreSQL via Neon (free tier). 6 tables:

| Table | Rows (current) | Purpose |
|-------|----------------|---------|
| `stock_prices` | 4,769 | OHLCV + RSI, MACD, BB, SMA50, SMA200, volume_ratio |
| `insider_trades` | 112 | SEC Form 4 + NSE bulk/block deals |
| `reddit_posts` | 32 | Reddit posts + India RSS articles with tickers + sentiment |
| `trading_signals` | 8 | Approved BUY signals with entry/stop/target |
| `predictions` | 0 | ML ensemble predictions (populated on-demand) |
| `feature_snapshots` | 0 | Feature engineering snapshots for training |

Key indexes: `idx_ticker_date` on stock_prices, `idx_tickers` (GIN) on reddit_posts, `idx_insider_ticker_date` on insider_trades.

---

## ML Pipeline

### Training

```bash
uv run python scripts/train_models.py
```

1. Fetches all stock prices from DB
2. Builds feature vectors (11 features: RSI, MACD, MACD signal, BB upper/lower, SMA50, SMA200, volume ratio, close, volume, high-low range)
3. Labels: 5-day forward return > +3% = BUY, < -3% = SELL, else HOLD
4. Trains XGBoost + LightGBM (classifiers) + LSTM
5. Saves to `data/models/ensemble_latest/`

### Inference

The `Predictor` class loads models from disk and runs weighted ensemble prediction. Called by `SignalEngine` only for tickers that passed triangulation.

### Model Artifacts

```
data/models/ensemble_latest/
├── xgboost_model.pkl      (995 KB) — XGBClassifier, multi:softprob, 3-class
├── lightgbm_model.pkl     (778 KB) — LGBMClassifier, multiclass
├── lstm_model.pt          (224 KB) — PyTorch 2-layer LSTM classifier
├── xgboost_metadata.json
└── lightgbm_metadata.json
```

---

## Celery Task Architecture

```
celery_app.py
├── Queue: scraping
│   ├── scrape_reddit_scheduled      (every 30 min)
│   ├── fetch_stocks_scheduled       (every hour)
│   ├── ingest_insider_trades        (daily 10 PM UTC)
│   ├── cleanup_old_data             (Sunday 3 AM)
│   ├── generate_system_report       (daily 6 AM)
│   └── refresh_trending_cache       (every 10 min)
└── Queue: ml
    ├── generate_daily_signals       (daily 10:30 PM UTC)
    └── monitor_active_signals       (every 5 min)
```

Signal generation runs at 10:30 PM UTC (30 min after insider ingestion) to ensure fresh insider data is available for triangulation scoring.

---

## Frontend

Next.js 16 with TypeScript + Tailwind CSS v4. Three pages:

| Route | Purpose |
|-------|---------|
| `/` | Dashboard — watchlist prices, active signals, trending tickers |
| `/signals` | Signal management — active, daily report, history tabs |
| `/ticker/[symbol]` | Ticker detail — price chart, ML confidence bars, insider activity |

The frontend is optional. The primary interface is Telegram. The dashboard exists for visual verification of the AI's logic after receiving a signal.

Production build: `output: 'standalone'` in next.config.ts, multi-stage Dockerfile.

---

## Key Design Decisions

1. **Sequential, not parallel** — ML only evaluates triangulation survivors. This prevents false positives from ML alone and reduces compute waste.

2. **Telegram-first, not dashboard-first** — The signal must reach your phone as a push notification. The dashboard is for verification, not discovery.

3. **Zero API keys for data** — Reddit .json backdoor, SEC EDGAR public XML, NSE public API, RSS feeds. No dependency on API approvals or rate limit negotiations.

4. **Risk manager is God** — Even if triangulation + ML both say BUY, the risk manager can reject. The 1:2 R/R ratio is the mathematical edge that makes the system profitable at 45% win rate.

5. **Baby-proof execution** — The Telegram message contains exact numbers. No charts, no analysis, no "maybe." Copy entry/stop/target into broker. Close the app.

6. **India + US dual market** — Same triangulation logic, different data sources. India uses NSE bulk/block deals instead of SEC Form 4, and RSS feeds instead of Reddit.
