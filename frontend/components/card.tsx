import { cn } from "@/lib/utils";

export function Panel({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("bg-surface-0 border border-border rounded", className)} {...props}>
      {children}
    </div>
  );
}

export function PanelHeader({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("px-3 py-2 border-b border-border flex items-center justify-between text-xs font-medium text-muted-foreground uppercase tracking-wider", className)}>
      {children}
    </div>
  );
}

export function PanelBody({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-3", className)}>{children}</div>;
}

export function Stat({
  label,
  value,
  sub,
  variant = "default",
}: {
  label: string;
  value: string | number;
  sub?: string;
  variant?: "default" | "bull" | "bear";
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">{label}</div>
      <div
        className={cn(
          "text-sm font-mono font-semibold",
          variant === "bull" && "text-bull",
          variant === "bear" && "text-bear"
        )}
      >
        {value}
      </div>
      {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}
