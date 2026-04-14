import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WebSocketConnectionRegistry');

export type WebSocketType = 'terminal' | 'chat' | 'agent-session';

export type ManagedSocketStatus =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  | 'closed';

export interface ManagedSocket {
  socket: WebSocket | null;
  status: ManagedSocketStatus;
  reconnectAttempts: number;
  listeners: Set<ManagedSocketListener>;
}

export type ManagedSocketListener = (status: ManagedSocketStatus) => void;

export class WebSocketConnectionRegistry {
  private sockets = new Map<WebSocketType, ManagedSocket>();

  ensure(type: WebSocketType): ManagedSocket {
    let managed = this.sockets.get(type);
    if (!managed) {
      managed = {
        socket: null,
        status: 'idle',
        reconnectAttempts: 0,
        listeners: new Set(),
      };
      this.sockets.set(type, managed);
    }
    return managed;
  }

  setSocket(type: WebSocketType, socket: WebSocket | null, status: ManagedSocketStatus) {
    const managed = this.ensure(type);
    managed.socket = socket;
    managed.status = status;
    managed.listeners.forEach((listener) => listener(status));
  }

  updateStatus(type: WebSocketType, status: ManagedSocketStatus) {
    const managed = this.ensure(type);
    managed.status = status;
    managed.listeners.forEach((listener) => listener(status));
  }

  incrementAttempts(type: WebSocketType) {
    const managed = this.ensure(type);
    managed.reconnectAttempts += 1;
  }

  resetAttempts(type: WebSocketType) {
    const managed = this.ensure(type);
    managed.reconnectAttempts = 0;
  }

  get(type: WebSocketType): ManagedSocket {
    return this.ensure(type);
  }

  close(type: WebSocketType) {
    const managed = this.ensure(type);
    if (managed.socket) {
      try {
        managed.socket.close();
      } catch (error) {
        logger.error('關閉 WebSocket 失敗', { error });
      }
    }
    managed.socket = null;
    managed.status = 'closed';
    managed.listeners.forEach((listener) => listener('closed'));
  }

  subscribe(type: WebSocketType, listener: ManagedSocketListener): () => void {
    const managed = this.ensure(type);
    managed.listeners.add(listener);
    return () => {
      managed.listeners.delete(listener);
    };
  }

  dispose() {
    this.sockets.forEach((managed) => {
      if (managed.socket) {
        try {
          managed.socket.close();
        } catch (error) {
          logger.error('關閉 WebSocket 失敗', { error });
        }
      }
      managed.listeners.clear();
    });
    this.sockets.clear();
  }
}
