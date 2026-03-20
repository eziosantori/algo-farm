import { useEffect, useState } from "react";

export interface ProgressEvent {
  type: string;
  sessionId?: string;
  pct?: number;
  current?: {
    instrument: string;
    timeframe: string;
    iteration: number;
    total: number;
  };
  elapsed_seconds?: number;
  instrument?: string;
  timeframe?: string;
  metrics?: Record<string, number>;
  params?: Record<string, unknown>;
}

export function useSessionProgress(sessionId: string | null) {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [latestProgress, setLatestProgress] = useState<ProgressEvent | null>(null);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (!sessionId) return;

    const wsPort = (import.meta.env["VITE_WS_PORT"] as string | undefined) ?? "3001";
    const wsHost = (import.meta.env["VITE_WS_HOST"] as string | undefined) ?? "localhost";

    const ws = new WebSocket(`ws://${wsHost}:${wsPort}`);

    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify({ action: "subscribe", sessionId }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as ProgressEvent;
        setEvents((prev) => [...prev.slice(-200), msg]);
        if (msg.type === "progress") {
          setLatestProgress(msg);
        }
        if (msg.type === "session_completed" || msg.type === "session_failed" || msg.type === "download_failed") {
          setIsComplete(true);
        }
      } catch {
        // ignore
      }
    };

    ws.onclose = () => setIsConnected(false);
    ws.onerror = () => setIsConnected(false);

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "unsubscribe", sessionId }));
      }
      ws.close();
    };
  }, [sessionId]);

  return { events, isConnected, latestProgress, isComplete };
}
