# TFT Trader — Triangulation Swing Trading Platform

**Legal insider trading (information arbitrage) swing trading platform using the Triangulation Method.**

BUY signals fire only when 3 independent data layers align: SEC Form 4 insider filings, institutional volume flow, and Reddit retail sentiment. An ML ensemble validates candidates, and a strict risk manager ensures profitability even at 45% win rate.

**Status:** Backend complete, Frontend complete, Integration tested  
**Strategy:** Triangulation swing trading (3-7 day holds)  
**Tech Stack:** FastAPI · PostgreSQL · PyTorch · XGBoost · LightGBM · Next.js 16 · Celery

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION (EOD)                        │
│                                                                     │
│  SEC EDGAR ──→ InsiderTracker ──→ insider_trades table              │
│  yfinance  ──→ StockScraper   ──→ stock_prices table               │
│  Reddit    ──→ RedditScraper  ──→ reddit_posts table                │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                    REGIME FILTER (Gate)                              │
│                                                                     │
│  SPY close > SMA200 → BULL (allow BUY)                              │
│  SPY close < SMA200 → BEAR (block all BUY signals)                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ BULL only
┌──────────────────────────▼──────────────────────────────────────────┐
│               TRIANGULATION SCORING (0-100)                         │
│                                                                     │
│  Insider Score  (0-30)  CEO/CFO buy = 30, Director = 20, cluster+5 │
│  Flow Score     (0-20)  Volume ratio > 2.0 = 20, > 1.5 = 10       │
│  Sentiment Score(0-20)  Reddit avg > 0.3 AND mentions > 20 = 20    │
│  Technical Score(0-30)  RSI < 35 = 10, MACD cross = 10, >SMA50 =10│
│                                                                     │
│  Total ≥ 60 → candidate passes to ML validation                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ score ≥ 60
┌──────────────────────────▼──────────────────────────────────────────┐
│                  ML ENSEMBLE VALIDATION                              │
│                                                                     │
│  XGBoost  (40%) ─┐                                                  │
│  LightGBM (30%) ─┼→ Weighted vote → BUY + confidence ≥ 0.70       │
│  TFT/LSTM (30%) ─┘                                                  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ BUY + conf ≥ 70%
┌──────────────────────────▼──────────────────────────────────────────┐
│                    RISK MANAGER                                      │
│                                                                     │
│  Stop: -5%  Target: +10%  R/R: 1:2                                  │
│  Max position: 20%  Max risk/trade: 2%  Max 5 positions             │
│  Portfolio drawdown limit: 15%                                       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ approved
                    TradingSignal → DB → API → Dashboard
```

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
| GET | `/insider/{ticker}?days=90` | Insider trading activity (Form 4) |

### Stocks (`/api/v1/stocks`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/prices/{ticker}` | Historical OHLCV + indicators |
| POST | `/fetch/{ticker}` | Trigger stock data fetch |

### Reddit (`/api/v1/posts`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Paginated Reddit posts |
| GET | `/ticker/{ticker}` | Posts mentioning ticker |
| GET | `/trending` | Most mentioned tickers |
| GET | `/sentiment/{ticker}` | Aggregate sentiment |

---

## Tech Stack

**Backend:** FastAPI, PostgreSQL (Neon), SQLAlchemy 2.0, Alembic, Celery, Redis  
**ML:** PyTorch (LSTM), XGBoost, LightGBM, pandas-ta  
**Data:** yfinance, PRAW, SEC EDGAR (Form 4 XML), vaderSentiment  
**Frontend:** Next.js 16, TypeScript, Tailwind CSS v4, Recharts, TradingView lightweight-charts  
**Infra:** Docker, Celery Beat scheduler

---

## Repository Structure

