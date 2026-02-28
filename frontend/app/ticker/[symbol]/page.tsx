"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  getSentimentHistory,
  getInsiderActivity,
  getPredictionsByTicker,
  getSignalsByTicker,
  type SentimentDay,
  type InsiderTrade,
  type Prediction,
  type Signal,
} from "@/lib/api";
import { Panel, PanelHeader, PanelBody, Stat } from "@/components/card";
import { SignalBadge, ConfidencePill } from "@/components/badges";
import { SignalCard } from "@/components/signal-card";
import { SentimentChart } from "@/components/sentiment-chart";
import { PriceChart } from "@/components/price-chart";
import { formatCurrency } from "@/lib/utils";

export default function TickerPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const ticker = symbol?.toUpperCase() ?? "";

  const [sentiment, setSentiment] = useState<SentimentDay[]>([]);
  const [insiders, setInsiders] = useState<InsiderTrade[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    Promise.allSettled([
      getSentimentHistory(ticker),
      getInsiderActivity(ticker),
      getPredictionsByTicker(ticker),
      getSignalsByTicker(ticker),
    ]).then(([sentRes, insRes, predRes, sigRes]) => {
      if (sentRes.status === "fulfilled") setSentiment(sentRes.value.history);
      if (insRes.status === "fulfilled") setInsiders(insRes.value.trades);
      if (predRes.status === "fulfilled") setPredictions(predRes.value.predictions);
      if (sigRes.status === "fulfilled") setSignals(sigRes.value.signals);
      setLoading(false);
    });
  }, [ticker]);

  if (loading) {
    return <div className="flex items-center justify-center h-full text-muted-foreground text-xs">Loading {ticker}…</div>;
  }

  const latestPred = predictions[0];

  return (
    <div className="h-full overflow-y-auto">
      {/* Ticker header bar */}
      <div className="border-b border-border bg-surface-0 px-4 py-2 flex items-center gap-6">
        <span className="text-lg font-bold">{ticker}</span>
        {latestPred && (
          <>
            <SignalBadge signal={latestPred.signal} />
            <ConfidencePill value={latestPred.confidence} />
          </>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Chart + Prediction side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Price chart placeholder — shows sentiment area if no OHLC data */}
          <div className="lg:col-span-2">
            <Panel>
              <PanelHeader>Chart</PanelHeader>
              <PanelBody className="p-0">
                {sentiment.length > 0 ? (
                  <div className="p-3">
                    <SentimentChart data={sentiment} />
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-64 text-muted-foreground text-xs">
                    No chart data available
                  </div>
                )}
              </PanelBody>
            </Panel>
          </div>

          {/* ML Prediction panel */}
          <Panel>
            <PanelHeader>ML Ensemble</PanelHeader>
            <PanelBody>
              {latestPred ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <SignalBadge signal={latestPred.signal} />
                    <span className="text-lg font-bold font-mono">
                      {(latestPred.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="space-y-2">
                    <ModelBar label="XGBoost" weight="40%" value={latestPred.xgb_confidence} />
                    <ModelBar label="LightGBM" weight="30%" value={latestPred.lgb_confidence} />
                    <ModelBar label="TFT/LSTM" weight="30%" value={latestPred.tft_confidence} />
                  </div>
                  <div className="text-[10px] text-muted-foreground pt-2 border-t border-border">
                    {new Date(latestPred.predicted_at).toLocaleString()}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-muted-foreground py-4 text-center">No predictions</div>
              )}
            </PanelBody>
          </Panel>
        </div>

        {/* Insider Activity */}
        <Panel>
          <PanelHeader>
            <span>Insider Activity</span>
            <span className="text-[10px] font-mono">{insiders.length}</span>
          </PanelHeader>
          {insiders.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Insider</th>
                    <th className="px-3 py-2">Title</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2 text-right">Shares</th>
                    <th className="px-3 py-2 text-right">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {insiders.map((t, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-surface-1 transition-colors">
                      <td className="px-3 py-1.5 font-mono">{t.transaction_date}</td>
                      <td className="px-3 py-1.5 text-foreground">{t.insider_name}</td>
                      <td className="px-3 py-1.5 text-muted-foreground">{t.insider_title ?? "—"}</td>
                      <td className="px-3 py-1.5"><SignalBadge signal={t.transaction_type} /></td>
                      <td className="px-3 py-1.5 text-right font-mono">{t.shares?.toLocaleString() ?? "—"}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{t.dollar_value ? formatCurrency(t.dollar_value) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <PanelBody><div className="text-xs text-muted-foreground text-center py-4">No insider trades</div></PanelBody>
          )}
        </Panel>

        {/* Signal History */}
        <Panel>
          <PanelHeader>
            <span>Signal History</span>
            <span className="text-[10px] font-mono">{signals.length}</span>
          </PanelHeader>
          <PanelBody>
            {signals.length > 0 ? (
              <div className="grid md:grid-cols-2 gap-3">
                {signals.map((s) => (
                  <SignalCard key={s.id} signal={s} />
                ))}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground text-center py-4">No signals</div>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}

function ModelBar({ label, weight, value }: { label: string; weight: string; value: number | null }) {
  const pct = (value ?? 0) * 100;
  return (
    <div>
      <div className="flex justify-between text-[10px] mb-0.5">
        <span className="text-muted-foreground">{label} <span className="text-[9px]">({weight})</span></span>
        <span className="font-mono">{value?.toFixed(3) ?? "—"}</span>
      </div>
      <div className="w-full h-1 rounded-full bg-surface-2 overflow-hidden">
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
