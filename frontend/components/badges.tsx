import { cn } from "@/lib/utils";

type Variant = "bull" | "bear" | "warn" | "neutral" | "accent";

const styles: Record<Variant, string> = {
  bull: "bg-bull-dim text-bull",
  bear: "bg-bear-dim text-bear",
  warn: "bg-warn-dim text-warn",
  neutral: "bg-surface-2 text-muted-foreground",
  accent: "bg-accent-dim text-accent",
};

export function Badge({
  variant = "neutral",
  className,
  children,
}: {
  variant?: Variant;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold", styles[variant], className)}>
      {children}
    </span>
  );
}

export function RegimeBadge({ regime }: { regime: "BULL" | "BEAR" | string }) {
  return (
    <Badge variant={regime === "BULL" ? "bull" : "bear"} className="gap-1">
      <span className={cn("w-1.5 h-1.5 rounded-full", regime === "BULL" ? "bg-bull" : "bg-bear")} />
      {regime}
    </Badge>
  );
}

export function SignalBadge({ signal }: { signal: string }) {
  const v: Variant = signal === "BUY" ? "bull" : signal === "SELL" ? "bear" : "neutral";
  return <Badge variant={v}>{signal}</Badge>;
}

export function SentimentBadge({ score }: { score: number }) {
  const v: Variant = score > 0.3 ? "bull" : score < -0.3 ? "bear" : "warn";
  return <Badge variant={v}>{score >= 0 ? "+" : ""}{score.toFixed(3)}</Badge>;
}

export function ConfidencePill({ value }: { value: number }) {
  const pct = value * 100;
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-12 h-1 rounded-full bg-surface-2 overflow-hidden">
        <div
          className={cn("h-full rounded-full", pct >= 70 ? "bg-bull" : pct >= 50 ? "bg-warn" : "bg-bear")}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] font-mono text-muted-foreground">{pct.toFixed(0)}%</span>
    </div>
  );
}
