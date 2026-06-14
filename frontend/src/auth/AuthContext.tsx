import { createContext, useContext, useState, type ReactNode } from "react";
import { api } from "../lib/api";

interface AuthCtx {
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("algorise_token"));

  const login = async (username: string, password: string) => {
    const res = await api.post("/auth/login", { username, password });
    const t = res.data.access_token as string;
    localStorage.setItem("algorise_token", t);
    setToken(t);
  };

  const logout = () => {
    localStorage.removeItem("algorise_token");
    setToken(null);
  };

  return <Ctx.Provider value={{ token, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
