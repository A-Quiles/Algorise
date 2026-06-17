import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Section, StatCard, Spinner } from "../components/ui";
import EquityChart from "../components/EquityChart";
import { money, num, pct, pnlColor } from "../lib/format";
import { COMMON_COINS, QUOTE_CURRENCIES, makePair } from "../lib/markets";
import type { BacktestResult, StrategyInfo } from "../lib/types";

const TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"];

export default function Backtest() {
  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: async () => (await api.get("/strategies")).data as StrategyInfo[] });

  const [coin, setCoin] = useState("BTC");
  const [quote, setQuote] = useState("USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [strategyId, setStrategyId] = useState("ma_cross");
  const [days, setDays] = useState(90);
  const [capital, setCapital] = useState(10000);
  const [params, setParams] = useState<Record<string, number>>({});
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const symbol = makePair(coin, quote);
  const activeStrategy = useMemo(() => strategies?.find((s) => s.id === strategyId), [strategies, strategyId]);

  // Al cambiar de estrategia se limpian los parámetros (se usarán los por defecto).
  const changeStrategy = (id: string) => { setStrategyId(id); setParams({}); };

  const run = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.post("/backtest", {
        symbol, timeframe, strategy_id: strategyId, strategy_params: params,
        days, starting_capital: capital,
      });
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
        <div className="grid sm:grid-cols-2 lg:grid-cols-6 gap-3 items-end">
          <div>
            <label className="label">Cripto</label>
            <select className="input" value={coin} onChange={(e) => setCoin(e.target.value)}>
              {Array.from(new Set([coin, ...COMMON_COINS])).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Moneda</label>
            <select className="input" value={quote} onChange={(e) => setQuote(e.target.value)}>
              {Array.from(new Set([quote, ...QUOTE_CURRENCIES])).map((q) => <option key={q} value={q}>{q}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Marco temporal</label>
            <select className="input" value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Estrategia</label>
            <select className="input" value={strategyId} onChange={(e) => changeStrategy(e.target.value)}>
              {strategies?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Días de histórico</label>
            <input type="number" className="input" value={days} min={1} max={1000} onChange={(e) => setDays(parseInt(e.target.value))} />
          </div>
          <div>
            <label className="label">Capital inicial</label>
            <input type="number" className="input" value={capital} onChange={(e) => setCapital(parseFloat(e.target.value))} />
          </div>
        </div>

        {activeStrategy && activeStrategy.params.length > 0 && (
          <div className="mt-4">
            <p className="text-xs text-slate-500 mb-2">Parámetros de «{activeStrategy.name}» (vacío = valores por defecto):</p>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {activeStrategy.params.map((p) => (
                <div key={p.key}>
                  <label className="label">{p.label}</label>
                  <input type="number" className="input" min={p.min} max={p.max} step={p.step}
                    value={params[p.key] ?? p.default}
                    onChange={(e) => setParams({ ...params, [p.key]: parseFloat(e.target.value) })} />
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-3 mt-4">
          <button className="btn-primary" onClick={run} disabled={loading}>{loading ? "Ejecutando…" : "Ejecutar backtest"}</button>
          <span className="text-xs text-slate-500">Par: <span className="text-slate-300">{symbol}</span></span>
        </div>
      </Section>

      {loading && <div className="card grid place-items-center py-10"><Spinner /></div>}
      {error && <div className="card border-loss/50 text-loss text-sm">{error}</div>}

      {m && !m.error && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="Retorno total" value={pct(m.total_return_pct as number)} valueClass={pnlColor(m.total_return_pct as number)} />
            <StatCard label="Comprar y mantener" value={pct(m.buy_hold_return_pct as number)} valueClass={pnlColor(m.buy_hold_return_pct as number)} sub="benchmark: solo holdear" />
            <StatCard label="Estrategia vs hold" value={pct(m.vs_buy_hold_pct as number)} valueClass={pnlColor(m.vs_buy_hold_pct as number)} sub="diferencia frente a holdear" />
            <StatCard label="CAGR (anualizado)" value={pct(m.cagr_pct as number)} valueClass={pnlColor(m.cagr_pct as number)} />
            <StatCard label="Equity final" value={money(m.final_equity as number, quote)} />
            <StatCard label="Operaciones" value={m.num_trades as number} sub={`${m.win_rate_pct}% ganadoras`} />
            <StatCard label="Máx. drawdown" value={pct(m.max_drawdown_pct as number)} valueClass="text-loss" />
            <StatCard label="Exposición al mercado" value={pct(m.exposure_pct as number)} sub="% del tiempo con posición" />
            <StatCard label="Ratio de Sharpe" value={num(m.sharpe_ratio as number, 2)} />
            <StatCard label="Profit factor" value={m.profit_factor === null ? "∞" : num(m.profit_factor as number, 2)} />
            <StatCard label="P&L medio/op." value={money(m.avg_trade_pnl as number, quote)} valueClass={pnlColor(m.avg_trade_pnl as number)} />
            <StatCard label="Máx. pérdidas seguidas" value={m.max_consecutive_losses as number} valueClass={(m.max_consecutive_losses as number) > 0 ? "text-loss" : undefined} />
            <StatCard label="Ganancia media" value={money(m.avg_win as number, quote)} valueClass="text-profit" />
            <StatCard label="Pérdida media" value={money(m.avg_loss as number, quote)} valueClass="text-loss" />
            <StatCard label="Mejor operación" value={pct(m.best_trade_pct as number)} valueClass="text-profit" />
            <StatCard label="Peor operación" value={pct(m.worst_trade_pct as number)} valueClass="text-loss" />
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
