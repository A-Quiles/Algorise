import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Card } from "../components/ui";
import type { BotConfig, StrategyInfo } from "../lib/types";

export default function Strategies() {
  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: async () => (await api.get("/strategies")).data as StrategyInfo[] });
  const { data: config, refetch } = useQuery({ queryKey: ["config"], queryFn: async () => (await api.get("/config")).data as BotConfig });

  const activate = async (id: string) => {
    await api.patch("/config", { active_strategy: id, strategy_params: {} });
    refetch();
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Estrategias</h1>
      <p className="text-slate-400 text-sm">Cada estrategia decide las señales de compra/venta. Elige una como activa; sus parámetros se ajustan en Configuración.</p>
      <div className="grid md:grid-cols-2 gap-4">
        {strategies?.map((s) => {
          const active = config?.active_strategy === s.id;
          return (
            <Card key={s.id} className={active ? "border-accent" : ""}>
              <div className="flex items-center justify-between mb-2">
                <h2 className="font-semibold">{s.name}</h2>
                {active ? <Badge color="green">Activa</Badge> : <button className="btn-ghost text-sm py-1" onClick={() => activate(s.id)}>Activar</button>}
              </div>
              <p className="text-sm text-slate-400 mb-3">{s.description}</p>
              <div className="flex flex-wrap gap-2">
                {s.params.map((p) => (
                  <span key={p.key} className="text-xs bg-cardalt border border-border rounded px-2 py-1 text-slate-400">
                    {p.label}: <span className="text-slate-200">{p.default}</span>
                  </span>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
