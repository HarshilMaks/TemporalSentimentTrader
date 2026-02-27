# GOD MODE MASTER PLAN — 2-Day Sprint to Complete TFT Trader

**Created:** 2026-02-27  
**Source of Truth:** `Stock Prediction/Global Algorithmic Trading Blueprint.pdf` (V5)  
**Goal:** Complete end-to-end pipeline: Data → Features → ML Models → Inference → Signal Engine → Risk Validation → Dashboard  
**Timeline:** 2 days (GOD MODE)

---

## THE RULES

### What We ARE Building
- Zero-cost, EOD batch-processing swing trading signal generator
- Triangulation Method: 3 independent layers must align for a BUY signal
- Ensemble ML (TFT + LSTM + XGBoost + LightGBM) for validation
- Human-in-the-loop: generates signals, human reviews and executes
- US market only (for now)

### What We Are NOT Building
- No real-time WebSocket/TimescaleDB tick ingestion (unnecessary for swing trading, costs money)
- No India market support yet (get US working first)
- No broker integration (manual execution)
- No 80% accuracy fantasies (45-55% is realistic and profitable with risk math)
- No more Reddit/technical feature additions until insider + institutional layers exist

### The Math That Makes It Work
Even at 45% win rate with 1:2 risk/reward:
- 55 losses × -5% = -275%
- 45 wins × +10% = +450%
- **Net = +175% profit**
- The risk manager is the survival mechanism, not the ML models

---

## CURRENT STATE AUDIT

### Working Code (Keep & Build On)
| File | Lines | Status |
|---|---|---|
| `backend/scrapers/reddit_scraper.py` | ~10.5K | ✅ Production-ready with retry/backoff |
| `backend/scrapers/stock_scraper.py` | ~6.6K | ✅ yfinance + pandas-ta indicators |
| `backend/services/quality_scorer.py` | ~14.7K | ✅ 4-dimensional quality scoring |
| `backend/services/risk_manager.py` | ~20.3K | ✅ 6 validation rules, 29 tests |
| `backend/services/reddit_service.py` | ~12.2K | ✅ Quality-filtered scraping |
| `backend/services/stock_service.py` | ~7.6K | ✅ Stock data service |
| `backend/ml/features/build.py` | ~20K | ✅ 23-dimensional feature builder |
| `backend/ml/features/sequences.py` | ~11.7K | ✅ 30-day sequence builder |
| `backend/ml/features/importance.py` | ~15.2K | ✅ Feature importance tracking |
| `backend/ml/features/sentiment_timeseries.py` | ~8.3K | ✅ Sentiment time-series features |
| `backend/ml/training/train_ensemble.py` | ~10.7K | ✅ XGBoost + LightGBM training with MLflow |
| `backend/ml/training/tft_training.py` | ~14.7K | ✅ TFT + LSTM training with MLflow |
| `backend/ml/training/baseline_training.py` | ~12.8K | ✅ Baseline model training |
| `backend/ml/backtesting/backtest_engine.py` | ~24.1K | ✅ Comprehensive backtesting |
| `backend/ml/tracking/mlflow_logger.py` | ~11.7K | ✅ MLflow experiment tracking |
| `backend/ml/tracking/experiment_compare.py` | ~16.4K | ✅ Experiment comparison |
| `backend/ml/registry/model_registry.py` | ~18.9K | ✅ Model version management |
| `backend/utils/retry.py` | ~11.5K | ✅ Retry/backoff framework |
| `backend/utils/ticker_extractor.py` | ~8.3K | ✅ Enhanced ticker extraction |
| `backend/utils/sentiment.py` | ~3.5K | ✅ Custom VADER lexicon |
| `backend/celery_app.py` | ~3.8K | ✅ 7 scheduled tasks |
| `backend/tasks/scraping_tasks.py` | ~4.4K | ✅ Reddit + stock scraping tasks |
| `backend/tasks/ml_tasks.py` | ~5.9K | ✅ ML signal generation tasks |
| `backend/tasks/maintenance_tasks.py` | ~7.8K | ✅ Cleanup + reporting |
| `backend/api/main.py` | ~5.4K | ✅ FastAPI app |
| `backend/api/routes/posts.py` | ~20.7K | ✅ Reddit post endpoints |
| `backend/api/routes/stocks.py` | ~22.6K | ✅ Stock data endpoints |
| `backend/cache/redis_client.py` | ~12.9K | ✅ Redis caching |
| `backend/config/rate_limits.py` | ~9.3K | ✅ Rate limiting config |
| `backend/models/reddit.py` | ~1.7K | ✅ RedditPost ORM |
| `backend/models/stock.py` | ~1.5K | ✅ StockPrice ORM |
| `backend/models/trading_signal.py` | ~1.8K | ✅ TradingSignal ORM |
| `backend/models/feature_snapshot.py` | ~2.9K | ✅ FeatureSnapshot ORM |

