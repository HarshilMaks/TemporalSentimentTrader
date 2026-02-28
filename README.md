# TFT Trader — Triangulation Swing Trading Platform

Enterprise-grade EOD signal generator using the Triangulation Method. BUY signals fire only when 3 independent data layers align. An ML ensemble validates candidates. A strict risk manager ensures profitability at 45% win rate. Signals are pushed to Telegram as baby-proof execution tickets.

**This is NOT an auto-trading bot.** It's a junior quant analyst that runs on your laptop, crunches data after market close, and texts you what to buy tomorrow morning.

**Status:** Production-ready, all real data, zero mocks
**Markets:** US (NYSE/NASDAQ) + India (NSE)
**Stack:** FastAPI · PostgreSQL · PyTorch · XGBoost · LightGBM · Next.js 16 · Celery · Telegram

---

## How It Works

```
 4:30 PM ─── System wakes up ───────────────────────────────────────────────

 DATA INGESTION (all free, zero API keys needed)
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  SEC EDGAR ──────→ InsiderTracker ──→ insider_trades (Form 4 XML)       │
 │  NSE Bulk/Block ─→ IndiaInsider   ──→ insider_trades (promoter deals)   │
 │  yfinance ───────→ StockScraper   ──→ stock_prices (OHLCV + indicators) │
 │  Reddit .json ───→ JsonScraper    ──→ reddit_posts (no API keys!)       │
 │  India RSS ──────→ RssScraper     ──→ reddit_posts (ET, Moneycontrol)   │
 └──────────────────────────┬───────────────────────────────────────────────┘
                            │
 STEP 1: REGIME GATE        │
 ┌──────────────────────────▼───────────────────────────────────────────────┐
 │  SPY close > SMA200 → BULL (proceed)                                    │
 │  SPY close < SMA200 → BEAR (stop, no signals today)                    │
 └──────────────────────────┬───────────────────────────────────────────────┘
                            │ BULL only
 STEP 2: TRIANGULATE ALL TICKERS (score 0-100)
 ┌──────────────────────────▼───────────────────────────────────────────────┐
 │  Layer 1 — Insider Buying  (0-30)  CEO/CFO buy=30, Director=20         │
 │  Layer 2 — Volume Flow     (0-20)  Volume ratio >2.0=20, >1.5=10      │
 │  Layer 3 — Retail Hype     (0-20)  Sentiment >0.3 + mentions >20      │
 │  Technicals                (0-30)  RSI<35=10, MACD cross=10, >SMA50=10│
 │                                                                         │
 │  20 tickers scanned → only those scoring ≥ 60 survive                  │
 └──────────────────────────┬───────────────────────────────────────────────┘
                            │ score ≥ 60 (typically 0-3 tickers)
 STEP 3: ML VALIDATION (only on survivors)
 ┌──────────────────────────▼───────────────────────────────────────────────┐
 │  XGBoost  (40%) ─┐                                                      │
 │  LightGBM (30%) ─┼→ Weighted vote → "Will this signal succeed?"        │
 │  LSTM     (30%) ─┘   BUY + confidence ≥ 70% → pass                    │
 └──────────────────────────┬───────────────────────────────────────────────┘
                            │ BUY + conf ≥ 70%
 STEP 4: RISK MANAGER (final gate)
 ┌──────────────────────────▼───────────────────────────────────────────────┐
 │  Stop Loss: -5% (hardcoded)     Take Profit: +10% (hardcoded)          │
 │  Risk/Reward: 1:2 minimum       Position: 2% of portfolio              │
 │  Max 5 concurrent positions     Max 15% portfolio drawdown             │
 └──────────────────────────┬───────────────────────────────────────────────┘
                            │ approved
 STEP 5: TELEGRAM ALERT
 ┌──────────────────────────▼───────────────────────────────────────────────┐
 │  🚨 TRIANGULATION BUY SIGNAL                                            │
 │  Ticker: $NVDA                                                          │
 │  Entry: $142.50  |  Stop: $135.38 (-5%)  |  Target: $156.75 (+10%)    │
 │  Position: 2% ($2,000)                                                  │
 │                                                                         │
 │  Copy into broker. Do not analyze. Execute.                             │
 └──────────────────────────┬───────────────────────────────────────────────┘
                            │
 Signal saved to DB → Dashboard updated → System sleeps
```

---

## The Math

```
Win rate: 45%    Avg win: +10%    Avg loss: -5%
EV per trade = (0.45 × 10) - (0.55 × 5) = +1.75%

100 trades × 1.75% = +175% cumulative return
Profitable even losing 55% of trades. The 1:2 R/R is the edge.
```

