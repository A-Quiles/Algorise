import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useDashboardSocket } from "../lib/ws";
import { Badge, Card, Section, StatCard } from "../components/ui";
import EquityChart from "../components/EquityChart";
import CandleChart from "../components/CandleChart";
import { dateTime, money, num, pct, pnlColor } from "../lib/format";
import type { BotConfig, DashboardPayload } from "../lib/types";

const STATUS_LABEL: Record<string, { text: string; color: "green" | "amber" | "slate" }> = {
  running: { text: "En marcha", color: "green" },
  paused: { text: "Pausado", color: "amber" },
  stopped: { text: "Detenido", color: "slate" },
};

// Intervalo de cada vela del gráfico (independiente del timeframe con el que opera el bot).
const CHART_TIMEFRAMES: { value: string; label: string }[] = [
  { value: "1m", label: "1 min" },
  { value: "5m", label: "5 min" },
  { value: "15m", label: "15 min" },
  { value: "30m", label: "30 min" },
  { value: "1h", label: "1 hora" },
  { value: "4h", label: "4 horas" },
  { value: "1d", label: "1 día" },
  { value: "1w", label: "1 semana" },
  { value: "1M", label: "1 mes" },
];

export default function Dashboard() {
  const { data: live, connected } = useDashboardSocket();
  const { data: initial, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard")).data as DashboardPayload,
    refetchInterval: connected ? false : 15000,
  });
  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: async () => (await api.get("/config")).data as BotConfig,
  });

  const d = live || initial;
  const [busy, setBusy] = useState<string | null>(null);
  const [pair, setPair] = useState<string>("BTC/USDT");
  const [chartTf, setChartTf] = useState<string>("1h");

  useEffect(() => {
    if (config?.pairs?.length && !config.pairs.includes(pair)) setPair(config.pairs[0]);
  }, [config]);

  const act = async (action: string) => {
    setBusy(action);
    try {
      await api.post(`/bot/${action}`);
      await refetch();
    } finally {
      setBusy(null);
    }
  };

  if (!d) return <div className="text-slate-400">Cargando panel…</div>;

  const status = STATUS_LABEL[d.bot.status] ?? STATUS_LABEL.stopped;
  const cur = d.account.base_currency;

  return (
    <div className="space-y-4">
      {/* Cabecera */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Panel</h1>
          <Badge color="amber">MODO PAPEL</Badge>
          <Badge color={status.color}>{status.text}</Badge>
          <span className={`text-xs ${connected ? "text-profit" : "text-slate-500"}`}>{connected ? "● en vivo" : "○ sin WS"}</span>
        </div>
        <div className="flex gap-2">
          {d.bot.status !== "running" && <button className="btn-primary" disabled={!!busy} onClick={() => act("start")}>{busy === "start" ? "…" : "▶ Arrancar"}</button>}
          {d.bot.status === "running" && <button className="btn-ghost" disabled={!!busy} onClick={() => act("pause")}>⏸ Pausar</button>}
          {d.bot.status !== "stopped" && <button className="btn-ghost" disabled={!!busy} onClick={() => act("stop")}>⏹ Parar</button>}
          <button className="btn-danger" disabled={!!busy} onClick={() => act("kill")} title="Cierra todas las posiciones y detiene el bot">⚠ Kill</button>
        </div>
      </div>

      {d.bot.last_error && <Card className="border-loss/50 text-loss text-sm">Último error: {d.bot.last_error}</Card>}

      {/* Métricas */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <StatCard label="Valor de la cartera" value={money(d.portfolio.equity, cur)} sub={`Inicial: ${money(d.account.initial_capital, cur)}`} />
        <StatCard label="P&L total" value={money(d.portfolio.total_pnl, cur)} sub={pct(d.portfolio.total_pnl_pct)} valueClass={pnlColor(d.portfolio.total_pnl)} />
        <StatCard label="Efectivo libre" value={money(d.portfolio.cash, cur)} />
        <StatCard label="P&L no realizado" value={money(d.portfolio.unrealized_pnl, cur)} valueClass={pnlColor(d.portfolio.unrealized_pnl)} />
        <StatCard label="Drawdown" value={pct(d.portfolio.drawdown_pct)} valueClass={d.portfolio.drawdown_pct > 0 ? "text-loss" : ""} />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Curva de equity">
          <EquityChart data={d.equity_curve} />
        </Section>
        <Section
          title="Gráfico de precio"
          action={
            <div className="flex flex-wrap gap-2">
              <select className="input w-auto" value={pair} onChange={(e) => setPair(e.target.value)} title="Par">
                {(config?.pairs ?? Object.keys(d.prices)).map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <select className="input w-auto" value={chartTf} onChange={(e) => setChartTf(e.target.value)} title="Intervalo de vela">
                {CHART_TIMEFRAMES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          }
        >
          <CandleChart symbol={pair} timeframe={chartTf} />
        </Section>
      </div>

      {/* Posiciones abiertas */}
      <Section title={`Posiciones abiertas (${d.open_positions.length})`}>
        {d.open_positions.length === 0 ? (
          <p className="text-slate-500 text-sm">No hay posiciones abiertas.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-400 text-xs">
                <tr className="text-left border-b border-border">
                  <th className="py-2">Par</th><th>Cantidad</th><th>Entrada</th><th>Actual</th><th>SL / TP</th><th>P&L</th><th>Estrategia</th>
                </tr>
              </thead>
              <tbody>
                {d.open_positions.map((p) => (
                  <tr key={p.id} className="border-b border-border/50">
                    <td className="py-2 font-medium">{p.symbol}</td>
                    <td>{num(p.quantity, 6)}</td>
                    <td>{num(p.entry_price)}</td>
                    <td>{num(p.current_price)}</td>
                    <td className="text-xs">{num(p.stop_loss, 2)} / {num(p.take_profit, 2)}</td>
                    <td className={pnlColor(p.unrealized_pnl)}>{money(p.unrealized_pnl, cur)} ({pct(p.unrealized_pnl_pct)})</td>
                    <td className="text-xs text-slate-400">{p.strategy}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Últimas decisiones">
          {d.recent_signals.length === 0 ? <p className="text-slate-500 text-sm">Sin decisiones aún.</p> : (
            <ul className="space-y-2 max-h-72 overflow-y-auto text-sm">
              {d.recent_signals.slice(0, 12).map((s) => (
                <li key={s.id} className="flex gap-2 items-start">
                  <Badge color={s.action === "buy" ? "green" : s.action === "sell" ? "red" : "slate"}>{s.action}</Badge>
                  <div className="flex-1">
                    <span className="font-medium">{s.symbol}</span>
                    {s.executed && <Badge color="sky">ejecutada</Badge>}
                    {s.llm_decision === "veto" && <Badge color="red">IA vetó</Badge>}
                    <p className="text-xs text-slate-400">{s.llm_explanation}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Registro de eventos">
          {d.logs.length === 0 ? <p className="text-slate-500 text-sm">Sin eventos.</p> : (
            <ul className="space-y-1 max-h-72 overflow-y-auto text-xs font-mono">
              {d.logs.map((l) => (
                <li key={l.id} className={l.level === "error" ? "text-loss" : l.level === "warning" ? "text-amber-400" : "text-slate-400"}>
                  <span className="text-slate-600">{new Date(l.timestamp).toLocaleTimeString("es-ES")}</span> {l.message}
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      <p className="text-xs text-slate-600 text-center">Último ciclo: {dateTime(d.bot.last_cycle_at)} · Algorise opera con dinero ficticio.</p>
    </div>
  );
}
