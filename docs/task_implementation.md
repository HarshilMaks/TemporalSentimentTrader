# TFT Trader — Task Implementation & Weekly Roadmap (Polished)

Version: 1.2
Last updated: 2026-02-15T15:03:17Z
Author: TFT Trader Development Team

Purpose
-------
Provide a single, actionable source of truth that converts the project roadmap into a week-by-week implementation plan. This file documents: what is currently implemented, what is actively in progress, a point-wise analysis of gaps and risks, detailed weekly tasks (Weeks 2–12), prioritized TODOs, and an immediate 2-week sprint with explicit acceptance criteria and owner suggestions.

Current snapshot (what's implemented and ongoing)
-------------------------------------------------
Note: "Evidence" lines point to repository paths that demonstrate implemented code.

1) Scrapers: Reddit & Stock
- Status: In progress (core scrapers present; operational verification outstanding)
- What exists: backend/scrapers/reddit_scraper.py, backend/scrapers/stock_scraper.py, backend/scrapers/mock_reddit.py
- Explanation: Code extracts tickers, computes sentiment and indicators; stock scraper computes OHLCV and some indicators using yfinance/pandas-ta utilities in backend/utils/indicators.py.
- Blockers: PRAW credentials, handling Reddit rate limits, missing robust integration tests for edge cases.
- Next actions (immediate): add .env.example, implement exponential backoff + retry, add unit tests for ticker extraction and edge posts.
- Priority: Critical for all downstream tasks.

2) Task orchestration (Celery + Scheduler)
- Status: Present but needs verification in dev/staging
- What exists: backend/celery_app.py, backend/tasks/scraping_tasks.py, scripts/scheduled_scraper.py
- Explanation: Celery app is configured; scraping tasks are defined and a standalone scheduled script exists for local execution.
- Blockers: Celery workers and beat not validated in CI; Redis connection and recommended concurrency not documented.
- Next actions: Add docker-compose dev setup for Redis + worker, add healthcheck endpoints and a simple CI check that starts a worker and runs a sample task.
- Priority: High.

