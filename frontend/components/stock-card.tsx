import Link from "next/link";
import { SentimentBadge } from "./badges";
import type { TrendingTicker } from "@/lib/api";
import { cn } from "@/lib/utils";

export function WatchlistRow({ ticker, active }: { ticker: TrendingTicker; active?: boolean }) {
  return (
    <Link
      href={`/ticker/${ticker.ticker}`}
      className={cn(
        "flex items-center justify-between px-3 py-1.5 hover:bg-surface-2 transition-colors text-xs",
        active && "bg-surface-2"
      )}
    >
      <div className="flex items-center gap-2">
        <span className="font-semibold text-foreground w-12">{ticker.ticker}</span>
        <span className="text-muted-foreground">{ticker.mentions}m</span>
      </div>
      <SentimentBadge score={ticker.avg_sentiment} />
    </Link>
  );
}
