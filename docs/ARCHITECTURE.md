# TFT Trader — System Architecture V5

**Last Updated:** 2026-02-27  
**Version:** 5.0 (Triangulation / Information Arbitrage)  
**Strategy:** Swing Trading (3-7 day holds) via EOD Batch Processing  
**Source of Truth:** `Stock Prediction/Global Algorithmic Trading Blueprint.pdf`

---

## Core Concept

Capture short-term momentum by triangulating three independent data layers. A BUY signal is only generated when insider activity, institutional flow, AND retail sentiment align simultaneously. This filters out ~90% of noise and leaves only high-probability setups.

The ML models exist to validate opportunities. The risk manager dictates survival. Even at a 45% win rate, the system is profitable due to enforced 1:2 risk/reward math.

---

## System Architecture

```
                          ┌─────────────────────────────┐
                          │     REGIME FILTER (Gate)     │
                          │  SPY vs SMA200 → BULL/BEAR  │
                          │  If BEAR → disable all BUYs │
                          └──────────────┬──────────────┘
                                         │ BULL only
                                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    TRIANGULATION ENGINE (Score 0-100)                │
│                                                                      │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐ │
│  │  LAYER 1: INSIDER │ │ LAYER 2: FLOW    │ │ LAYER 3: SENTIMENT   │ │
│  │  (0-30 points)    │ │ (0-20 points)    │ │ (0-20 points)        │ │
│  │                   │ │                  │ │                      │ │
│  │  SEC Form 4 buys  │ │  Volume spikes   │ │  Reddit sentiment    │ │
│  │  CEO/CFO/Director │ │  > 2x 20-day avg │ │  Mention count > 20  │ │
│  │  purchases        │ │  Unusual flow    │ │  Sentiment > 0.3     │ │
│  └──────────┬───────┘ └────────┬─────────┘ └──────────┬───────────┘ │
│             │                  │                       │             │
│             └──────────────────┼───────────────────────┘             │
│                                ▼                                     │
│                    ┌──────────────────────┐                          │
│                    │  TECHNICAL SCORE     │                          │
│                    │  (0-30 points)       │                          │
│                    │  RSI + MACD + SMA    │                          │
│                    └──────────┬───────────┘                          │
│                               │                                      │
│                    Total Score > 60?                                  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ YES
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    ML ENSEMBLE VALIDATION                            │
│                                                                      │
│  ┌────────────────┐ ┌────────────────┐ ┌──────────────────────────┐ │
│  │ XGBoost (40%)  │ │ LightGBM (30%) │ │ TFT/LSTM (30%)          │ │
│  │ Feature vector │ │ Feature vector │ │ 30-day sequences        │ │
│  └───────┬────────┘ └───────┬────────┘ └────────────┬─────────────┘ │
│          └──────────────────┼────────────────────────┘               │
│                             ▼                                        │
│                  Weighted Vote → Signal + Confidence                 │
│                  Confidence > 0.7?                                   │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ YES
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    RISK MANAGER (Final Gate)                          │
│                                                                      │
│  ✓ Confidence > 70%           ✓ Risk/reward > 1:2                   │
│  ✓ Position size < 20%        ✓ Max 5 concurrent positions          │
│  ✓ Risk per trade < 2%        ✓ Portfolio drawdown < 15%            │
│  ✓ Stop loss at -5%           ✓ Target at +7-10%                    │
│                                                                      │
│  APPROVED → TradingSignal saved to DB                               │
│  REJECTED → logged with rejection reason                            │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    HUMAN-IN-THE-LOOP                                  │
│                                                                      │
│  Daily intelligence report via API + Dashboard                       │
│  Human reviews flagged assets, verifies charts, executes manually    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Ingestion Layer

All ingestion runs as EOD batch jobs via Celery Beat after market close. No real-time tick ingestion. No WebSockets. No TimescaleDB. This keeps infrastructure cost at zero.

```
4:00 PM ET — Market closes

4:15 PM ET — Celery Beat triggers 3 parallel ingestion tasks:

  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────────┐
  │  Stock Scraper       │  │  Reddit Scraper      │  │  Insider Tracker      │
  │                      │  │                      │  │                       │
  │  yfinance EOD OHLCV  │  │  PRAW: WSB, stocks,  │  │  SEC EDGAR Form 4     │
  │  pandas-ta indicators│  │  investing            │  │  XML parsing          │
  │  RSI, MACD, BB, SMA  │  │  VADER sentiment      │  │  Filter: BUY only     │
  │  Volume ratio, OBV   │  │  Quality scoring      │  │  CEO/CFO/Director     │
  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬────────────┘
             │                        │                         │
             ▼                        ▼                         ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                         PostgreSQL                                       │
  │                                                                          │
  │  stock_prices    │  reddit_posts     │  insider_trades  │ trading_signals│
  │  OHLCV + tech    │  sentiment +      │  Form 4 buys    │ BUY/SELL/HOLD  │
  │  indicators      │  quality scores   │  insider names   │ risk params    │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Engineering Layer

