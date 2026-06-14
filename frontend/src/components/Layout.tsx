import { NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";

const NAV = [
  { to: "/", label: "Panel", icon: "📊" },
  { to: "/config", label: "Configuración", icon: "⚙️" },
  { to: "/strategies", label: "Estrategias", icon: "🧠" },
  { to: "/history", label: "Historial", icon: "📜" },
  { to: "/backtest", label: "Backtesting", icon: "⏮️" },
  { to: "/insights", label: "IA", icon: "🤖" },
  { to: "/settings", label: "Ajustes", icon: "🔧" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Barra lateral (escritorio) / inferior (móvil) */}
      <aside className="md:w-56 md:min-h-screen bg-cardalt border-b md:border-b-0 md:border-r border-border md:flex md:flex-col">
        <div className="hidden md:flex items-center gap-2 px-4 py-4 border-b border-border">
          <img src="/icon.svg" className="w-8 h-8" alt="Algorise" />
          <span className="font-bold text-lg">Algorise</span>
        </div>
        <nav className="flex md:flex-col overflow-x-auto md:overflow-visible">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `flex-shrink-0 flex items-center gap-2 px-4 py-3 text-sm whitespace-nowrap ${
                  isActive ? "text-accent md:bg-card border-b-2 md:border-b-0 md:border-l-2 border-accent" : "text-slate-400 hover:text-slate-200"
                }`
              }
            >
              <span>{n.icon}</span>
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <button
          onClick={() => {
            logout();
            navigate("/login");
          }}
          className="hidden md:block mt-auto text-left px-4 py-3 text-sm text-slate-500 hover:text-loss border-t border-border"
        >
          Cerrar sesión
        </button>
      </aside>

      <main className="flex-1 p-4 md:p-6 max-w-[1400px] w-full mx-auto">{children}</main>
    </div>
  );
}