```
tft-trader/
├── backend/
│   ├── api/
│   │   ├── main.py                 # FastAPI app + router registration
│   │   ├── routes/
│   │   │   ├── signals.py          # Trading signals CRUD
│   │   │   ├── predictions.py      # ML predictions
│   │   │   ├── sentiment.py        # Sentiment + insider data
│   │   │   ├── stocks.py           # Stock prices + fetch
│   │   │   └── posts.py            # Reddit posts
│   │   └── middleware/
│   │       └── rate_limit.py       # IP-based rate limiting
│   ├── models/                     # SQLAlchemy ORM
│   │   ├── trading_signal.py       # BUY/SELL/HOLD signals
│   │   ├── prediction.py           # ML ensemble predictions
│   │   ├── insider_trade.py        # SEC Form 4 filings
│   │   ├── stock.py                # OHLCV + indicators
│   │   ├── reddit.py               # Reddit posts + sentiment
│   │   └── feature_snapshot.py     # Feature engineering snapshots
│   ├── strategy/                   # Triangulation engine
│   │   ├── signal_engine.py        # Score → ML → Risk → Signal
│   │   ├── regime_filter.py        # SPY vs SMA200 bull/bear
│   │   └── insider_tracker.py      # SEC EDGAR Form 4 scraper
│   ├── ml/
│   │   ├── models/                 # XGBoost, LightGBM, TFT/LSTM, Ensemble
│   │   ├── inference/predictor.py  # Batch/single prediction
│   │   ├── features/build.py       # Feature engineering (25-d vector)
│   │   └── training/               # Training scripts
│   ├── services/
│   │   ├── risk_manager.py         # 5-rule risk validation
│   │   ├── ml_service.py           # ML orchestrator
│   │   └── stock_service.py        # Stock data service
│   ├── scrapers/
│   │   ├── stock_scraper.py        # yfinance + pandas_ta
│   │   └── reddit_scraper.py       # PRAW + VADER sentiment
│   ├── tasks/                      # Celery background tasks
│   │   ├── ml_tasks.py             # Signal generation (uses SignalEngine)
│   │   ├── insider_tasks.py        # SEC Form 4 ingestion
│   │   ├── scraping_tasks.py       # Reddit + stock scraping
│   │   └── maintenance_tasks.py    # Cleanup + reports
│   └── celery_app.py               # Beat schedule + task routing
├── frontend/                       # Next.js 16 dashboard
│   ├── app/
│   │   ├── page.tsx                # Dashboard (watchlist + signals + trending)
│   │   ├── signals/page.tsx        # Signals (active/daily/history tabs)
│   │   └── ticker/[symbol]/page.tsx# Ticker detail (chart + ML + insider)
│   ├── components/                 # Reusable UI components
│   └── lib/api.ts                  # Typed API client
├── alembic/                        # 11 migrations
├── docker-compose.yml              # Celery worker + beat + Flower
├── Dockerfile                      # Multi-stage (dev + prod)
└── docs/                           # Architecture + strategy docs
```

---

## Getting Started

### Prerequisites
- Python 3.12+, Node.js 20+, Docker
- PostgreSQL (Neon free tier) + Redis (Redis Cloud free tier)
- UV package manager (`pip install uv`)

### Backend
```bash
cp .env.example .env          # Fill in credentials
uv sync                       # Install dependencies
uv run alembic upgrade head   # Run migrations
uv run uvicorn backend.api.main:app --reload  # Start API on :8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                   # Start on :3000 (proxies to :8000)
```

### Celery (Background Tasks)
```bash
# Worker
celery -A backend.celery_app worker --loglevel=info --queues=scraping,ml

# Beat scheduler
celery -A backend.celery_app beat --loglevel=info
```

### Docker (All Services)
```bash
docker-compose up -d          # Starts worker + beat + Flower
# API: http://localhost:8000
# Flower: http://localhost:5555
```

---

## Celery Beat Schedule

| Time (UTC) | Task | Queue |
|------------|------|-------|
| Every 30 min | Scrape Reddit | scraping |
| Every hour | Fetch stock data | scraping |
| 10:00 PM | Ingest SEC Form 4 insider trades | scraping |
| 10:30 PM | Generate trading signals (triangulation) | ml |
| Every 5 min | Monitor active signals (target/stop/expiry) | ml |

---

## Risk Math

```
Win rate: 45%    Avg win: +10%    Avg loss: -5%
Expected value per trade = (0.45 × 10) - (0.55 × 5) = 4.5 - 2.75 = +1.75%

100 trades × 1.75% edge = +175% cumulative return
Even at 45% accuracy, the system is profitable due to 1:2 R/R.
```

---

## Disclaimer

This project is for **educational and research purposes only**. Not financial advice. Do not use for live trading without extensive validation and regulatory compliance.

---

**Built as a learning project for ML engineering + quantitative trading systems.**