The FeatureBuilder constructs a 25-dimensional daily snapshot per ticker by joining stock prices, Reddit sentiment, and insider filings. Weekend/holiday data is rolled into the next trading day to prevent lookahead bias.

**25-Dimensional Feature Vector:**

| # | Feature | Source | Type |
|---|---------|--------|------|
| 1 | RSI (14-period) | stock_prices | Technical |
| 2 | MACD value | stock_prices | Technical |
| 3 | MACD signal | stock_prices | Technical |
| 4 | MACD histogram | stock_prices | Technical |
| 5 | Bollinger Band position | stock_prices | Technical |
| 6 | SMA 50 | stock_prices | Technical |
| 7 | SMA 200 | stock_prices | Technical |
| 8 | Volume Ratio | stock_prices | Technical |
| 9 | Sentiment score | reddit_posts | Sentiment |
| 10 | Sentiment trend (5d) | reddit_posts | Sentiment |
| 11 | Mention count | reddit_posts | Sentiment |
| 12 | Sentiment volatility | reddit_posts | Sentiment |
| 13 | Sentiment momentum | reddit_posts | Sentiment |
| 14 | Conviction score | reddit_posts | Sentiment |
| 15 | 1-day return | stock_prices | Price |
| 16 | 5-day return | stock_prices | Price |
| 17 | 10-day return | stock_prices | Price |
| 18 | 20-day volatility | stock_prices | Price |
| 19 | OBV | stock_prices | Price |
| 20 | Insider buy volume (7d) | insider_trades | Insider |
| 21 | Insider buy count (7d) | insider_trades | Insider |
| 22 | Has insider buy (30d) | insider_trades | Insider |
| 23 | Volume spike (binary) | stock_prices | Flow |
| 24 | Delivery ratio | placeholder | Flow |
| 25 | Market regime | SPY vs SMA200 | Regime |

---

## ML Ensemble Layer

Three model types with different strengths, combined via weighted voting:

| Model | Weight | Input | Strength |
|-------|--------|-------|----------|
| XGBoost | 40% | Feature vector (25-d) | Feature importance, hard thresholds, most reliable |
| LightGBM | 30% | Feature vector (25-d) | Fast inference, good generalization |
| TFT/LSTM | 30% | 30-day sequences | Temporal patterns, sentiment buildup over time |

**Ensemble Logic:**
```
final_proba = 0.40 × xgb_proba + 0.30 × lgb_proba + 0.30 × tft_proba
signal = argmax(final_proba)        # BUY / SELL / HOLD
confidence = max(final_proba)       # 0.0 - 1.0
if confidence < 0.7: signal = HOLD  # not confident enough
```

---

## Triangulation Scoring

```
Component        │ Max Points │ Criteria
─────────────────┼────────────┼──────────────────────────────────────
Insider Score    │     30     │ CEO/CFO buy (7d) = 30, Director = 20
Flow Score       │     20     │ Volume > 2x avg = 20, > 1.5x = 10
Sentiment Score  │     20     │ Sentiment > 0.3 AND mentions > 20
Technical Score  │     30     │ RSI < 35 (10) + MACD cross (10) + > SMA50 (10)
─────────────────┼────────────┼──────────────────────────────────────
TOTAL            │    100     │ BUY trigger: score > 60
```

---

## Risk Management

Every signal passes through the risk manager before becoming actionable. No exceptions.

| Rule | Value | Purpose |
|------|-------|---------|
| Min confidence | 70% | Quality over quantity |
| Max position size | 20% of portfolio | Diversification |
| Max risk per trade | 2% of portfolio | Capital preservation |
| Stop loss | -5% from entry | Limit downside |
| Take profit | +7-10% from entry | Lock in gains |
| Min risk/reward | 1:2 | Favorable odds |
| Max concurrent positions | 5 | Manageable exposure |
| Max portfolio drawdown | 15% | Circuit breaker |

**Why this works even at 45% accuracy:**
- 100 trades: 55 losses × -5% = -275%
- 100 trades: 45 wins × +10% = +450%
- Net: +175% profit

---

## Daily Signal Flow

