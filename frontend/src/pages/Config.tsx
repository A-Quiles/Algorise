import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Section, Slider, Toggle } from "../components/ui";
import type { BotConfig, StrategyInfo } from "../lib/types";

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];
const COMMON_PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT"];
const PRESETS = [
  { id: "conservador", label: "🛡️ Conservador" },
  { id: "equilibrado", label: "⚖️ Equilibrado" },
  { id: "agresivo", label: "🔥 Agresivo" },
];

export default function Config() {
  const { data, refetch } = useQuery({ queryKey: ["config"], queryFn: async () => (await api.get("/config")).data as BotConfig });
  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: async () => (await api.get("/strategies")).data as StrategyInfo[] });

  const [draft, setDraft] = useState<BotConfig | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (data && !draft) setDraft(structuredClone(data)); }, [data]);

  if (!draft) return <div className="text-slate-400">Cargando configuración…</div>;

  const activeStrategy = strategies?.find((s) => s.id === draft.active_strategy);
  const set = (patch: Partial<BotConfig>) => setDraft({ ...draft, ...patch });
  const setRisk = (patch: Partial<BotConfig["risk"]>) => setDraft({ ...draft, risk: { ...draft.risk, ...patch } });
  const setLLM = (patch: Partial<BotConfig["llm"]>) => setDraft({ ...draft, llm: { ...draft.llm, ...patch } });

  const togglePair = (p: string) => {
    const pairs = draft.pairs.includes(p) ? draft.pairs.filter((x) => x !== p) : [...draft.pairs, p];
    set({ pairs });
  };

  const applyPreset = async (name: string) => {
    await api.post(`/config/preset/${name}`);
    const fresh = await refetch();
    if (fresh.data) setDraft(structuredClone(fresh.data));
    flashSaved();
  };

  const save = async () => {
    setError("");
    try {
      await api.put("/config", draft);
      await refetch();
      flashSaved();
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Error al guardar.");
    }
  };

  const flashSaved = () => { setSaved(true); setTimeout(() => setSaved(false), 2000); };

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Configuración</h1>
        <div className="flex items-center gap-3">
          {saved && <Badge color="green">Guardado ✓</Badge>}
          <button className="btn-primary" onClick={save}>Guardar cambios</button>
        </div>
      </div>
      {error && <div className="card border-loss/50 text-loss text-sm">{error}</div>}

      <Section title="Perfil de riesgo rápido">
        <p className="text-sm text-slate-400 mb-3">Aplica un perfil y luego afina los valores. Se guarda al instante.</p>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button key={p.id} className="btn-ghost" onClick={() => applyPreset(p.id)}>{p.label}</button>
          ))}
        </div>
      </Section>

      <Section title="General">
        <div className="grid sm:grid-cols-3 gap-4">
          <div>
            <label className="label">Capital virtual inicial</label>
            <input type="number" className="input" value={draft.starting_capital} onChange={(e) => set({ starting_capital: parseFloat(e.target.value) })} />
            <p className="text-xs text-slate-500 mt-1">Aplícalo con "Reiniciar cuenta" en Ajustes.</p>
          </div>
          <div>
            <label className="label">Moneda base</label>
            <input className="input" value={draft.base_currency} onChange={(e) => set({ base_currency: e.target.value.toUpperCase() })} />
          </div>
          <div>
            <label className="label">Marco temporal (vela / ciclo)</label>
            <select className="input" value={draft.timeframe} onChange={(e) => set({ timeframe: e.target.value })}>
              {TIMEFRAMES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div className="mt-4">
          <label className="label">Pares a operar</label>
          <div className="flex flex-wrap gap-2">
            {Array.from(new Set([...COMMON_PAIRS, ...draft.pairs])).map((p) => (
              <button key={p} onClick={() => togglePair(p)} className={`px-3 py-1 rounded-full text-sm border ${draft.pairs.includes(p) ? "bg-accent/20 border-accent text-sky-300" : "border-border text-slate-400"}`}>{p}</button>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Estrategia">
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Estrategia activa</label>
            <select className="input" value={draft.active_strategy} onChange={(e) => set({ active_strategy: e.target.value, strategy_params: {} })}>
              {strategies?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            {activeStrategy && <p className="text-xs text-slate-500 mt-2">{activeStrategy.description}</p>}
          </div>
        </div>
        {activeStrategy && (
          <div className="grid sm:grid-cols-2 gap-4 mt-4">
            {activeStrategy.params.map((p) => {
              const value = draft.strategy_params[p.key] ?? p.default;
              return (
                <div key={p.key}>
                  <label className="label">{p.label}</label>
                  <input type="number" className="input" min={p.min} max={p.max} step={p.step} value={value}
                    onChange={(e) => set({ strategy_params: { ...draft.strategy_params, [p.key]: parseFloat(e.target.value) } })} />
                  {p.description && <p className="text-xs text-slate-500 mt-1">{p.description}</p>}
                </div>
              );
            })}
          </div>
        )}
      </Section>

      <Section title="Gestión de riesgo">
        <div className="grid sm:grid-cols-2 gap-x-8 gap-y-5">
          <Slider label="Riesgo por operación" suffix="%" min={0.1} max={10} step={0.1} value={draft.risk.risk_per_trade_pct} onChange={(v) => setRisk({ risk_per_trade_pct: v })} />
          <Slider label="Stop-loss" suffix="%" min={0.5} max={20} step={0.1} value={draft.risk.stop_loss_pct} onChange={(v) => setRisk({ stop_loss_pct: v })} />
          <Slider label="Take-profit" suffix="%" min={0.5} max={50} step={0.1} value={draft.risk.take_profit_pct} onChange={(v) => setRisk({ take_profit_pct: v })} />
          <Slider label="Máx. posiciones abiertas" min={1} max={20} step={1} value={draft.risk.max_open_positions} onChange={(v) => setRisk({ max_open_positions: v })} />
          <Slider label="Límite pérdida diaria" suffix="%" min={1} max={50} step={0.5} value={draft.risk.max_daily_loss_pct} onChange={(v) => setRisk({ max_daily_loss_pct: v })} />
          <Slider label="Drawdown máximo (breaker)" suffix="%" min={5} max={80} step={1} value={draft.risk.max_drawdown_pct} onChange={(v) => setRisk({ max_drawdown_pct: v })} />
        </div>
        <div className="grid sm:grid-cols-2 gap-4 mt-5 items-center">
          <Toggle checked={draft.risk.use_atr_stops} onChange={(v) => setRisk({ use_atr_stops: v })} label="Usar stops por volatilidad (ATR)" />
          {draft.risk.use_atr_stops && <Slider label="Multiplicador ATR" min={0.5} max={6} step={0.1} value={draft.risk.atr_multiplier} onChange={(v) => setRisk({ atr_multiplier: v })} />}
          <div className="flex items-center gap-3">
            <Toggle checked={draft.risk.trailing_stop_pct !== null} onChange={(v) => setRisk({ trailing_stop_pct: v ? 1.5 : null })} label="Trailing stop" />
            {draft.risk.trailing_stop_pct !== null && (
              <input type="number" className="input w-24" step={0.1} min={0.1} value={draft.risk.trailing_stop_pct} onChange={(e) => setRisk({ trailing_stop_pct: parseFloat(e.target.value) })} />
            )}
          </div>
        </div>
      </Section>

      <Section title="Inteligencia artificial (IA gratuita)">
        <div className="flex items-center gap-4 mb-4">
          <Toggle checked={draft.llm.enabled} onChange={(v) => setLLM({ enabled: v })} label="Activar capa de IA (valida y explica operaciones)" />
        </div>
        {draft.llm.enabled && (
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Proveedor</label>
              <select className="input" value={draft.llm.provider} onChange={(e) => setLLM({ provider: e.target.value as any })}>
                <option value="ollama">Ollama (local, gratis y privado)</option>
                <option value="groq">Groq (API gratuita)</option>
                <option value="gemini">Google Gemini (API gratuita)</option>
              </select>
            </div>
            <div>
              <label className="label">Modelo</label>
              <input className="input" value={draft.llm.model} onChange={(e) => setLLM({ model: e.target.value })} placeholder="p.ej. llama3.1:8b" />
            </div>
            <Slider label="Umbral de veto (confianza mínima)" min={0} max={1} step={0.05} value={draft.llm.veto_threshold} onChange={(v) => setLLM({ veto_threshold: v })} />
            <Slider label="Temperatura" min={0} max={1.5} step={0.1} value={draft.llm.temperature} onChange={(v) => setLLM({ temperature: v })} />
          </div>
        )}
      </Section>

      <Section title="Costes de simulación">
        <div className="grid sm:grid-cols-2 gap-4">
          <Slider label="Comisión por operación" suffix="%" min={0} max={1} step={0.01} value={draft.fee_pct} onChange={(v) => set({ fee_pct: v })} />
          <Slider label="Slippage" suffix="%" min={0} max={1} step={0.01} value={draft.slippage_pct} onChange={(v) => set({ slippage_pct: v })} />
        </div>
      </Section>

      <div className="flex justify-end">
        <button className="btn-primary" onClick={save}>Guardar cambios</button>
      </div>
    </div>
  );
}