### Empty Files (0 bytes) — MUST BUILD
| File | What It Needs |
|---|---|
| `backend/ml/models/xgboost_model.py` | XGBoost model wrapper class |
| `backend/ml/models/lightgbm_model.py` | LightGBM model wrapper class |
| `backend/ml/models/tft_model.py` | TFT/LSTM model architecture class |
| `backend/ml/models/ensemble.py` | Ensemble voting logic (weighted average) |
| `backend/ml/inference/predictor.py` | Load models → run inference → return predictions |
| `backend/services/ml_service.py` | Orchestrate: features → inference → risk → signal |
| `backend/utils/indicators.py` | Technical indicator calculations (RSI, MACD, BB, SMA) |
| `backend/models/prediction.py` | Prediction ORM model |
| `backend/api/routes/predictions.py` | Prediction API endpoints |
| `backend/api/routes/sentiment.py` | Sentiment API endpoints |
| `backend/api/middleware/auth.py` | Basic auth middleware |
| `backend/scrapers/news_scraper.py` | Skip for now (not in critical path) |
| `backend/ml/training/train_tft.py` | Skip (tft_training.py already handles this) |
| `backend/models/user.py` | Skip for now |

### Files That Don't Exist Yet — MUST CREATE
| File | What It Needs |
|---|---|
| `backend/strategy/insider_tracker.py` | SEC Form 4 scraper + parser |
| `backend/strategy/regime_filter.py` | SPY SMA200 market regime gate |
| `backend/strategy/signal_engine.py` | Triangulation scoring + signal generation |
| `backend/models/insider_trade.py` | InsiderTrade ORM model |
| `alembic/versions/XXX_add_insider_trades.py` | Migration for insider_trades table |
| `backend/tasks/insider_tasks.py` | Celery task for insider data ingestion |
| `backend/api/routes/signals.py` | Trading signal endpoints |

---

## THE 2-DAY PLAN

### DAY 1: BUILD THE BRAIN (ML Models + Inference + Insider Data)

**Block 1 (3 hours): ML Model Architectures — Fill the Empty Files**

The training scripts exist but reference model classes that don't exist. Fix this.

Task 1.1: `backend/utils/indicators.py`
- Calculate RSI (14-period), MACD (12,26,9), Bollinger Bands (20,2), SMA 50/200, Volume Ratio, OBV
- Input: DataFrame with OHLCV columns
- Output: DataFrame with indicator columns added
- Used by: feature builder, stock scraper enrichment

Task 1.2: `backend/ml/models/xgboost_model.py`
- Class `XGBoostModel` with `train()`, `predict()`, `predict_proba()`, `save()`, `load()`, `get_feature_importance()`
- Default params: max_depth=6, learning_rate=0.1, n_estimators=100, objective='binary:logistic'
- Input: feature vector (not sequence)
- Output: BUY/SELL/HOLD probabilities

Task 1.3: `backend/ml/models/lightgbm_model.py`
- Class `LightGBMModel` with same interface as XGBoost
- Default params: num_leaves=31, learning_rate=0.05, n_estimators=150
- Input: feature vector
- Output: BUY/SELL/HOLD probabilities

Task 1.4: `backend/ml/models/tft_model.py`
- Class `TFTModel` wrapping the TFT architecture from `tft_training.py`
- `train()`, `predict()`, `predict_proba()`, `save()`, `load()`
- Input: 30-day sequences from SequenceBuilder
- Output: BUY/SELL/HOLD probabilities

