import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Section, Spinner } from "../components/ui";
import { num } from "../lib/format";
import type { BotConfig } from "../lib/types";

export default function Insights() {
  const { data: config } = useQuery({ queryKey: ["config"], queryFn: async () => (await api.get("/config")).data as BotConfig });
  const [pair, setPair] = useState("BTC/USDT");
  const [result, setResult] = useState<{ commentary: string; indicators: Record<string, number>; provider: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const ask = async () => {
    setLoading(true);
    setResult(null);
    const [base, quote] = pair.split("/");
    try {
      const res = await api.get(`/ai/commentary/${base}/${quote}`);
      setResult(res.data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-2xl font-bold">IA · Análisis de mercado</h1>
      <p className="text-slate-400 text-sm">Pide a la IA una lectura del momento de mercado de un par, basada en sus indicadores actuales.</p>

      <Section title="Consultar a la IA">
        <div className="flex gap-2">
          <select className="input w-auto" value={pair} onChange={(e) => setPair(e.target.value)}>
            {(config?.pairs ?? ["BTC/USDT"]).map((p) => <option key={p}>{p}</option>)}
          </select>
          <button className="btn-primary" onClick={ask} disabled={loading}>{loading ? "Pensando…" : "Pedir lectura"}</button>
        </div>
        <p className="text-xs text-slate-500 mt-2">Proveedor configurado: {config?.llm.provider} · {config?.llm.model} {config?.llm.enabled ? "" : "(IA desactivada)"}</p>
      </Section>

      {loading && <div className="card grid place-items-center py-8"><Spinner /></div>}

      {result && (
        <Section title={`Lectura de ${pair}`}>
          <p className="text-slate-200 leading-relaxed mb-4">{result.commentary}</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(result.indicators).map(([k, v]) => (
              <span key={k} className="text-xs bg-cardalt border border-border rounded px-2 py-1 text-slate-400">{k}: <span className="text-slate-200">{num(v)}</span></span>
            ))}
          </div>
          <p className="text-xs text-slate-600 mt-3">Generado por {result.provider}.</p>
        </Section>
      )}
    </div>
  );
}
