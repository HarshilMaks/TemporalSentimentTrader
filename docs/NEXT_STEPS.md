# TFT Trader — Status & Remaining Work

Last updated: 2026-02-28

---

## Completed

| # | Task | Date |
|---|------|------|
| 1 | GOD MODE Sprint (9 blocks) — full backend, ML, API, frontend | Feb 27 |
| 2 | Populate stock data (4,769 rows, 19 tickers, 1yr each) | Feb 27 |
| 3 | Train ML ensemble (XGBoost + LightGBM + LSTM) | Feb 27 |
| 4 | SEC insider trade ingestion (112 trades) | Feb 28 |
| 5 | Fix filing_url unique constraint (migration) | Feb 28 |
| 6 | Clean pyproject.toml (remove TF, pytorch-forecasting, auth deps) | Feb 27 |
| 7 | Add .dockerignore | Feb 27 |
| 8 | Create data/models directory structure | Feb 27 |
| 9 | Write scripts/train_models.py | Feb 28 |
| 10 | Docker: add API service, add alembic/ to Dockerfile | Feb 28 |
| 11 | Frontend: standalone output + Dockerfile | Feb 28 |
| 12 | Restore production thresholds (tri=60, ML=0.7, ensemble=0.70, risk=0.70) | Feb 28 |
| 13 | Replace delisted SQ with COIN in all watchlists | Feb 28 |
| 14 | Remove stale scripts (backtest.py, query_db.py, scrape_reddit.py, scheduled_scraper.py) | Feb 28 |
| 15 | **Step 1: Data Pipeline Purge** — Reddit JSON scraper, India RSS scraper, India insider scraper | Feb 28 |
| 16 | **Step 2: Sequential Pipeline Rewrite** — signal_engine.py rewritten to triangulate → ML → risk | Feb 28 |
| 17 | **Step 3: Telegram Webhook** — telegram_notifier.py, wired into signal engine | Feb 28 |
| 18 | Purge 550 mock posts from DB | Feb 28 |
| 19 | Fix 7 bugs in Celery tasks (wrong imports, stale fields, dedup logic) | Feb 28 |
| 20 | Rewire ml_service.py to delegate to SignalEngine | Feb 28 |
| 21 | Wire India insider scraper into Celery insider task | Feb 28 |
| 22 | Full documentation rewrite (README, ARCHITECTURE) | Feb 28 |

**Total bugs found and fixed: 29+**

---

## Remaining Work

### Must Do (Before Live Use)

1. **Set up Telegram bot** — message @BotFather, get token + chat_id, add to .env
2. **Accumulate data** — run Celery for 1-2 weeks to build up Reddit posts + insider trades. Triangulation needs data density to score ≥ 60.
3. **Retrain models** — after 2 weeks of real data, run `uv run python scripts/train_models.py` to retrain on real data instead of the initial training set.
4. **Fetch India stock data** — add India tickers to stock scraping (yfinance supports `.NS` suffix for NSE tickers).

### Nice to Have

5. **Expand US watchlist** — add mid-cap tickers (CRWD, DDOG, NET, PLTR, HOOD) where insider signals have higher information value.
6. **Telegram group scraping** — use Telethon to scrape public Indian stock Telegram groups for Layer 3 hype data.
7. **Backtest on historical data** — use `backend/ml/backtesting/backtest_engine.py` to validate the triangulation strategy on past data.
8. **Add India tickers to signal engine** — extend `DEFAULT_WATCHLIST` with `.NS` suffixed NSE tickers.
9. **Retrain ML to predict signal success** — currently trained on 5-day forward returns. Should be retrained on actual signal outcomes (did the +10% target hit before the -5% stop?).

### Frozen (Per Blueprint)

10. **MLOps infrastructure** — MLflow tracking, model registry, experiment comparison. All built but frozen until data pipes are proven clean and models are retrained on real signal outcomes.
