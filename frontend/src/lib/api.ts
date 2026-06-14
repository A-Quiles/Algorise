import axios from "axios";

// El backend corre en el puerto 8000. Por defecto usamos el mismo host que sirve la web,
// para que también funcione desde el móvil (que carga la web por la IP del PC).
const API_HOST =
  (import.meta.env.VITE_API_URL as string | undefined) ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

export const API_BASE = `${API_HOST}/api`;
export const WS_URL = `${API_HOST.replace(/^http/, "ws")}/api/ws`;

export const api = axios.create({ baseURL: API_BASE });

// Inyecta el token en cada petición.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("algorise_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Si el token caduca, vuelve al login.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config.url?.includes("/auth/login")) {
      localStorage.removeItem("algorise_token");
      if (location.pathname !== "/login") location.href = "/login";
    }
    return Promise.reject(err);
  }
);
