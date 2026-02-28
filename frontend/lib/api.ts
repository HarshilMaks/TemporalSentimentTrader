const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchAPI<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Signals ─────────────────────────────────────────────────────────────

export interface Signal {
  id: number;
  ticker: string;
  signal: string;
  confidence: number;
  entry_price: number;
  target_price: number | null;
  stop_loss: number | null;
  risk_reward_ratio: number | null;
  position_size_pct: number | null;
  rsi_value: number | null;
  macd_value: number | null;
  sentiment_score: number | null;
  is_active: boolean;
  generated_at: string;
  expires_at: string | null;
  exit_price?: number;
  exit_reason?: string;
  closed_at?: string;
  pnl_pct?: number;
}

export const getActiveSignals = () =>
  fetchAPI<{ count: number; signals: Signal[] }>("/signals/active");

export const getSignalHistory = (limit = 50) =>
  fetchAPI<{ count: number; signals: Signal[] }>(`/signals/history?limit=${limit}`);

export const getSignalsByTicker = (ticker: string) =>
  fetchAPI<{ ticker: string; signals: Signal[] }>(`/signals/ticker/${ticker}`);

export const getDailyReport = () =>
  fetchAPI<{ date: string; count: number; signals: Signal[] }>("/signals/daily-report");

export const closeSignal = (id: number, exitPrice: number, reason = "manual") =>
  fetchAPI<{ status: string; signal: Signal }>(`/signals/${id}/close?exit_price=${exitPrice}&exit_reason=${reason}`, { method: "POST" });

// ── Predictions ─────────────────────────────────────────────────────────

export interface Prediction {
  id: number;
  ticker: string;
  signal: string;
  confidence: number;
  xgb_confidence: number | null;
  lgb_confidence: number | null;
  tft_confidence: number | null;
  feature_snapshot_id: string | null;
  predicted_at: string;
}

export const getLatestPredictions = () =>
  fetchAPI<{ count: number; predictions: Prediction[] }>("/predictions/latest");

export const getPredictionsByTicker = (ticker: string, limit = 30) =>
  fetchAPI<{ ticker: string; predictions: Prediction[] }>(`/predictions/ticker/${ticker}?limit=${limit}`);

export const triggerPredictionRun = () =>
  fetchAPI<{ status: string; task_id: string }>("/predictions/run", { method: "POST" });

// ── Sentiment ───────────────────────────────────────────────────────────

export interface TrendingTicker {
  ticker: string;
  mentions: number;
  avg_sentiment: number;
}

export interface SentimentDay {
  date: string;
  avg_sentiment: number;
  mentions: number;
}

export interface InsiderTrade {
  insider_name: string;
  insider_title: string | null;
  transaction_type: string;
  shares: number | null;
  dollar_value: number | null;
  transaction_date: string;
  filing_url: string | null;
}

export const getTrending = (days = 7, limit = 20) =>
  fetchAPI<{ period_days: number; tickers: TrendingTicker[] }>(`/sentiment/trending?days=${days}&limit=${limit}`);

export const getSentimentHistory = (ticker: string, days = 30) =>
  fetchAPI<{ ticker: string; history: SentimentDay[] }>(`/sentiment/ticker/${ticker}?days=${days}`);

export const getInsiderActivity = (ticker: string, days = 90) =>
  fetchAPI<{ ticker: string; trades: InsiderTrade[] }>(`/sentiment/insider/${ticker}?days=${days}`);

// ── Health ──────────────────────────────────────────────────────────────

export const getHealth = () =>
  fetch(process.env.NEXT_PUBLIC_API_URL?.replace("/api/v1", "") || "http://localhost:8000" + "/health").then((r) => r.json());
