import { describe, expect, it, vi } from 'vitest';
import { WebSocketConnectionRegistry } from './webSocketConnectionRegistry';

const createSocket = () => ({
  close: vi.fn(),
}) as unknown as WebSocket;

const createConnectingSocket = () => ({
  readyState: WebSocket.CONNECTING,
  close: vi.fn(),
  addEventListener: vi.fn(),
}) as unknown as WebSocket;

describe('WebSocketConnectionRegistry', () => {
  it('creates one stable managed record per key', () => {
    const registry = new WebSocketConnectionRegistry<'chat'>();

    const first = registry.getOrCreate('chat');
    const second = registry.getOrCreate('chat');

    expect(first).toBe(second);
    expect(first).toEqual({
      socket: null,
      status: 'idle',
      reconnectAttempts: 0,
    });
    expect('get' in registry).toBe(false);
  });

  it('preserves socket status and reconnect-attempt lifecycle', () => {
    const registry = new WebSocketConnectionRegistry<'chat'>();
    const socket = createSocket();

    registry.setSocket('chat', socket, 'connecting');
    registry.updateStatus('chat', 'open');
    registry.incrementAttempts('chat');
    registry.incrementAttempts('chat');

    expect(registry.getOrCreate('chat')).toMatchObject({
      socket,
      status: 'open',
      reconnectAttempts: 2,
    });

    registry.resetAttempts('chat');
    expect(registry.getOrCreate('chat').reconnectAttempts).toBe(0);
  });

  it('closes one socket and leaves its managed record closed', () => {
    const registry = new WebSocketConnectionRegistry<'chat'>();
    const socket = createSocket();
    registry.setSocket('chat', socket, 'open');

    registry.close('chat');

    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(registry.getOrCreate('chat')).toMatchObject({
      socket: null,
      status: 'closed',
      reconnectAttempts: 0,
    });
  });

  it('defers closing a connecting socket until its connection is established', () => {
    const registry = new WebSocketConnectionRegistry<'chat'>();
    const socket = createConnectingSocket();
    registry.setSocket('chat', socket, 'connecting');

    registry.close('chat');

    expect(socket.close).not.toHaveBeenCalled();
    expect(socket.addEventListener).toHaveBeenCalledWith(
      'open',
      expect.any(Function),
      { once: true },
    );

    const handleOpen = vi.mocked(socket.addEventListener).mock.calls[0][1] as EventListener;
    handleOpen(new Event('open'));

    expect(socket.close).toHaveBeenCalledTimes(1);
  });

  it('disposes every socket and clears managed records', () => {
    const registry = new WebSocketConnectionRegistry<'chat' | 'terminal'>();
    const chatSocket = createSocket();
    const terminalSocket = createSocket();
    registry.setSocket('chat', chatSocket, 'open');
    registry.setSocket('terminal', terminalSocket, 'connecting');

    registry.dispose();

    expect(chatSocket.close).toHaveBeenCalledTimes(1);
    expect(terminalSocket.close).toHaveBeenCalledTimes(1);
    expect(registry.getOrCreate('chat')).toEqual({
      socket: null,
      status: 'idle',
      reconnectAttempts: 0,
    });
  });
});
