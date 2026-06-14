import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Section, StatCard, Spinner } from "../components/ui";
import EquityChart from "../components/EquityChart";
import { money, num, pct, pnlColor } from "../lib/format";
import type { BacktestResult, StrategyInfo } from "../lib/types";

const TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"];

export default function Backtest() {
  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: async () => (await api.get("/strategies")).data as StrategyInfo[] });
  const [form, setForm] = useState({ symbol: "BTC/USDT", timeframe: "1h", strategy_id: "ma_cross", days: 90, starting_capital: 10000 });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.post("/backtest", form);
      setResult(res.data as BacktestResult);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Error ejecutando el backtest.");
    } finally {
      setLoading(false);
    }
  };

  const m = result?.metrics;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Backtesting</h1>
      <p className="text-slate-400 text-sm">Simula la estrategia sobre histórico de Binance para validar una configuración antes de operar. Usa la gestión de riesgo guardada (solo señal cuantitativa, sin IA, por velocidad).</p>

      <Section title="Parámetros">
        <div className="grid sm:grid-cols-5 gap-3 items-end">
          <div>
            <label className="label">Par</label>
            <input className="input" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} />
          </div>
          <div>
            <label className="label">Marco temporal</label>
            <select className="input" value={form.timeframe} onChange={(e) => setForm({ ...form, timeframe: e.target.value })}>
              {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Estrategia</label>
            <select className="input" value={form.strategy_id} onChange={(e) => setForm({ ...form, strategy_id: e.target.value })}>
              {strategies?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Días de histórico</label>
            <input type="number" className="input" value={form.days} min={1} max={1000} onChange={(e) => setForm({ ...form, days: parseInt(e.target.value) })} />
          </div>
          <div>
            <label className="label">Capital inicial</label>
            <input type="number" className="input" value={form.starting_capital} onChange={(e) => setForm({ ...form, starting_capital: parseFloat(e.target.value) })} />
          </div>
        </div>
        <button className="btn-primary mt-4" onClick={run} disabled={loading}>{loading ? "Ejecutando…" : "Ejecutar backtest"}</button>
      </Section>

      {loading && <div className="card grid place-items-center py-10"><Spinner /></div>}
      {error && <div className="card border-loss/50 text-loss text-sm">{error}</div>}

      {m && !m.error && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="Retorno total" value={pct(m.total_return_pct as number)} valueClass={pnlColor(m.total_return_pct as number)} />
            <StatCard label="Equity final" value={money(m.final_equity as number)} />
            <StatCard label="Operaciones" value={m.num_trades as number} sub={`${m.win_rate_pct}% ganadoras`} />
            <StatCard label="Máx. drawdown" value={pct(m.max_drawdown_pct as number)} valueClass="text-loss" />
            <StatCard label="Ratio de Sharpe" value={num(m.sharpe_ratio as number, 2)} />
            <StatCard label="Profit factor" value={m.profit_factor === null ? "∞" : num(m.profit_factor as number, 2)} />
            <StatCard label="P&L medio/op." value={money(m.avg_trade_pnl as number)} valueClass={pnlColor(m.avg_trade_pnl as number)} />
          </div>

          <Section title="Curva de equity (backtest)">
            <EquityChart data={result!.equity_curve.filter((_, i) => i % Math.ceil(result!.equity_curve.length / 500) === 0)} />
          </Section>

          <Section title={`Operaciones (${result!.trades.length})`}>
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-sm">
                <thead className="text-slate-400 text-xs sticky top-0 bg-card">
                  <tr className="text-left border-b border-border"><th className="py-2">Entrada</th><th>Salida</th><th>Precio entrada</th><th>Precio salida</th><th>P&L</th><th>Motivo</th></tr>
                </thead>
                <tbody>
                  {result!.trades.map((t, i) => (
                    <tr key={i} className="border-b border-border/50">
                      <td className="py-1 text-xs">{new Date(t.entry_time).toLocaleString("es-ES")}</td>
                      <td className="text-xs">{new Date(t.exit_time).toLocaleString("es-ES")}</td>
                      <td>{num(t.entry_price)}</td>
                      <td>{num(t.exit_price)}</td>
                      <td className={pnlColor(t.pnl)}>{money(t.pnl)} ({pct(t.pnl_pct)})</td>
                      <td className="text-xs text-slate-400">{t.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}
      {m?.error && <div className="card text-amber-400 text-sm">{m.error as string}</div>}
    </div>
  );
}