Task 1.5: `backend/ml/models/ensemble.py`
- Class `EnsembleModel` that combines all three models
- Weighted voting: XGBoost 40%, LightGBM 30%, TFT/LSTM 30%
- `predict()` returns signal + confidence
- Confidence threshold: only output BUY/SELL if confidence > 0.7, else HOLD

**Block 2 (2 hours): Inference Pipeline**

Task 2.1: `backend/models/prediction.py`
- ORM model: id, ticker, signal, confidence, xgb_confidence, lgb_confidence, tft_confidence, feature_snapshot_id, predicted_at
- Index on (ticker, predicted_at)

Task 2.2: `backend/ml/inference/predictor.py`
- Class `Predictor`
- `load_models()` — load ensemble from saved artifacts
- `predict_single(ticker, features)` → (signal, confidence, model_scores)
- `predict_batch(tickers, features_df)` → list of predictions
- Uses FeatureBuilder to get latest features, SequenceBuilder for TFT input

Task 2.3: `backend/services/ml_service.py`
- Class `MLService` — the orchestrator
- `generate_daily_signals()`:
  1. Call FeatureBuilder to get latest features for all tracked tickers
  2. Call Predictor to get ensemble predictions
  3. For each BUY/SELL prediction with confidence > 0.7:
     - Call RiskManager to validate
     - If approved: create TradingSignal record
     - If rejected: log rejection reason
  4. Return list of approved signals

**Block 3 (2 hours): Insider Data Layer (The Alpha)**

Task 3.1: `backend/models/insider_trade.py`
- ORM model: id, ticker, insider_name, insider_title, transaction_type (BUY/SELL), shares, dollar_value, transaction_date, filing_date, filing_url, source (SEC/SEBI), created_at
- Index on (ticker, transaction_date)

Task 3.2: Alembic migration for insider_trades table
- `alembic revision --autogenerate -m "add_insider_trades"`

Task 3.3: `backend/strategy/insider_tracker.py`
- Class `InsiderTracker`
- `fetch_sec_form4(days_back=7)` — scrape SEC EDGAR RSS feed for Form 4 filings
  - Parse XML: get insider name, title, ticker, shares, buy/sell, dollar amount
  - Filter: only keep BUY transactions (sells are noise)
  - Normalize to InsiderTrade records
- `calculate_insider_score(ticker, lookback_days=30)` → 0-30 score
  - CEO/CFO buy in last 7 days = 30 points
  - Director buy in last 7 days = 20 points
  - Multiple insiders buying = bonus points
  - No insider activity = 0 points

Task 3.4: `backend/tasks/insider_tasks.py`
- Celery task `ingest_insider_trades()` — runs daily after market close
- Calls InsiderTracker.fetch_sec_form4()
- Upserts into insider_trades table (deduplicate by filing_url)

**Block 4 (2 hours): Strategy Layer (Regime Filter + Signal Engine)**

Task 4.1: `backend/strategy/regime_filter.py`
- Class `RegimeFilter`
- `get_market_regime()`:
  - Fetch SPY daily close from yfinance
  - Calculate SMA 200
  - If SPY close > SMA200 → BULL regime (allow BUY signals)
  - If SPY close < SMA200 → BEAR regime (disable all BUY signals)
- Returns: regime (BULL/BEAR), spy_price, sma200_value

Task 4.2: `backend/strategy/signal_engine.py`
- Class `SignalEngine` — the Triangulation scoring system
- `calculate_triangulation_score(ticker)`:
  - `insider_score` (0-30): from InsiderTracker
  - `flow_score` (0-20): volume_ratio > 2.0 = 20pts, > 1.5 = 10pts
  - `sentiment_score` (0-20): Reddit sentiment > 0.3 AND mentions > 20 = 20pts
  - `technical_score` (0-30): RSI < 35 = 10pts, MACD crossover = 10pts, price > SMA50 = 10pts
  - Total: 0-100