```
4:00 PM ET ─── Market closes
4:15 PM ET ─── Ingestion: stock scraper + Reddit scraper + insider tracker
5:00 PM ET ─── FeatureBuilder: 25-d vectors + 30-day sequences
5:15 PM ET ─── RegimeFilter: SPY vs SMA200 → BULL or BEAR
             │
             ├─ BEAR → log "market bearish", no signals generated
             │
             └─ BULL → SignalEngine: triangulation scores for all tickers
                         │
                         ├─ Score < 60 → skip
                         │
                         └─ Score ≥ 60 → ML Ensemble validation
                                          │
                                          ├─ Confidence < 0.7 → HOLD, skip
                                          │
                                          └─ Confidence ≥ 0.7 → RiskManager
                                                                  │
                                                                  ├─ Rejected → log reason
                                                                  │
                                                                  └─ Approved → save TradingSignal
5:45 PM ET ─── Daily report available via API + Dashboard
             Human reviews, verifies charts, executes manually
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API | FastAPI | Async REST API with auto-docs |
| Database | PostgreSQL (Neon) | Primary data store |
| ORM | SQLAlchemy 2.0 | Async database access |
| Migrations | Alembic | Schema versioning |
| Task Queue | Celery + Redis | Scheduled EOD batch jobs |
| Cache | Redis | Task queue + data caching |
| ML: Trees | XGBoost, LightGBM | Tabular feature models |
| ML: Deep | PyTorch (TFT/LSTM) | Sequence models |
| ML: Tracking | MLflow | Experiment tracking + model registry |
| Stock Data | yfinance | Free EOD OHLCV data |
| Indicators | pandas-ta | RSI, MACD, BB, SMA |
| Reddit | PRAW | Reddit API scraping |
| Sentiment | vaderSentiment | Custom stock market lexicon |
| Insider Data | SEC EDGAR | Form 4 XML filings |
| Frontend | Next.js 15 + TypeScript | Dashboard |
| Styling | Tailwind CSS | UI |
| Charts | Recharts / lightweight-charts | Price + sentiment visualization |
| Containers | Docker + Docker Compose | Zero-cost local deployment |

---

## Database Schema

### stock_prices
OHLCV + technical indicators. One row per ticker per trading day.
- Columns: ticker, open, high, low, close, adjusted_close, volume, rsi, macd, macd_signal, bb_upper, bb_lower, sma_50, sma_200, volume_ratio, date
- Unique constraint: (ticker, date)

### reddit_posts
Scraped posts with sentiment analysis and quality scoring.
- Columns: post_id, title, text, subreddit, tickers[], sentiment_score, quality_score, quality_tier, is_quality, score, num_comments, upvote_ratio, created_at
- GIN index on tickers array

### insider_trades
SEC Form 4 filings tracking corporate insider purchases.
- Columns: ticker, insider_name, insider_title, transaction_type, shares, dollar_value, transaction_date, filing_date, filing_url, source
- Index on (ticker, transaction_date)

### trading_signals
Generated BUY/SELL/HOLD signals with risk parameters.
- Columns: ticker, signal, confidence, entry_price, target_price, stop_loss, risk_reward_ratio, position_size_pct, rsi_value, macd_value, sentiment_score, sentiment_trend, is_active, exit_price, exit_reason, generated_at, closed_at
- Index on (ticker, is_active)

### feature_snapshots
Versioned feature engineering outputs for ML reproducibility.
- Columns: snapshot_id (UUID), ticker, features (JSON), created_at

---

## Repository Structure

```
tft-trader/
├── backend/
│   ├── api/                        # FastAPI application
│   │   ├── main.py                 # Entry point, route registration
│   │   ├── routes/
│   │   │   ├── posts.py            # Reddit post endpoints
│   │   │   ├── stocks.py           # Stock data endpoints
│   │   │   ├── signals.py          # Trading signal endpoints
│   │   │   ├── predictions.py      # ML prediction endpoints
│   │   │   └── sentiment.py        # Sentiment + insider endpoints
│   │   ├── schemas/                # Pydantic request/response models
│   │   └── middleware/             # Rate limiting
│   ├── strategy/                   # Trading strategy layer
│   │   ├── insider_tracker.py      # SEC Form 4 ingestion
│   │   ├── regime_filter.py        # SPY SMA200 market regime gate
│   │   └── signal_engine.py        # Triangulation scoring + signal gen
│   ├── ml/
│   │   ├── models/                 # Model architectures
│   │   │   ├── xgboost_model.py    # XGBoost wrapper
│   │   │   ├── lightgbm_model.py   # LightGBM wrapper
│   │   │   ├── tft_model.py        # TFT/LSTM architecture
│   │   │   └── ensemble.py         # Weighted voting ensemble
│   │   ├── features/               # Feature engineering
│   │   │   ├── build.py            # 25-d feature builder
│   │   │   ├── sequences.py        # 30-day sequence builder
│   │   │   ├── importance.py       # Feature importance tracking
│   │   │   └── sentiment_timeseries.py
│   │   ├── inference/
│   │   │   └── predictor.py        # Load models → run predictions
│   │   ├── training/               # Training scripts with MLflow
│   │   │   ├── train_ensemble.py   # XGBoost + LightGBM
│   │   │   ├── tft_training.py     # TFT + LSTM
│   │   │   └── baseline_training.py
│   │   ├── backtesting/
│   │   │   └── backtest_engine.py  # Walk-forward backtesting
│   │   ├── tracking/               # MLflow integration
│   │   │   ├── mlflow_logger.py
│   │   │   └── experiment_compare.py
│   │   └── registry/
│   │       └── model_registry.py   # Model version management
│   ├── scrapers/
│   │   ├── reddit_scraper.py       # PRAW + VADER + quality scoring
│   │   └── stock_scraper.py        # yfinance + pandas-ta
│   ├── services/
│   │   ├── reddit_service.py       # Reddit business logic
│   │   ├── stock_service.py        # Stock business logic
│   │   ├── ml_service.py           # ML orchestrator
│   │   ├── risk_manager.py         # 6-rule risk validation
│   │   └── quality_scorer.py       # Post quality scoring
│   ├── tasks/                      # Celery scheduled tasks
│   │   ├── scraping_tasks.py       # Reddit + stock ingestion
│   │   ├── insider_tasks.py        # SEC Form 4 ingestion
│   │   ├── ml_tasks.py             # Signal generation pipeline
│   │   └── maintenance_tasks.py    # Cleanup + reporting
│   ├── models/                     # SQLAlchemy ORM models
│   │   ├── stock.py
│   │   ├── reddit.py
│   │   ├── trading_signal.py
│   │   ├── insider_trade.py
│   │   ├── feature_snapshot.py
│   │   └── prediction.py
│   ├── utils/
│   │   ├── indicators.py           # Technical indicator calculations
│   │   ├── sentiment.py            # Custom VADER lexicon
│   │   ├── ticker_extractor.py     # Ticker extraction + validation
│   │   ├── retry.py                # Retry/backoff framework
│   │   └── logger.py
│   ├── config/
│   │   ├── settings.py             # Pydantic settings from .env
│   │   └── rate_limits.py
│   ├── cache/
│   │   └── redis_client.py
│   ├── database/
│   │   └── config.py               # SQLAlchemy async engine
│   └── celery_app.py               # Celery config + beat schedule
├── frontend/                       # Next.js 15 dashboard
│   ├── app/
│   │   ├── page.tsx                # Main dashboard
│   │   ├── ticker/[symbol]/page.tsx # Ticker detail
│   │   └── signals/page.tsx        # Signals view
│   ├── components/                 # Shared UI components
│   └── lib/
│       └── api.ts                  # Typed API client
├── alembic/                        # Database migrations
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
└── docs/
    ├── GOD_MODE_MASTER_PLAN.md     # Implementation plan
    ├── ARCHITECTURE.md             # This file
    ├── REALITY_CHECK.md            # Honest project analysis
    ├── MLFLOW_SETUP.md             # MLflow guide
    ├── DEVELOPMENT.md              # Docker dev setup
    └── credentials.md              # Credential setup
```

---

## Design Principles

**EOD Batch, Not Real-Time:** Swing trading (3-7 day holds) does not require millisecond tick data. All processing runs once daily after market close using free public data. This eliminates cloud compute costs entirely.

**Triangulation, Not Single-Signal:** Never trade on one data source alone. Insider + flow + sentiment must converge. This filters 90% of noise.

**Risk-First, Not Accuracy-First:** The risk manager is the edge, not the ML models. 45% accuracy is profitable with 1:2 risk/reward. The system is designed to survive, not to be right.

**Human-In-The-Loop:** This is a signal generator, not an autonomous trading bot. The system flags opportunities; the human verifies and executes.

**Zero-Cost Infrastructure:** Everything runs locally via Docker. PostgreSQL, Redis, Celery, MLflow — all containerized. No cloud bills.

---

*Version 5.0 — Triangulation / Information Arbitrage Architecture*  
*Bible: `Stock Prediction/Global Algorithmic Trading Blueprint.pdf`*
