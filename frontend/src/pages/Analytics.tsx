import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Section, StatCard } from "../components/ui";
import { pnlColor } from "../lib/format";
import type { AnalyticsPayload, TradeStats } from "../lib/types";

function StatsTable({ rows, label }: { rows: TradeStats[]; label: string }) {
  if (!rows.length) return <p className="text-slate-500 text-sm">Sin datos.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-slate-400 text-xs">
          <tr className="text-left border-b border-border">
            <th className="py-2">{label}</th><th>Trades</th><th>Win %</th><th>P&L total</th><th>Media</th><th>Profit factor</th><th>Expectancy</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.group} className="border-b border-border/50">
              <td className="py-2 font-medium">{r.group}</td>
              <td>{r.trades}</td>
              <td>{r.win_rate.toFixed(0)}%</td>
              <td className={pnlColor(r.total_pnl)}>{r.total_pnl.toFixed(2)}</td>
              <td className={pnlColor(r.avg_pnl)}>{r.avg_pnl.toFixed(2)}</td>
              <td>{r.profit_factor ?? "∞"}</td>
              <td className={pnlColor(r.expectancy)}>{r.expectancy.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Analytics() {
  const { data, isLoading } = useQuery({
    queryKey: ["analytics"],
    queryFn: async () => (await api.get("/analytics")).data as AnalyticsPayload,
    refetchInterval: 30000,
  });

  if (isLoading) return <div className="text-slate-400">Cargando analítica…</div>;
  if (!data || data.overall.trades === 0)
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Analítica de operaciones</h1>
        <p className="text-slate-400">Aún no hay operaciones cerradas. Cuando el bot cierre trades, aquí verás de dónde viene el rendimiento.</p>
      </div>
    );

  const o = data.overall;
  return (
    <div className="space-y-4 max-w-5xl">
      <h1 className="text-2xl font-bold">Analítica de operaciones</h1>
      <p className="text-sm text-slate-400">Atribución del rendimiento: qué estrategias, símbolos y condiciones funcionan (y cuáles no).</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Operaciones" value={o.trades} />
        <StatCard label="Win rate" value={`${o.win_rate.toFixed(1)}%`} />
        <StatCard label="Profit factor" value={o.profit_factor ?? "∞"} />
        <StatCard label="Expectancy / trade" value={o.expectancy.toFixed(2)} valueClass={pnlColor(o.expectancy)} />
      </div>

      <div className="grid lg:grid-cols-2 gap-3">
        <StatCard label="Racha ganadora máx." value={data.streaks.max_wins} valueClass="text-profit" />
        <StatCard label="Racha perdedora máx." value={data.streaks.max_losses} valueClass="text-loss" />
      </div>

      {(data.best_trade || data.worst_trade) && (
        <div className="grid lg:grid-cols-2 gap-3">
          {data.best_trade && (
            <Section title="🏆 Mejor operación">
              <p className="text-sm"><span className="font-medium">{data.best_trade.symbol}</span> · {data.best_trade.strategy}</p>
              <p className={`text-lg font-bold ${pnlColor(data.best_trade.pnl)}`}>{data.best_trade.pnl.toFixed(2)} ({data.best_trade.pnl_pct.toFixed(2)}%)</p>
              <p className="text-xs text-slate-500">{data.best_trade.reason}</p>
            </Section>
          )}
          {data.worst_trade && (
            <Section title="💀 Peor operación">
              <p className="text-sm"><span className="font-medium">{data.worst_trade.symbol}</span> · {data.worst_trade.strategy}</p>
              <p className={`text-lg font-bold ${pnlColor(data.worst_trade.pnl)}`}>{data.worst_trade.pnl.toFixed(2)} ({data.worst_trade.pnl_pct.toFixed(2)}%)</p>
              <p className="text-xs text-slate-500">{data.worst_trade.reason}</p>
            </Section>
          )}
        </div>
      )}

      <Section title="Por estrategia"><StatsTable rows={data.by_strategy} label="Estrategia" /></Section>
      <Section title="Por símbolo"><StatsTable rows={data.by_symbol} label="Símbolo" /></Section>
      <Section title="Por motivo de salida"><StatsTable rows={data.by_exit_reason} label="Motivo" /></Section>
      <Section title="Por hora de apertura (UTC)"><StatsTable rows={data.by_hour} label="Hora" /></Section>
    </div>
  );
}
