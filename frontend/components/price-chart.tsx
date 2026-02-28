"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, CandlestickSeries, type IChartApi } from "lightweight-charts";

interface PriceChartProps {
  data: { time: string; open: number; high: number; low: number; close: number }[];
  height?: number;
}

export function PriceChart({ data, height = 300 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#131520" },
        textColor: "#6b7194",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1a1d2e" },
        horzLines: { color: "#1a1d2e" },
      },
      crosshair: {
        vertLine: { color: "#2962ff", width: 1, style: 2, labelBackgroundColor: "#2962ff" },
        horzLine: { color: "#2962ff", width: 1, style: 2, labelBackgroundColor: "#2962ff" },
      },
      rightPriceScale: { borderColor: "#2a2e3f" },
      timeScale: { borderColor: "#2a2e3f", timeVisible: false },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderDownColor: "#ef5350",
      borderUpColor: "#26a69a",
      wickDownColor: "#ef5350",
      wickUpColor: "#26a69a",
    });

    series.setData(data);
    chart.timeScale().fitContent();
    chartRef.current = chart;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [data, height]);

  return <div ref={containerRef} className="w-full rounded overflow-hidden" />;
}
