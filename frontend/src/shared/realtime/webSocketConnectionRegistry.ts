import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WebSocketConnectionRegistry');

export type ManagedSocketStatus =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  | 'closed';

interface ManagedSocket {
  socket: WebSocket | null;
  status: ManagedSocketStatus;
  reconnectAttempts: number;
}

const closeSocket = (socket: WebSocket): void => {
  if (socket.readyState === WebSocket.CONNECTING) {
    socket.addEventListener('open', () => socket.close(), { once: true });
    return;
  }
  socket.close();
};

export class WebSocketConnectionRegistry<Key extends string = string> {
  private sockets = new Map<Key, ManagedSocket>();

  private ensure(type: Key): ManagedSocket {
    let managed = this.sockets.get(type);
    if (!managed) {
      managed = {
        socket: null,
        status: 'idle',
        reconnectAttempts: 0,
      };
      this.sockets.set(type, managed);
    }
    return managed;
  }

  setSocket(type: Key, socket: WebSocket | null, status: ManagedSocketStatus) {
    const managed = this.ensure(type);
    managed.socket = socket;
    managed.status = status;
  }

  updateStatus(type: Key, status: ManagedSocketStatus) {
    const managed = this.ensure(type);
    managed.status = status;
  }

  incrementAttempts(type: Key) {
    const managed = this.ensure(type);
    managed.reconnectAttempts += 1;
  }

  resetAttempts(type: Key) {
    const managed = this.ensure(type);
    managed.reconnectAttempts = 0;
  }

  getOrCreate(type: Key): ManagedSocket {
    return this.ensure(type);
  }

  close(type: Key) {
    const managed = this.ensure(type);
    if (managed.socket) {
      try {
        closeSocket(managed.socket);
      } catch (error) {
        logger.error('Failed to close WebSocket', { error });
      }
    }
    managed.socket = null;
    managed.status = 'closed';
  }

  dispose() {
    this.sockets.forEach((managed) => {
      if (managed.socket) {
        try {
          closeSocket(managed.socket);
        } catch (error) {
          logger.error('Failed to close WebSocket', { error });
        }
      }
    });
    this.sockets.clear();
  }
}