- `generate_signals()`:
  1. Check regime filter — if BEAR, return empty (no buys)
  2. For each tracked ticker:
     - Calculate triangulation score
     - If score > 60: run through ML ensemble for validation
     - If ML confidence > 0.7: pass to risk manager
     - If risk approved: create TradingSignal
  3. Return approved signals

**Block 5 (1 hour): Wire It All Together**

Task 5.1: Update `backend/tasks/ml_tasks.py`
- Update `generate_daily_signals` task to use new SignalEngine
- Flow: RegimeFilter → SignalEngine.generate_signals() → persist to DB

Task 5.2: Update `backend/celery_app.py`
- Add insider_tasks to beat schedule (daily at 5:00 PM ET)
- Ensure signal generation runs after insider ingestion (5:30 PM ET)

Task 5.3: Update `backend/ml/features/build.py`
- Add insider features to feature vector:
  - `insider_buy_volume_7d`: sum of insider buy dollar amounts in last 7 days
  - `insider_buy_count_7d`: count of insider buy transactions in last 7 days
  - `has_insider_buy`: binary flag (1 if any insider bought in last 30 days)

---

### DAY 2: BUILD THE FACE (API + Frontend + Integration Testing)

**Block 6 (2 hours): API Endpoints**

Task 6.1: `backend/api/routes/signals.py`
- `GET /api/v1/signals/active` — all active trading signals
- `GET /api/v1/signals/history` — closed signals with P&L
- `GET /api/v1/signals/ticker/{ticker}` — signals for specific ticker
- `GET /api/v1/signals/daily-report` — today's generated signals with triangulation scores
- `POST /api/v1/signals/{id}/close` — manually close a signal (with exit_price, exit_reason)

Task 6.2: `backend/api/routes/predictions.py`
- `GET /api/v1/predictions/latest` — latest ensemble predictions for all tickers
- `GET /api/v1/predictions/ticker/{ticker}` — prediction history for ticker
- `POST /api/v1/predictions/run` — trigger manual prediction run

Task 6.3: `backend/api/routes/sentiment.py`
- `GET /api/v1/sentiment/trending` — top tickers by mention count + sentiment
- `GET /api/v1/sentiment/ticker/{ticker}` — sentiment history for ticker
- `GET /api/v1/sentiment/insider/{ticker}` — insider trading activity for ticker

Task 6.4: Register all new routes in `backend/api/main.py`

**Block 7 (3 hours): Frontend Dashboard**

Task 7.1: `frontend/app/page.tsx` — Main dashboard
- Trending stocks table (ticker, sentiment, insider activity, triangulation score)
- Active signals panel (BUY signals with entry/target/stop prices)
- Market regime indicator (BULL/BEAR badge based on SPY vs SMA200)
- Portfolio summary (active positions count, total P&L)

Task 7.2: `frontend/app/ticker/[symbol]/page.tsx` — Ticker detail page
- Price chart (use lightweight-charts or recharts)
- Sentiment timeline (sentiment score over last 30 days)
- Insider activity table (recent Form 4 filings)
- ML prediction panel (ensemble confidence, individual model scores)
- Signal history (past BUY/SELL signals with outcomes)

Task 7.3: `frontend/app/signals/page.tsx` — Signals page
- Active signals table with risk parameters
- Signal history with P&L tracking
- Daily report view

Task 7.4: `frontend/lib/api.ts` — API client
- Typed fetch wrappers for all backend endpoints
- Error handling

Task 7.5: `frontend/components/` — Shared components
- StockCard, SignalCard, SentimentBadge, RegimeBadge, TriangulationScore

**Block 8 (2 hours): Integration + Smoke Testing**

Task 8.1: End-to-end smoke test
- Manually trigger: scrape Reddit → scrape stocks → build features → run predictions → generate signals
- Verify signals appear in DB and API returns them

Task 8.2: Verify the full Celery pipeline
- Start all services with docker-compose
- Confirm scheduled tasks fire in correct order
- Confirm insider ingestion → feature build → signal generation chain works

Task 8.3: Frontend integration
- Verify dashboard loads and displays real data from API
- Verify ticker detail page shows sentiment + predictions

