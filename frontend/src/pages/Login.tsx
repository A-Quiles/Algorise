import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Usuario o contraseña incorrectos.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center p-4">
      <form onSubmit={submit} className="card w-full max-w-sm">
        <div className="flex items-center gap-3 mb-6">
          <img src="/icon.svg" className="w-12 h-12" alt="Algorise" />
          <div>
            <h1 className="text-xl font-bold">Algorise</h1>
            <p className="text-xs text-slate-400">Bot de trading IA · modo papel</p>
          </div>
        </div>
        <label className="label">Usuario</label>
        <input className="input mb-3" value={username} onChange={(e) => setUsername(e.target.value)} />
        <label className="label">Contraseña</label>
        <input type="password" className="input mb-4" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p className="text-loss text-sm mb-3">{error}</p>}
        <button className="btn-primary w-full" disabled={loading}>{loading ? "Entrando…" : "Entrar"}</button>
        <p className="text-xs text-slate-500 mt-4 text-center">Credenciales por defecto: admin / admin (cámbialas en Ajustes del .env)</p>
      </form>
    </div>
  );
}
