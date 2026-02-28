"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  CartesianGrid,
} from "recharts";

const TOOLTIP_STYLE = {
  contentStyle: {
    background: "#1a1d2e",
    border: "1px solid #2a2e3f",
    borderRadius: 4,
    fontSize: 11,
  },
  labelStyle: { color: "#6b7194", fontSize: 11 },
};

interface SentimentChartProps {
  data: { date: string; avg_sentiment: number; mentions: number }[];
}

export function SentimentChart({ data }: SentimentChartProps) {
  return (
    <div className="space-y-1">
      <div className="h-36">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2962ff" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#2962ff" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2e3f" />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7194" }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "#6b7194" }} tickLine={false} axisLine={false} domain={[-1, 1]} />
            <Tooltip {...TOOLTIP_STYLE} />
            <Area type="monotone" dataKey="avg_sentiment" stroke="#2962ff" strokeWidth={1.5} fill="url(#sentGrad)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="h-20">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <XAxis dataKey="date" tick={false} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "#6b7194" }} tickLine={false} axisLine={false} />
            <Tooltip {...TOOLTIP_STYLE} />
            <Bar dataKey="mentions" fill="#2a2e3f" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
