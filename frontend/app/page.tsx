"use client";

import { useEffect, useState } from "react";
import {
  getActiveSignals,
  getTrending,
  getDailyReport,
  type Signal,
  type TrendingTicker,
} from "@/lib/api";
import { Panel, PanelHeader, PanelBody, Stat } from "@/components/card";
import { RegimeBadge } from "@/components/badges";
import { SignalRow } from "@/components/signal-card";
import { WatchlistRow } from "@/components/stock-card";

export default function Dashboard() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [trending, setTrending] = useState<TrendingTicker[]>([]);
  const [dailyCount, setDailyCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getActiveSignals(),
      getTrending(7, 20),
      getDailyReport(),
    ]).then(([sigRes, trendRes, dailyRes]) => {
      if (sigRes.status === "fulfilled") setSignals(sigRes.value.signals);
      if (trendRes.status === "fulfilled") setTrending(trendRes.value.tickers);
      if (dailyRes.status === "fulfilled") setDailyCount(dailyRes.value.count);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-xs">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Sidebar — Watchlist */}
      <aside className="w-56 border-r border-border bg-surface-0 shrink-0 flex flex-col overflow-hidden">
        <div className="px-3 py-2 border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
          Watchlist
        </div>
        <div className="flex-1 overflow-y-auto">
          {trending.map((t) => (
            <WatchlistRow key={t.ticker} ticker={t} />
          ))}
          {trending.length === 0 && (
            <div className="px-3 py-4 text-xs text-muted-foreground text-center">No data</div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Top stats bar */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Market</span>
            <RegimeBadge regime="BULL" />
          </div>
          <Stat label="Active" value={signals.length} />
          <Stat label="Today" value={dailyCount} />
          <Stat label="Watchlist" value={trending.length} />
        </div>

        {/* Active Signals */}
        <Panel>
          <PanelHeader>
            <span>Active Signals</span>
            <span className="text-[10px] font-mono">{signals.length}</span>
          </PanelHeader>
          {signals.length === 0 ? (
            <PanelBody>
              <div className="text-center text-muted-foreground text-xs py-6">
                No active signals — next scan at 5:30 PM ET
              </div>
            </PanelBody>
          ) : (
            <div>
              {/* Table header */}
              <div className="flex items-center gap-3 px-3 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                <span className="w-12">Ticker</span>
                <span className="w-10">Side</span>
                <span className="w-20">Conf</span>
                <span className="ml-auto w-16 text-right">Entry</span>
                <span className="w-16 text-right">Target</span>
                <span className="w-16 text-right">Stop</span>
              </div>
              {signals.map((s) => (
                <SignalRow key={s.id} signal={s} />
              ))}
            </div>
          )}
        </Panel>

        {/* Trending grid */}
        <Panel>
          <PanelHeader>Trending Tickers</PanelHeader>
          <PanelBody>
            {trending.length === 0 ? (
              <div className="text-center text-muted-foreground text-xs py-4">No trending data</div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-2">
                {trending.slice(0, 10).map((t) => (
                  <a
                    key={t.ticker}
                    href={`/ticker/${t.ticker}`}
                    className="bg-surface-1 border border-border rounded px-2.5 py-2 hover:border-border-hover transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs">{t.ticker}</span>
                      <span className={`text-[11px] font-mono ${t.avg_sentiment > 0 ? "text-bull" : "text-bear"}`}>
                        {t.avg_sentiment > 0 ? "+" : ""}{t.avg_sentiment.toFixed(2)}
                      </span>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{t.mentions} mentions</div>
                  </a>
                ))}
              </div>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
