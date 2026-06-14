import { useEffect, useRef, useState } from "react";
import { WS_URL } from "./api";
import type { DashboardPayload } from "./types";

// Hook que mantiene una conexión WebSocket viva y devuelve el último payload del panel.
export function useDashboardSocket() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let stop = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (stop) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          const payload = JSON.parse(ev.data) as DashboardPayload;
          if (payload?.account) setData(payload);
        } catch {
          /* ignora mensajes no-JSON */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!stop) retry = setTimeout(connect, 3000); // reconexión automática
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      stop = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, []);

  return { data, connected };
}
