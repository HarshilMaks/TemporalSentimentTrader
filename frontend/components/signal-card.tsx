import { SignalBadge, ConfidencePill } from "./badges";
import { formatCurrency, formatPct } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { Signal } from "@/lib/api";

export function SignalRow({ signal }: { signal: Signal }) {
  const hasPnl = signal.pnl_pct !== undefined;
  return (
    <div className="flex items-center gap-3 px-3 py-2 border-b border-border/50 hover:bg-surface-1 transition-colors text-xs">
      <span className="font-semibold text-foreground w-12">{signal.ticker}</span>
      <SignalBadge signal={signal.signal} />
      <ConfidencePill value={signal.confidence} />
      <span className="font-mono text-muted-foreground ml-auto">{formatCurrency(signal.entry_price)}</span>
      <span className="font-mono text-bull w-16 text-right">
        {signal.target_price ? formatCurrency(signal.target_price) : "—"}
      </span>
      <span className="font-mono text-bear w-16 text-right">
        {signal.stop_loss ? formatCurrency(signal.stop_loss) : "—"}
      </span>
      {hasPnl && (
        <span className={cn("font-mono font-semibold w-14 text-right", signal.pnl_pct! >= 0 ? "text-bull" : "text-bear")}>
          {formatPct(signal.pnl_pct!)}
        </span>
      )}
    </div>
  );
}

export function SignalCard({ signal }: { signal: Signal }) {
  return (
    <div className="bg-surface-0 border border-border rounded p-3 hover:border-border-hover transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm">{signal.ticker}</span>
          <SignalBadge signal={signal.signal} />
        </div>
        <ConfidencePill value={signal.confidence} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-[11px]">
        <div>
          <span className="text-muted-foreground">Entry</span>
          <p className="font-mono">{formatCurrency(signal.entry_price)}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Target</span>
          <p className="font-mono text-bull">{signal.target_price ? formatCurrency(signal.target_price) : "—"}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Stop</span>
          <p className="font-mono text-bear">{signal.stop_loss ? formatCurrency(signal.stop_loss) : "—"}</p>
        </div>
      </div>
      {signal.pnl_pct !== undefined && (
        <div className="mt-2 pt-2 border-t border-border flex justify-between text-[11px]">
          <span className="text-muted-foreground">{signal.exit_reason}</span>
          <span className={cn("font-mono font-semibold", signal.pnl_pct >= 0 ? "text-bull" : "text-bear")}>
            {formatPct(signal.pnl_pct)}
          </span>
        </div>
      )}
    </div>
  );
}
