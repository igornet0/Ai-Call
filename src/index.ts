import express from 'express';
import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import { randomUUID } from 'crypto';

type ClientId = string;

type SignalMessage =
  | { type: 'join'; roomId: string }
  | { type: 'leave'; roomId: string }
  | { type: 'signal'; roomId: string; targetId: ClientId; payload: unknown }
  | { type: 'peers'; roomId: string; peers: ClientId[] }
  | { type: 'ping' };

type ServerToClient =
  | { type: 'welcome'; clientId: ClientId }
  | { type: 'peers'; roomId: string; peers: ClientId[] }
  | { type: 'signal'; fromId: ClientId; payload: unknown }
  | { type: 'error'; message: string };

const app = express();
const httpServer = createServer(app);
const wss = new WebSocketServer({ server: httpServer, path: '/ws' });

// roomId -> set of clientIds
const roomIdToClients = new Map<string, Set<ClientId>>();
// clientId -> ws
const clientIdToSocket = new Map<ClientId, WebSocket>();
// clientId -> roomId
const clientIdToRoom = new Map<ClientId, string>();

function send(ws: WebSocket, message: ServerToClient) {
  try {
    ws.send(JSON.stringify(message));
  } catch (_) {
    // ignore
  }
}

wss.on('connection', (ws) => {
  const clientId = randomUUID();
  clientIdToSocket.set(clientId, ws);
  send(ws, { type: 'welcome', clientId });

  ws.on('message', (raw) => {
    let msg: SignalMessage | null = null;
    try {
      msg = JSON.parse(String(raw));
    } catch {
      send(ws, { type: 'error', message: 'invalid json' });
      return;
    }

    if (!msg) return;

    switch (msg.type) {
      case 'join': {
        const { roomId } = msg;
        const prevRoom = clientIdToRoom.get(clientId);
        if (prevRoom && prevRoom !== roomId) {
          leaveRoom(clientId, prevRoom);
        }
        clientIdToRoom.set(clientId, roomId);
        const set = roomIdToClients.get(roomId) ?? new Set<ClientId>();
        set.add(clientId);
        roomIdToClients.set(roomId, set);
        broadcastPeers(roomId);
        break;
      }
      case 'leave': {
        const { roomId } = msg;
        leaveRoom(clientId, roomId);
        break;
      }
      case 'signal': {
        const { roomId, targetId, payload } = msg;
        const currentRoom = clientIdToRoom.get(clientId);
        if (currentRoom !== roomId) return;
        const targetWs = clientIdToSocket.get(targetId);
        if (targetWs && targetWs.readyState === WebSocket.OPEN) {
          send(targetWs, { type: 'signal', fromId: clientId, payload });
        }
        break;
      }
      case 'ping':
        // Keepalive
        break;
      default:
        send(ws, { type: 'error', message: 'unknown message' });
    }
  });

  ws.on('close', () => {
    const roomId = clientIdToRoom.get(clientId);
    clientIdToSocket.delete(clientId);
    clientIdToRoom.delete(clientId);
    if (roomId) {
      const set = roomIdToClients.get(roomId);
      if (set) {
        set.delete(clientId);
        if (set.size === 0) roomIdToClients.delete(roomId);
        else broadcastPeers(roomId);
      }
    }
  });
});

function leaveRoom(clientId: ClientId, roomId: string) {
  const ws = clientIdToSocket.get(clientId);
  const set = roomIdToClients.get(roomId);
  if (set) {
    set.delete(clientId);
    if (set.size === 0) roomIdToClients.delete(roomId);
  }
  clientIdToRoom.delete(clientId);
  if (set && set.size > 0) broadcastPeers(roomId);
  if (ws && ws.readyState === WebSocket.OPEN) {
    send(ws, { type: 'peers', roomId, peers: Array.from(set ?? []) });
  }
}

function broadcastPeers(roomId: string) {
  const set = roomIdToClients.get(roomId);
  if (!set) return;
  const peers = Array.from(set);
  for (const id of peers) {
    const ws = clientIdToSocket.get(id);
    if (ws && ws.readyState === WebSocket.OPEN) {
      send(ws, { type: 'peers', roomId, peers: peers.filter((p) => p !== id) });
    }
  }
}

app.get('/health', (_req, res) => res.json({ status: 'ok' }));
// Serve static client
import { mountStatic } from './static';
mountStatic(app);

const PORT = process.env.PORT ? Number(process.env.PORT) : 3000;
const HOST = process.env.HOST ?? '0.0.0.0';
httpServer.listen(PORT, HOST, () => {
  // eslint-disable-next-line no-console
  console.log(`Signaling server listening on http://${HOST}:${PORT}`);
});