---

## Data Sources (All Free, Zero API Keys)

| Layer | US Market | India Market |
|-------|-----------|-------------|
| Insider Buying | SEC EDGAR Form 4 XML parser | NSE bulk/block deals API |
| Volume Flow | yfinance OHLCV + volume ratio | yfinance (NSE tickers) |
| Retail Hype | Reddit `.json` backdoor (no PRAW) | RSS feeds (ET Markets, Moneycontrol, NDTV, Yahoo Finance India) |
| Technicals | pandas-ta (RSI, MACD, BB, SMA) | pandas-ta |

The Reddit scraper hits `reddit.com/r/{sub}/hot.json` with rotating User-Agents. No API keys, no PRAW library, no OAuth. Just HTTP GET with a 2-second rate limit.

---

## Watchlist

**US (20 tickers):**
AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, AMD, NFLX, DIS,
BABA, INTC, CSCO, ADBE, PYPL, CRM, ORCL, UBER, SPOT, COIN

**India (30 tickers):**
RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, HINDUNILVR, ITC, SBIN,
BHARTIARTL, KOTAKBANK, LT, AXISBANK, ASIANPAINT, MARUTI, TITAN,
SUNPHARMA, BAJFINANCE, WIPRO, HCLTECH, ULTRACEMCO, NESTLEIND,
TATAMOTORS, TATASTEEL, POWERGRID, NTPC, ONGC, JSWSTEEL,
ADANIENT, ADANIPORTS, TECHM

---

## Quick Start

### 1. Backend

```bash
cp .env.example .env              # Fill in DB + Redis + Telegram credentials
uv sync                           # Install dependencies
uv run alembic upgrade head       # Run migrations
uv run uvicorn backend.api.main:app --reload  # API on :8000
```

### 2. Telegram Bot (for signal alerts)

```bash
# 1. Message @BotFather on Telegram → /newbot → copy token
# 2. Message your bot, then visit:
#    https://api.telegram.org/bot<TOKEN>/getUpdates
#    Copy the chat_id from the response
# 3. Add to .env:
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Background Tasks (Celery)

```bash
# Worker (processes scraping + ML tasks)
celery -A backend.celery_app worker --loglevel=info --queues=scraping,ml

# Scheduler (triggers tasks on schedule)
celery -A backend.celery_app beat --loglevel=info
```

### 4. Frontend (optional — for visual verification)

```bash
cd frontend && npm install && npm run dev    # Dashboard on :3000
```

### 5. Docker (all-in-one)

```bash
docker compose up -d
# API: http://localhost:8000
# Flower (task monitor): http://localhost:5555
```

---

## Celery Beat Schedule

| Time (UTC) | Task | What It Does |
|------------|------|-------------|
| Every 30 min | `scrape_reddit_scheduled` | Reddit JSON + India RSS → DB |
| Every hour | `fetch_stocks_scheduled` | yfinance OHLCV for 20 tickers |
| 10:00 PM | `ingest_insider_trades` | SEC Form 4 + NSE bulk/block deals |
| 10:30 PM | `generate_daily_signals` | Full pipeline: triangulate → ML → risk → Telegram |
| Every 5 min | `monitor_active_signals` | Check target/stop/expiry on active signals |
| Every 10 min | `refresh_trending_cache` | Pre-warm Redis cache |
| Sunday 3 AM | `cleanup_old_data` | Purge data older than 90 days |
| Daily 6 AM | `generate_system_report` | DB counts + data freshness |

---

## API Endpoints

### Signals (`/api/v1/signals`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/active` | Active trading signals |
| GET | `/history?limit=50` | Closed signals with P&L |
| GET | `/ticker/{ticker}` | Signals for specific ticker |
| GET | `/daily-report` | Today's generated signals |
| POST | `/{id}/close?exit_price=&exit_reason=` | Manually close a signal |

### Predictions (`/api/v1/predictions`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/latest` | Latest ensemble prediction per ticker |
| GET | `/ticker/{ticker}?limit=30` | Prediction history |
| POST | `/run` | Trigger manual prediction run |

### Sentiment (`/api/v1/sentiment`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/trending?days=7&limit=20` | Top tickers by mentions + sentiment |
| GET | `/ticker/{ticker}?days=30` | Daily sentiment aggregates |
| GET | `/insider/{ticker}?days=90` | Insider trading activity |

### Stocks (`/api/v1/stocks`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/prices/{ticker}` | Historical OHLCV + indicators |
| POST | `/fetch/{ticker}` | Trigger stock data fetch |