3) Database & Migrations
- Status: Implemented
- What exists: alembic/versions/*, backend/models/* (stock, reddit, trading_signal)
- Explanation: Database schema for reddit_posts, stock_prices and trading_signals defined and migrations present.
- Blockers: None major; ensure migration workflow documented (.env, DB URL)
- Next actions: Add sample seed data scripts for dev.
- Priority: Medium.

4) Feature engineering
- Status: Partially implemented
- What exists: backend/utils/indicators.py, components in backend/ml/* that assume prepared features
- Explanation: Indicator utilities exist but a formal, versioned feature builder pipeline (persisting features with metadata) is not yet in place.
- Blockers: No canonical features table or parquet snapshot that training scripts can rely on.
- Next actions: Implement backend/ml/features/ builder that writes to DB or parquet and records a snapshot id.
- Priority: High for ML reproducibility.

5) ML models & training
- Status: Implemented (models present) but training infra needs reproducibility improvements
- What exists: backend/ml/models/{xgboost_model.py, lightgbm_model.py, tft_model.py, ensemble.py}, backend/ml/training/train_ensemble.py
- Explanation: Core model code and training scripts exist (including a TFT sequence model); however experiment tracking (MLflow) and consistent dataset snapshots are missing.
- Blockers: No model registry, drift detection, or tuning automation configured.
- Next actions: Integrate MLflow (or equivalent), persist artifacts with metadata, add basic hyperparameter search job.
- Priority: High.

6) Inference & Risk manager
- Status: Partially implemented (inference pieces exist; risk manager missing)
- What exists: backend/ml/inference/predictor.py, backend/services/ml_service.py; risk manager file NOT present
- Explanation: Prediction logic exists but risk validation rules described in ARCHITECTURE.md are not implemented in a single service file for signal gating.
- Blockers: Missing backend/services/risk_manager.py prevents safe automated signal persistence/execution.
- Next actions: Implement risk_manager skeleton and unit tests for rules (confidence, position sizing, max concurrent positions).
- Priority: Critical before any automated execution path.

7) Frontend
- Status: Starter code present, UI milestone not complete
- What exists: frontend/ directory and backend/api/routes/{stocks.py,predictions.py,posts.py}
- Explanation: The backend exposes routes but frontend pages and integration need to be verified and built (dashboard, ticker detail, auth).
- Blockers: No confirmed build + test of the Next.js app in repo CI; TradingView chart integration to be completed.
- Next actions: Wire API endpoints, implement login, dashboard and ticker pages, and add E2E tests.
- Priority: Medium.

8) CI/CD, Monitoring & Deployment
- Status: Partial
- What exists: Dockerfile, docker-compose.yml, Makefile
- Explanation: Containerization and local compose exist; GitHub Actions and production monitoring (Sentry, Prometheus) are not configured.
- Blockers: No CI pipelines or staging deployment runs recorded.
- Next actions: Add GitHub Actions that run tests, lint and build images; add Sentry test instrumentation and /metrics endpoint for Prometheus.
- Priority: High for production readiness.

9) Tests & QA
- Status: Partial
- What exists: tests/test_scraper.py, tests/test_celery.py
- Explanation: Some unit tests present; integration and E2E tests missing.
- Blockers: Missing test coverage for feature builder, risk_manager, and inference pipeline.
- Next actions: Expand tests and add CI jobs to run them.
- Priority: High.

Weekly implementation plan (concise & actionable)
-------------------------------------------------
For each week below: Goal • Why • 3–6 tasks • Deliverables • Acceptance criteria • Owner (recommended)

Week 2 (now) — Real Data integration
- Goal: Make scrapers production-ready and schedule hourly ingestion.
- Why: Foundation for all downstream features and models.
- Tasks (top-priority):
  1. Add .env.example and docs describing required secrets (PRAW, YFinance config, Redis, Postgres).
  2. Harden reddit_scraper with robust retry/backoff and add tests for ticker extraction edge-cases.
  3. Add data validation (dedupe, schema checks) before DB insert and a dev-mode that writes to local parquet.
  4. Create docker-compose.dev with redis, postgres and a sample celery worker + beat.
- Deliverables: .env.example, unit tests, compose dev file, sample DB inserts from scraper.
- Acceptance: pytest passes; scheduled scraper run writes validated rows to DB; worker starts via docker-compose.
- Owner: Backend Lead

Week 3 — Feature builder + snapshots
- Goal: Produce a reproducible features dataset and a sequence builder for ML input.
- Tasks:
  1. Implement backend/ml/features/build.py to output a features table (DB or parquet) and record snapshot_id.
  2. Implement 30-day sequence builder util and vectorizer for tree models.
  3. Add automated unit tests and a small sample data integration test.
- Deliverables: features snapshot, sequence arrays, tests.
- Acceptance: Feature snapshot created and sequence arrays shape verified.
- Owner: ML Lead

Week 4 — Baseline training, logging, and backtest
- Goal: Train baseline models, log runs, and run backtests.
- Tasks:
  1. Integrate MLflow (or a file-based run log) into training scripts.
  2. Run baseline training for XGBoost, LightGBM and TFT; persist artifacts.
  3. Add a backtest script that consumes signals and computes P&L and drawdown.
- Deliverables: artifacts + backtest report.
- Acceptance: Runs recorded in MLflow; backtest generates metrics table.
- Owner: ML Lead

Week 5 — Tuning & ensemble validation
- Goal: Improve model robustness with automated tuning and validate ensemble weights.
- Tasks:
  1. Add Optuna tuning jobs for tree models; run at small scale.
  2. Add walk-forward validation script to avoid lookahead bias.
  3. Validate and store ensemble weights and calibration parameters.
- Deliverables: best hyperparams; validated ensemble.
- Owner: ML Lead

Week 6 — Inference + Risk Manager + scheduled signals
- Goal: Safely create daily signals and persist them after risk checks.
- Tasks:
  1. Implement /api/predict endpoint and a Celery daily job to call it and persist signals.
  2. Implement backend/services/risk_manager.py with unit tests for rules (confidence, position sizing, max positions).
  3. Add a webhook/log notification for candidate signals.
- Deliverables: endpoint + scheduled job + risk_manager tests.
- Acceptance: Scheduled job writes trading_signals only for signals that pass risk checks.
- Owner: Backend + ML

Week 7–8 — Frontend baseline & watchlist
- Goal: Basic dashboard, ticker pages and watchlist.
- Tasks:
  1. Implement Dashboard, Ticker detail, Auth pages; wire to backend routes.
  2. Implement watchlist CRUD API and client UI.
  3. Add TradingView / Recharts for charting and sentiment timeline.
- Deliverables: working UI with auth and watchlist.
- Acceptance: User can login, add watchlist, view live/updating ticker details.
- Owner: Frontend Lead

Week 9–10 — Real-time, polishing, QA
- Goal: Add WebSockets, polish UI and finalize tests.
- Tasks:
  1. Implement WebSocket price feed and client subscriptions.
  2. Add sentiment feed and Reddit posts timeline on ticker page.
  3. Add E2E tests and accessibility checks.
- Deliverables: Real-time dashboard and test suite.
- Acceptance: Dashboard updates within <5s in simulated environment; E2E flows pass.
- Owner: Frontend + QA

Week 11 — CI/CD & Observability
- Goal: Build CI pipelines and add basic observability.
- Tasks:
  1. Add GitHub Actions for tests, lint, build and optional image push.
  2. Integrate Sentry SDK and a /metrics endpoint for Prometheus.
  3. Add deployment smoke-tests.
- Deliverables: CI runs on PRs; Sentry test event visible.
- Acceptance: CI passes on PR; Sentry receives test event.
- Owner: DevOps

Week 12 — Production deployment & smoke-tests
- Goal: Deploy to staging/production, run smoke tests and finalize runbooks.
- Tasks:
  1. Provision Neon Postgres, managed Redis, Vercel frontend; deploy containers to Render/Railway.
  2. Run smoke tests and small load tests; document rollback and retraining runbooks.
- Deliverables: Live staging/production, runbook, smoke-test report.
- Acceptance: Live app reachable; smoke tests pass; monitoring alerts configured.
- Owner: DevOps + Team Leads

Global prioritized TODOs (by priority)
-------------------------------------
Critical
- Add .env.example and secure secrets documentation.
- Implement backend/services/risk_manager.py and unit tests.
- Verify scrapers with real API credentials and add retry/backoff.
High
- Implement feature builder and snapshotting.
- Integrate MLflow and persist artifacts with metadata.
- Create a scheduled inference job that writes signals to DB.
Medium
- Implement frontend dashboard and watchlist.
- Add GitHub Actions for CI.
Low
- Broker integration (Alpaca/IB) — future work and gated by risk manager and regulatory considerations.

Immediate 2-week sprint (actionable checklist)
---------------------------------------------
Sprint goal: Reach a reproducible pipeline end-to-end: Scraper -> Feature snapshot -> Train -> Inference -> Risked signal persist (on staging data).

Tasks (owner: Backend + ML):
- [ ] Add .env.example and docs/credentials.md (Backend) — cmd: create file and PR
- [ ] Add unit tests for reddit_scraper and stock_scraper (Backend) — cmd: pytest tests/test_scraper.py
- [ ] Implement feature builder that outputs a features snapshot (ML) — cmd: python -m backend.ml.training.build_features --sample AAPL
- [ ] Implement risk_manager skeleton and tests (Backend) — create backend/services/risk_manager.py
- [ ] Wire a daily scheduled inference Celery task writing to trading_signals (Backend+ML)

Sprint acceptance criteria
- All test cases for scrapers and risk_manager pass locally (pytest)
- Feature snapshot produced and used by training script to create an artifact
- Daily inference job runs locally and writes at least one risk-validated signal to DB (staging)

Recommended quick commands
--------------------------
- DB migrations: alembic upgrade head
- Start local infra: docker-compose up -d redis postgres
- Start Celery worker & beat:
  - celery -A backend.celery_app worker --loglevel=info
  - celery -A backend.celery_app beat --loglevel=info
- Run scraper manually: python scripts/scheduled_scraper.py
- Run training (dev): python backend/ml/training/train_ensemble.py --config configs/train.yaml
- Run tests: pytest -q

Notes & recommendations (technical choices)
-------------------------------------------
- Sequence model: repository includes tft_model.py (Temporal Fusion Transformer). If TFT is stable and documented, prefer it over hand-rolled LSTM — TFT often generalizes better for multivariate time-series. If LSTM is preferred for simplicity, implement a compact LSTM training script and keep TFT as advanced option.
- Experiment tracking: MLflow is recommended (lightweight and well-supported). Use local MLflow for dev, push to remote tracking server for production.
- Monitoring & drift: Track simple metrics (daily accuracy, prediction distribution shifts, feature nulls) and add alerting thresholds before automated retraining.

How to keep this document current
---------------------------------
- Update status lines (Completed / In Progress / Blocked) and add evidence (file paths, PR links) after every sprint.
- For major changes add a changelog header with date and short summary.

Appendix — Quick evidence pointers
----------------------------------
- Scrapers & utils: backend/scrapers/* and backend/utils/*
- Celery & tasks: backend/celery_app.py and backend/tasks/*
- ML models & training: backend/ml/models/* and backend/ml/training/*
- API routes: backend/api/routes/*
- DevOps: Dockerfile, docker-compose.yml, Makefile

End of document — use this as the sprint source of truth; update with brief evidence notes after completing each task.
