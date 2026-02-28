"use client";

import { useEffect, useState } from "react";
import {
  getActiveSignals,
  getSignalHistory,
  getDailyReport,
  type Signal,
} from "@/lib/api";
import { Panel, PanelHeader, PanelBody } from "@/components/card";
import { SignalBadge, ConfidencePill } from "@/components/badges";
import { SignalCard } from "@/components/signal-card";
import { formatCurrency, formatPct } from "@/lib/utils";
import { cn } from "@/lib/utils";

type Tab = "active" | "daily" | "history";

export default function SignalsPage() {
  const [active, setActive] = useState<Signal[]>([]);
  const [history, setHistory] = useState<Signal[]>([]);
  const [daily, setDaily] = useState<Signal[]>([]);
  const [dailyDate, setDailyDate] = useState("");
  const [tab, setTab] = useState<Tab>("active");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getActiveSignals(),
      getSignalHistory(100),
      getDailyReport(),
    ]).then(([aRes, hRes, dRes]) => {
      if (aRes.status === "fulfilled") setActive(aRes.value.signals);
      if (hRes.status === "fulfilled") setHistory(hRes.value.signals);
      if (dRes.status === "fulfilled") {
        setDaily(dRes.value.signals);
        setDailyDate(dRes.value.date);
      }
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-full text-muted-foreground text-xs">Loading…</div>;
  }

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "active", label: "Active", count: active.length },
    { key: "daily", label: "Daily Report", count: daily.length },
    { key: "history", label: "History", count: history.length },
  ];

  const currentSignals = tab === "active" ? active : tab === "daily" ? daily : history;

  return (
    <div className="h-full overflow-y-auto">
      {/* Tab bar */}
      <div className="border-b border-border bg-surface-0 px-4 flex items-center gap-0.5">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "px-3 py-2.5 text-xs font-medium border-b-2 transition-colors",
              tab === t.key
                ? "border-accent text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {t.label}
            <span className="ml-1.5 text-[10px] font-mono text-muted-foreground">{t.count}</span>
          </button>
        ))}
        {tab === "daily" && dailyDate && (
          <span className="ml-auto text-[10px] text-muted-foreground font-mono">{dailyDate}</span>
        )}
      </div>

      <div className="p-4">
        {/* History — table view */}
        {tab === "history" && history.length > 0 ? (
          <Panel>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                    <th className="px-3 py-2">Ticker</th>
                    <th className="px-3 py-2">Signal</th>
                    <th className="px-3 py-2">Confidence</th>
                    <th className="px-3 py-2 text-right">Entry</th>
                    <th className="px-3 py-2 text-right">Target</th>
                    <th className="px-3 py-2 text-right">Stop</th>
                    <th className="px-3 py-2 text-right">Exit</th>
                    <th className="px-3 py-2">Reason</th>
                    <th className="px-3 py-2 text-right">P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((s) => (
                    <tr key={s.id} className="border-b border-border/50 hover:bg-surface-1 transition-colors">
                      <td className="px-3 py-1.5 font-semibold text-foreground">{s.ticker}</td>
                      <td className="px-3 py-1.5"><SignalBadge signal={s.signal} /></td>
                      <td className="px-3 py-1.5"><ConfidencePill value={s.confidence} /></td>
                      <td className="px-3 py-1.5 text-right font-mono">{formatCurrency(s.entry_price)}</td>
                      <td className="px-3 py-1.5 text-right font-mono text-bull">
                        {s.target_price ? formatCurrency(s.target_price) : "—"}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono text-bear">
                        {s.stop_loss ? formatCurrency(s.stop_loss) : "—"}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono">
                        {s.exit_price ? formatCurrency(s.exit_price) : "—"}
                      </td>
                      <td className="px-3 py-1.5 text-muted-foreground">{s.exit_reason ?? "—"}</td>
                      <td className={cn(
                        "px-3 py-1.5 text-right font-mono font-semibold",
                        s.pnl_pct !== undefined ? (s.pnl_pct >= 0 ? "text-bull" : "text-bear") : ""
                      )}>
                        {s.pnl_pct !== undefined ? formatPct(s.pnl_pct) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        ) : (
          /* Card grid for active / daily */
          currentSignals.length === 0 ? (
            <Panel>
              <PanelBody>
                <div className="text-center text-muted-foreground text-xs py-8">
                  No signals to display
                </div>
              </PanelBody>
            </Panel>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
              {currentSignals.map((s) => (
                <SignalCard key={s.id} signal={s} />
              ))}
            </div>
          )
        )}
      </div>
    </div>
  );
}