### Posts (`/api/v1/posts`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Paginated posts (Reddit + India RSS) |
| GET | `/ticker/{ticker}` | Posts mentioning ticker |
| GET | `/trending` | Most mentioned tickers |
| GET | `/sentiment/{ticker}` | Aggregate sentiment |

---

## Repository Structure

```
tft-trader/
├── backend/
│   ├── api/
│   │   ├── main.py                     # FastAPI app, health check, lifespan
│   │   ├── routes/                     # 5 route files, 15 endpoints
│   │   └── middleware/rate_limit.py    # Redis-backed IP rate limiting
│   ├── models/                         # 6 SQLAlchemy ORM models
│   ├── strategy/
│   │   ├── signal_engine.py            # Sequential pipeline (triangulate → ML → risk → Telegram)
│   │   ├── regime_filter.py            # SPY vs SMA200 bull/bear gate
│   │   └── insider_tracker.py          # SEC EDGAR Form 4 XML parser
│   ├── ml/
│   │   ├── models/                     # XGBoost, LightGBM, LSTM, Ensemble
│   │   ├── inference/predictor.py      # Load models + predict
│   │   ├── features/build.py           # Feature engineering
│   │   └── training/                   # Training scripts
│   ├── scrapers/
│   │   ├── reddit_json_scraper.py      # Reddit .json backdoor (no API keys)
│   │   ├── india_rss_scraper.py        # India RSS (ET, Moneycontrol, NDTV, Yahoo)
│   │   ├── india_insider_scraper.py    # NSE bulk/block deals
│   │   ├── stock_scraper.py            # yfinance + pandas_ta indicators
│   │   └── reddit_scraper.py           # PRAW scraper (legacy, unused)
│   ├── services/
│   │   ├── telegram_notifier.py        # Push signals to Telegram
│   │   ├── risk_manager.py             # 5-rule risk validation
│   │   ├── reddit_service.py           # Scrape → extract tickers → sentiment → DB
│   │   ├── ml_service.py               # Delegates to SignalEngine
│   │   └── stock_service.py            # Stock data operations
│   ├── tasks/                          # 4 Celery task files
│   ├── celery_app.py                   # Beat schedule + routing
│   └── config/settings.py              # Pydantic settings from .env
├── frontend/                           # Next.js 16 dashboard
│   ├── app/                            # 3 pages: dashboard, signals, ticker detail
│   ├── components/                     # Charts, cards, badges
│   └── Dockerfile                      # Production standalone build
├── data/models/ensemble_latest/        # Trained model artifacts
│   ├── xgboost_model.pkl              # XGBClassifier (995 KB)
│   ├── lightgbm_model.pkl             # LGBMClassifier (778 KB)
│   └── lstm_model.pt                  # PyTorch LSTM (224 KB)
├── scripts/train_models.py             # One-shot training script
├── alembic/                            # 12 migrations
├── docker-compose.yml                  # API + Celery worker + beat + Flower
├── Dockerfile                          # Multi-stage (dev + prod)
└── docs/                               # Architecture + strategy docs
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, Pydantic, uvicorn |
| Database | PostgreSQL (Neon free tier), SQLAlchemy 2.0, Alembic |
| Cache | Redis (Redis Cloud free tier) |
| Tasks | Celery, Celery Beat |
| ML | PyTorch (LSTM), XGBoost, LightGBM, scikit-learn |
| Features | pandas-ta, vaderSentiment |
| Data | yfinance, feedparser, requests (Reddit JSON + SEC EDGAR + NSE) |
| Alerts | Telegram Bot API (raw HTTP POST) |
| Frontend | Next.js 16, TypeScript, Tailwind CSS v4, Recharts |
| Infra | Docker, Docker Compose |

---

## Environment Variables

```bash
# Database (required)
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require

# Redis (required for Celery + caching)
REDIS_URL=redis://default:pass@host:port/0

# Telegram (required for signal alerts)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# SEC EDGAR (recommended)
SEC_USER_AGENT=TFT-Trader/1.0 your@email.com

# Optional
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000
```

---

## Training Models

```bash
uv run python scripts/train_models.py
```

This builds training data from stock prices in the DB, trains XGBoost + LightGBM + LSTM, and saves to `data/models/ensemble_latest/`. Retrain weekly or after accumulating 2+ weeks of new data.

---

## Disclaimer

This project is for **educational and research purposes only**. Not financial advice. Do not use for live trading without extensive validation and regulatory compliance. Past performance does not guarantee future results. You are responsible for your own trading decisions.

---

Built as a learning project for ML engineering + quantitative trading systems.
