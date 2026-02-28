import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TFT Trader",
  description: "Triangulation swing trading terminal",
};

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/signals", label: "Signals" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen flex flex-col`}>
        {/* Top bar — thin, dense, TradingView-style */}
        <header className="h-10 border-b border-border bg-surface-0 flex items-center px-3 gap-6 shrink-0">
          <Link href="/" className="font-bold text-sm tracking-wide flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-accent inline-block" />
            <span className="text-foreground">TFT</span>
            <span className="text-muted-foreground font-normal">Trader</span>
          </Link>
          <div className="flex gap-0.5">
            {NAV.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="px-2.5 py-1 rounded text-xs text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
              >
                {label}
              </Link>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-bull inline-block" />
              API
            </span>
          </div>
        </header>
        <div className="flex-1 overflow-hidden">{children}</div>
      </body>
    </html>
  );
}
