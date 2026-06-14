import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import { Section } from "../components/ui";
import { money } from "../lib/format";
import type { BotConfig } from "../lib/types";

export default function Settings() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const { data: config } = useQuery({ queryKey: ["config"], queryFn: async () => (await api.get("/config")).data as BotConfig });
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: async () => (await api.get("/health")).data });
  const [capital, setCapital] = useState<number | "">("");
  const [msg, setMsg] = useState("");

  const reset = async () => {
    if (!confirm("Esto borrará TODO el historial (operaciones, señales, logs) y reiniciará la cartera virtual. ¿Continuar?")) return;
    const body = capital === "" ? {} : { starting_capital: capital };
    const res = await api.post("/bot/reset", body);
    setMsg(`Cuenta reiniciada con ${money(res.data.starting_capital, config?.base_currency)}.`);
    setTimeout(() => setMsg(""), 4000);
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-bold">Ajustes</h1>

      <Section title="Reiniciar cuenta virtual">
        <p className="text-sm text-slate-400 mb-3">Vuelve a empezar de cero. Borra historial y restablece el efectivo. El bot se detiene.</p>
        <div className="flex gap-2 items-end">
          <div>
            <label className="label">Capital inicial (vacío = usar config: {money(config?.starting_capital, config?.base_currency)})</label>
            <input type="number" className="input" placeholder={String(config?.starting_capital ?? 10000)} value={capital} onChange={(e) => setCapital(e.target.value === "" ? "" : parseFloat(e.target.value))} />
          </div>
          <button className="btn-danger" onClick={reset}>Reiniciar</button>
        </div>
        {msg && <p className="text-profit text-sm mt-3">{msg}</p>}
      </Section>

      <Section title="Información">
        <ul className="text-sm text-slate-400 space-y-1">
          <li>Estado API: <span className="text-profit">{health?.status ?? "—"}</span></li>
          <li>Modo: <span className="text-amber-400">{health?.mode ?? "paper"}</span> (dinero ficticio)</li>
          <li>Proveedor de IA: {config?.llm.provider} · {config?.llm.model}</li>
          <li>Pares activos: {config?.pairs.join(", ")}</li>
        </ul>
        <p className="text-xs text-slate-600 mt-3">
          La contraseña y las claves se cambian en el archivo <code className="text-slate-400">backend/.env</code>.
          El paso a dinero real (futuro) requerirá añadir claves de Binance y confirmaciones de seguridad.
        </p>
      </Section>

      <Section title="Sesión">
        <button className="btn-ghost" onClick={() => { logout(); navigate("/login"); }}>Cerrar sesión</button>
      </Section>
    </div>
  );
}
