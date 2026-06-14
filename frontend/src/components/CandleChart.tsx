import { useEffect, useRef } from "react";
import { createChart, ColorType, type IChartApi, type CandlestickData } from "lightweight-charts";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export default function CandleChart({ symbol, timeframe, limit = 300 }: { symbol: string; timeframe: string; limit?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["ohlcv", symbol, timeframe, limit],
    queryFn: async () => {
      const res = await api.get("/market/ohlcv", { params: { symbol, timeframe, limit } });
      return res.data as CandlestickData[];
    },
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#1e2a45" }, horzLines: { color: "#1e2a45" } },
      timeScale: { timeVisible: true, borderColor: "#1e2a45" },
      rightPriceScale: { borderColor: "#1e2a45" },
      autoSize: true,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#22c55e", downColor: "#ef4444", borderVisible: false,
      wickUpColor: "#22c55e", wickDownColor: "#ef4444",
    });
    chartRef.current = chart;
    (chart as any)._series = series;
    return () => chart.remove();
  }, []);

  useEffect(() => {
    const chart = chartRef.current as any;
    if (chart && data) chart._series.setData(data);
  }, [data]);

  return (
    <div className="relative">
      <div ref={containerRef} className="h-[360px] w-full" />
      {isLoading && <div className="absolute inset-0 grid place-items-center text-slate-500 text-sm">Cargando velas…</div>}
      {error && <div className="absolute inset-0 grid place-items-center text-loss text-sm">No se pudo cargar el gráfico (¿sin conexión a Binance?)</div>}
    </div>
  );
}
