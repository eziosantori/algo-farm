import { WebSocketServer, WebSocket } from "ws";
import type { Server as HttpServer } from "http";

// sessionId -> connected WebSocket clients subscribed to live progress
const subscribers = new Map<string, Set<WebSocket>>();

export function createWsServer(httpServer: HttpServer): WebSocketServer {
  const wss = new WebSocketServer({ server: httpServer });

  wss.on("connection", (ws: WebSocket) => {
    ws.on("message", (data) => {
      try {
        const msg = JSON.parse(data.toString()) as {
          action?: string;
          sessionId?: string;
        };

        if (msg.action === "subscribe" && msg.sessionId) {
          if (!subscribers.has(msg.sessionId)) {
            subscribers.set(msg.sessionId, new Set());
          }
          subscribers.get(msg.sessionId)!.add(ws);
          ws.send(JSON.stringify({ type: "subscribed", sessionId: msg.sessionId }));
        }

        if (msg.action === "unsubscribe" && msg.sessionId) {
          subscribers.get(msg.sessionId)?.delete(ws);
        }
      } catch {
        // ignore malformed messages
      }
    });

    ws.on("close", () => {
      subscribers.forEach((clients) => clients.delete(ws));
    });
  });

  return wss;
}

export function broadcast(sessionId: string, message: unknown): void {
  const clients = subscribers.get(sessionId);
  if (!clients || clients.size === 0) return;
  const data = JSON.stringify(message);
  for (const ws of clients) {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(data);
    }
  }
}
