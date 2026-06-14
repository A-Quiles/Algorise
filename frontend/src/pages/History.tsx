import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Section } from "../components/ui";
import { dateTime, money, num, pct, pnlColor } from "../lib/format";
import type { Position, Signal } from "../lib/types";

export default function History() {
  const [tab, setTab] = useState<"trades" | "signals">("trades");
  const { data: trades } = useQuery({ queryKey: ["trades"], queryFn: async () => (await api.get("/trades", { params: { limit: 200 } })).data as Position[] });
  const { data: signals } = useQuery({ queryKey: ["signals"], queryFn: async () => (await api.get("/signals", { params: { limit: 200 } })).data as Signal[] });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Historial</h1>
      <div className="flex gap-2">
        <button className={tab === "trades" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("trades")}>Operaciones cerradas</button>
        <button className={tab === "signals" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("signals")}>Diario de decisiones (IA)</button>
      </div>

      {tab === "trades" && (
        <Section title={`Operaciones cerradas (${trades?.length ?? 0})`}>
          {!trades?.length ? <p className="text-slate-500 text-sm">Aún no hay operaciones cerradas.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-400 text-xs">
                  <tr className="text-left border-b border-border">
                    <th className="py-2">Par</th><th>Entrada</th><th>Salida</th><th>P&L</th><th>Motivo cierre</th><th>Cerrada</th><th>Razón IA</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((t) => (
                    <tr key={t.id} className="border-b border-border/50 align-top">
                      <td className="py-2 font-medium">{t.symbol}</td>
                      <td>{num(t.entry_price)}</td>
                      <td>{num(t.exit_price)}</td>
                      <td className={pnlColor(t.pnl)}>{money(t.pnl)} <span className="text-xs">({pct(t.pnl_pct)})</span></td>
                      <td className="text-xs text-slate-400">{t.close_reason}</td>
                      <td className="text-xs text-slate-500">{dateTime(t.closed_at)}</td>
                      <td className="text-xs text-slate-400 max-w-xs">{t.llm_explanation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      )}

      {tab === "signals" && (
        <Section title={`Decisiones (${signals?.length ?? 0})`}>
          {!signals?.length ? <p className="text-slate-500 text-sm">Sin decisiones registradas.</p> : (
            <ul className="space-y-2">
              {signals.map((s) => (
                <li key={s.id} className="border-b border-border/50 pb-2 flex gap-3 items-start">
                  <Badge color={s.action === "buy" ? "green" : s.action === "sell" ? "red" : "slate"}>{s.action}</Badge>
                  <div className="flex-1">
                    <div className="flex flex-wrap gap-2 items-center text-sm">
                      <span className="font-medium">{s.symbol}</span>
                      <span className="text-xs text-slate-500">{dateTime(s.timestamp)}</span>
                      {s.executed && <Badge color="sky">ejecutada</Badge>}
                      {s.llm_used && <Badge color="slate">IA: {s.llm_decision} ({Math.round((s.llm_confidence ?? 0) * 100)}%)</Badge>}
                      {s.llm_decision === "veto" && <Badge color="red">vetada</Badge>}
                    </div>
                    {s.llm_explanation && <p className="text-xs text-slate-400 mt-1">{s.llm_explanation}</p>}
                    {Object.keys(s.indicators || {}).length > 0 && (
                      <p className="text-xs text-slate-600 mt-1 font-mono">{JSON.stringify(s.indicators)}</p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}
    </div>
  );
}