**Block 9 (1 hour): Documentation + Cleanup**

Task 9.1: Update `README.md`
- Reflect new Triangulation architecture
- Update feature list
- Update API endpoint list
- Add architecture diagram showing the 3-layer triangulation flow

Task 9.2: Update `.env.example`
- Add any new env vars (SEC API key if needed, ACTIVE_MARKET toggle)

Task 9.3: Verify `docker-compose.yml` starts everything cleanly

---

## DEPENDENCY GRAPH

```
DAY 1 MORNING:
  indicators.py ──→ xgboost_model.py ──→ ensemble.py ──→ predictor.py ──→ ml_service.py
                ──→ lightgbm_model.py ─┘                                        │
                ──→ tft_model.py ──────┘                                        │
                                                                                 │
  insider_trade.py (model) ──→ migration ──→ insider_tracker.py ──→ insider_tasks.py
                                                      │                          │
DAY 1 AFTERNOON:                                      │                          │
  regime_filter.py ──→ signal_engine.py ←─────────────┘                          │
                              │                                                  │
                              ├── uses insider_tracker.calculate_insider_score()  │
                              ├── uses ensemble.predict()                        │
                              ├── uses risk_manager.validate()                   │
                              └── creates TradingSignal records                  │
                                                                                 │
  update ml_tasks.py ←── update celery_app.py ←── update features/build.py      │
                                                                                 │
DAY 2 MORNING:                                                                   │
  routes/signals.py ──→ routes/predictions.py ──→ routes/sentiment.py ──→ main.py
                                                                                 │
DAY 2 AFTERNOON:                                                                 │
  frontend/page.tsx ──→ frontend/ticker/page.tsx ──→ frontend/signals/page.tsx   │
  frontend/lib/api.ts ──→ frontend/components/*                                  │
                                                                                 │
DAY 2 EVENING:                                                                   │
  smoke test ──→ celery pipeline test ──→ frontend integration ──→ README update │
```

---

## WHAT NOT TO DO (ANTI-PATTERNS)

1. **Don't add TimescaleDB or WebSocket tick ingestion** — EOD batch is correct for swing trading
2. **Don't build India market support** — US first, factory pattern later
3. **Don't build broker integration** — manual execution, human-in-the-loop
4. **Don't add more Reddit features** — the insider + institutional layers are the priority
5. **Don't over-engineer model architectures** — simple wrappers around sklearn/xgboost/lightgbm/pytorch
6. **Don't write tests during the sprint** — get it working first, test after
7. **Don't deploy to cloud** — local Docker is the zero-cost mandate
8. **Don't build auth/user system** — single-user tool, skip auth middleware
9. **Don't build news scraper** — not in critical path, Reddit + insider is enough
10. **Don't chase accuracy metrics** — the risk manager math is the edge, not prediction accuracy

---

## FEATURE VECTOR (25 Dimensions)

After Day 1, the feature vector for each ticker should contain:

**Technical (8):**
1. RSI (14-period)
2. MACD value
3. MACD signal
4. MACD histogram
5. Bollinger Band position (where price sits in band)
6. SMA 50
7. SMA 200
8. Volume Ratio (current / 20-day avg)

**Sentiment (6):**
9. Sentiment score (VADER compound)
10. Sentiment trend (5-day delta)
11. Mention count
12. Sentiment volatility (5-day std)
13. Sentiment momentum (rate of change)
14. Conviction score (mentions × abs(sentiment))

**Price (5):**
15. 1-day return
16. 5-day return
17. 10-day return
18. 20-day volatility
19. OBV (On-Balance Volume)

**Insider (3):**
20. insider_buy_volume_7d (dollar amount of insider buys)
21. insider_buy_count_7d (number of insider buy transactions)
22. has_insider_buy (binary: any insider bought in 30 days)

**Flow (2):**
23. volume_spike (binary: volume > 2x 20-day avg)
24. delivery_ratio (for future India support, placeholder for now)

**Regime (1):**
25. market_regime (1 = BULL, 0 = BEAR, based on SPY vs SMA200)

---

## TRIANGULATION SCORING

