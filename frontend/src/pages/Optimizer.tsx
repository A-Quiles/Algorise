import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Section, Spinner, Badge } from "../components/ui";
import { num, pct } from "../lib/format";
import { COMMON_COINS, QUOTE_CURRENCIES, makePair } from "../lib/markets";
import type { BotConfig, OptJob, OptResultItem, StrategyInfo } from "../lib/types";

const TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"];

export default function Optimizer() {
  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: async () => (await api.get("/strategies")).data as StrategyInfo[] });
  const { data: config } = useQuery({ queryKey: ["config"], queryFn: async () => (await api.get("/config")).data as BotConfig });
  const { data: objectives } = useQuery({ queryKey: ["objectives"], queryFn: async () => (await api.get("/backtest/objectives")).data as Record<string, string> });

  const [coin, setCoin] = useState("BTC");
  const [quote, setQuote] = useState("USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [days, setDays] = useState(180);
  const [capital, setCapital] = useState(10000);
  const [objective, setObjective] = useState("total_return_pct");
  const [samples, setSamples] = useState(20);
  const [selected, setSelected] = useState<string[]>([]);
  const [job, setJob] = useState<OptJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const symbol = makePair(coin, quote);
  const pollRef = useRef<number | null>(null);

  // Por defecto, todas las estrategias seleccionadas.
  useEffect(() => { if (strategies && selected.length === 0) setSelected(strategies.map((s) => s.id)); }, [strategies]);
  // Limpia el polling al desmontar.
  useEffect(() => () => { if (pollRef.current) window.clearTimeout(pollRef.current); }, []);

  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const poll = (id: string) => {
    const tick = async () => {
      try {
        const res = await api.get(`/backtest/optimize/${id}`);
        const j = res.data as OptJob;
        setJob(j);
        if (j.status === "running") pollRef.current = window.setTimeout(tick, 1500);
      } catch {
        setError("Error consultando el progreso de la optimización.");
      }
    };
    tick();
  };

  const start = async () => {
    setError(""); setMsg(""); setJob(null);
    if (selected.length === 0) { setError("Selecciona al menos una estrategia."); return; }
    setStarting(true);
    try {
      const res = await api.post("/backtest/optimize", {
        symbol, timeframe, days, starting_capital: capital,
        strategy_ids: selected, samples_per_strategy: samples, objective,
      });
      poll(res.data.job_id as string);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "No se pudo iniciar la optimización.");
    } finally {
      setStarting(false);
    }
  };

  const buildConfig = (r: OptResultItem): BotConfig => ({
    ...(config as BotConfig),
    active_strategy: r.strategy_id,
    strategy_params: r.params,
    timeframe,
    base_currency: quote,
    pairs: [symbol],
    risk: {
      ...(config as BotConfig).risk,
      ...r.risk_config,
    },
  });

  const flash = (text: string) => { setMsg(text); setTimeout(() => setMsg(""), 2500); };

  const saveResult = async (r: OptResultItem) => {
    if (!config) return;
    const name = window.prompt("Nombre para guardar esta configuración:", `${r.strategy_name} · ${symbol} ${timeframe}`);
    if (!name) return;
    try {
      await api.post("/config/saved", {
        name, config: buildConfig(r), source: "optimizer",
        note: `${job?.objective_label}: ${objectiveValue(r)} · ${symbol} ${timeframe} · ${days}d`,
      });
      flash("Configuración guardada ✓ (la verás en Configuración)");
    } catch {
      setError("No se pudo guardar la configuración.");
    }
  };

  const applyResult = async (r: OptResultItem) => {
    if (!config) return;
    if (!window.confirm(`¿Aplicar «${r.strategy_name}» como configuración activa del bot?`)) return;
    try {
      await api.put("/config", buildConfig(r));
      flash("Configuración aplicada al bot ✓");
    } catch (e: any) {
      setError(e?.response?.data?.detail || "No se pudo aplicar la configuración.");
    }
  };

  const objectiveValue = (r: OptResultItem): string => {
    const v = r.metrics[objective];
    if (v === null || v === undefined) return objective === "profit_factor" ? "∞" : "—";
    return typeof v === "number" ? num(v, 2) : String(v);
  };

  const progress = job && job.total > 0 ? Math.round((job.done / job.total) * 100) : 0;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Backtesting automático</h1>
      <p className="text-slate-400 text-sm">La IA prueba muchas combinaciones de estrategia, parámetros y configuración sobre el histórico y te devuelve las <b>10 mejores</b> con su configuración exacta. Puedes <b>guardarlas</b> o <b>aplicarlas</b> al bot con un clic.</p>

      <Section title="Qué optimizar">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 items-end">
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
            <label className="label">Días de histórico</label>
            <input type="number" className="input" value={days} min={10} max={1000} onChange={(e) => setDays(parseInt(e.target.value))} />
          </div>
          <div>
            <label className="label">Capital inicial</label>
            <input type="number" className="input" value={capital} onChange={(e) => setCapital(parseFloat(e.target.value))} />
          </div>
          <div>
            <label className="label">Optimizar para</label>
            <select className="input" value={objective} onChange={(e) => setObjective(e.target.value)}>
              {objectives && Object.entries(objectives).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Combinaciones por estrategia: {samples}</label>
            <input type="range" min={5} max={60} step={5} value={samples} onChange={(e) => setSamples(parseInt(e.target.value))} className="w-full accent-sky-500" />
          </div>
        </div>

        <div className="mt-4">
          <label className="label">Estrategias a probar</label>
          <div className="flex flex-wrap gap-2">
            {strategies?.map((s) => (
              <button key={s.id} onClick={() => toggle(s.id)} type="button"
                className={`px-3 py-1 rounded-full text-sm border ${selected.includes(s.id) ? "bg-accent/20 border-accent text-sky-300" : "border-border text-slate-400"}`}>
                {s.name}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 mt-4">
          <button className="btn-primary" onClick={start} disabled={starting || job?.status === "running"}>
            {job?.status === "running" ? "Optimizando…" : starting ? "Iniciando…" : "Iniciar optimización"}
          </button>
          <span className="text-xs text-slate-500">Probará ~{selected.length * samples} combinaciones sobre {symbol} {timeframe}.</span>
        </div>
      </Section>

      {error && <div className="card border-loss/50 text-loss text-sm">{error}</div>}
      {msg && <div className="card border-accent/50 text-sky-300 text-sm">{msg}</div>}

      {job?.status === "running" && (
        <Section title="Progreso">
          <div className="flex items-center gap-3">
            <Spinner />
            <div className="flex-1">
              <div className="h-2 bg-cardalt rounded-full overflow-hidden">
                <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-xs text-slate-400 mt-1">{job.done} / {job.total} combinaciones ({progress}%)</p>
            </div>
          </div>
        </Section>
      )}

      {job?.status === "error" && <div className="card text-amber-400 text-sm">{job.error}</div>}

      {job?.status === "done" && (
        <Section title={`Top ${job.results.length} resultados — optimizado para «${job.objective_label}»`}>
          {job.results.length === 0 ? (
            <p className="text-sm text-slate-400">Ninguna combinación generó operaciones. Prueba más días, otro marco temporal o más combinaciones.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-400 text-xs">
                  <tr className="text-left border-b border-border">
                    <th className="py-2">#</th><th>Estrategia</th><th>{job.objective_label}</th>
                    <th>Retorno</th><th>vs Hold</th><th>Aciertos</th><th>Ops.</th><th>Máx DD</th>
                    <th>Riesgo/op</th><th>SL%</th><th>TP%</th><th>Parámetros</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {job.results.map((r) => (
                    <tr key={r.rank} className="border-b border-border/50 align-top">
                      <td className="py-2 font-semibold">{r.rank}</td>
                      <td className="font-medium text-slate-200">{r.strategy_name}</td>
                      <td className="text-sky-300 font-semibold">{objectiveValue(r)}</td>
                      <td className={pnlColorOf(r.metrics.total_return_pct)}>{pct(r.metrics.total_return_pct as number)}</td>
                      <td className={pnlColorOf(r.metrics.vs_buy_hold_pct)}>{pct(r.metrics.vs_buy_hold_pct as number)}</td>
                      <td>{r.metrics.win_rate_pct as number}%</td>
                      <td>{r.metrics.num_trades as number}</td>
                      <td className="text-loss">{pct(r.metrics.max_drawdown_pct as number)}</td>
                      <td className="text-xs">{r.risk_config.risk_per_trade_pct}%</td>
                      <td className="text-xs">{r.risk_config.stop_loss_pct}%</td>
                      <td className="text-xs">{r.risk_config.take_profit_pct}%</td>
                      <td className="text-xs text-slate-400 max-w-[180px]">
                        {Object.entries(r.params).map(([k, v]) => `${k}:${v}`).join(" ")}
                      </td>
                      <td className="whitespace-nowrap">
                        <button className="btn-ghost text-xs py-1 mr-1" onClick={() => saveResult(r)}>Guardar</button>
                        <button className="btn-ghost text-xs py-1" onClick={() => applyResult(r)}>Aplicar</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-xs text-slate-500 mt-3">
            <Badge color="sky">consejo</Badge> «Guardar» añade la config a tu biblioteca (Configuración → Configuraciones guardadas). «Aplicar» la activa en el bot al instante.
          </p>
        </Section>
      )}
    </div>
  );
}

function pnlColorOf(v: unknown): string {
  const n = typeof v === "number" ? v : 0;
  if (n === 0) return "text-slate-300";
  return n > 0 ? "text-profit" : "text-loss";
}
