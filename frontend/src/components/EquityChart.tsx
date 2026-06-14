import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function EquityChart({ data }: { data: { timestamp: string; equity: number }[] }) {
  if (!data || data.length < 2) {
    return <div className="h-[260px] grid place-items-center text-slate-500 text-sm">Sin datos de equity todavía. Arranca el bot para empezar a registrar.</div>;
  }
  const formatted = data.map((d) => ({ t: new Date(d.timestamp).toLocaleString("es-ES", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }), equity: d.equity }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={formatted} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="t" tick={{ fontSize: 10, fill: "#64748b" }} minTickGap={40} />
        <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "#64748b" }} width={60} />
        <Tooltip contentStyle={{ background: "#111a2e", border: "1px solid #1e2a45", borderRadius: 8 }} labelStyle={{ color: "#94a3b8" }} />
        <Area type="monotone" dataKey="equity" stroke="#0ea5e9" strokeWidth={2} fill="url(#eq)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