```
Score Component     | Max Points | Source
--------------------|------------|---------------------------
Insider Score       | 30         | SEC Form 4 (CEO/CFO buys)
Flow Score          | 20         | Volume anomalies
Sentiment Score     | 20         | Reddit sentiment + mentions
Technical Score     | 30         | RSI + MACD + SMA signals
--------------------|------------|---------------------------
TOTAL               | 100        |

BUY Signal: Score > 60 AND ML confidence > 0.7 AND regime = BULL AND risk manager approves
```

---

## RISK MANAGEMENT (Already Implemented — Don't Touch)

The risk_manager.py is solid. These rules are enforced:
- Confidence threshold: > 70%
- Max position size: 20% of portfolio
- Max risk per trade: 2% of portfolio
- Stop loss: -5% from entry
- Take profit: +7-10% from entry
- Risk/reward ratio: minimum 1:2
- Max concurrent positions: 5
- Portfolio drawdown limit: 15%

---

## SIGNAL FLOW (End-to-End)

```
4:00 PM ET — Market closes
4:15 PM ET — Celery Beat triggers:
  1. Stock scraper fetches EOD OHLCV for all tracked tickers
  2. Reddit scraper fetches latest posts
  3. Insider tracker fetches today's SEC Form 4 filings

5:00 PM ET — Feature pipeline:
  4. FeatureBuilder constructs 25-dimensional feature vectors
  5. SequenceBuilder creates 30-day sequences for TFT/LSTM

5:15 PM ET — ML inference:
  6. RegimeFilter checks SPY vs SMA200
  7. If BEAR → skip, log "market bearish, no signals"
  8. If BULL → SignalEngine calculates triangulation scores
  9. Tickers with score > 60 → run through Ensemble model
  10. Ensemble returns BUY/SELL/HOLD + confidence

5:30 PM ET — Risk validation:
  11. BUY signals with confidence > 0.7 → RiskManager validates
  12. Approved signals → saved to trading_signals table
  13. Rejected signals → logged with rejection reason

5:45 PM ET — Output:
  14. Daily intelligence report available via API
  15. Dashboard shows new signals
  16. Human reviews, verifies charts, executes manually
```

---

## DOCS/ FOLDER AFTER CLEANUP

| File | Status | Purpose |
|---|---|---|
| `GOD_MODE_MASTER_PLAN.md` | ✅ NEW (this file) | Single source of truth for all implementation |
| `REALITY_CHECK.md` | ✅ KEEP | Honest analysis of what's real vs. fantasy |
| `MLFLOW_SETUP.md` | ✅ KEEP | MLflow setup guide (still accurate) |
| `DEVELOPMENT.md` | ✅ KEEP | Docker dev setup guide (still accurate) |
| `credentials.md` | ✅ KEEP | Credential setup guide (still accurate) |
| `ARCHITECTURE.md` | 🗄️ ARCHIVED | Redirects to this file |
| `TRADING_STRATEGY.md` | 🗄️ ARCHIVED | Redirects to this file |
| `INSIDER_ARBITRAGE_GUIDE.md` | 🗄️ ARCHIVED | Redirects to this file |
| `IMPLEMENTATION.md` | 🗄️ ARCHIVED | Redirects to this file |

---

## SUCCESS CRITERIA (End of Day 2)

- [ ] All 13 empty .py files are filled with working code
- [ ] 7 new files created (strategy/, insider model, migration, tasks, routes)
- [ ] `python -c "from backend.strategy.signal_engine import SignalEngine"` works
- [ ] `python -c "from backend.ml.models.ensemble import EnsembleModel"` works
- [ ] `python -c "from backend.ml.inference.predictor import Predictor"` works
- [ ] API endpoint `/api/v1/signals/active` returns data
- [ ] API endpoint `/api/v1/predictions/latest` returns data
- [ ] Frontend dashboard loads and shows trending stocks + signals
- [ ] Celery pipeline runs end-to-end without errors
- [ ] README.md reflects the Triangulation architecture

---

*This is the only implementation document that matters. Everything else is archived.*
*Bible: `Stock Prediction/Global Algorithmic Trading Blueprint.pdf`*
