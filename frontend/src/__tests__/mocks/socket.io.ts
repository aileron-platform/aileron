/**
 * Socket.IO Mock 工廠
 * 用於模擬 WebSocket 連接
 */

import { vi } from 'vitest';

/**
 * Mock Socket 實例
 */
export const createMockSocket = () => ({
  id: 'mock-socket-id',
  connected: false,
  disconnected: true,
  on: vi.fn(),
  off: vi.fn(),
  once: vi.fn(),
  emit: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  removeAllListeners: vi.fn(),
  listeners: vi.fn(() => []),
  close: vi.fn(),
  open: vi.fn(),
  send: vi.fn(),
  io: {
    engine: {
      close: vi.fn(),
    },
  },
});

/**
 * Mock IO 函數
 */
export const createMockIO = () => {
  const mockSocket = createMockSocket();
  const mockIO = vi.fn(() => mockSocket);

  return {
    mockIO,
    mockSocket,
  };
};

/**
 * 模擬 Socket 事件
 */
export const emitSocketEvent = (
  socket: ReturnType<typeof createMockSocket>,
  event: string,
  ...args: any[]
) => {
  const listeners = socket.on.mock.calls
    .filter(call => call[0] === event)
    .map(call => call[1]);

  listeners.forEach(listener => {
    if (typeof listener === 'function') {
      listener(...args);
    }
  });
};

/**
 * 獲取 Socket 事件監聽器
 */
export const getSocketListener = (
  socket: ReturnType<typeof createMockSocket>,
  event: string
) => {
  const call = socket.on.mock.calls.find(c => c[0] === event);
  return call ? call[1] : null;
};

/**
 * Mock socket.io-client 模組
 */
export const setupSocketIOMock = () => {
  const { mockIO, mockSocket } = createMockIO();

  vi.mock('socket.io-client', () => ({
    io: mockIO,
    Socket: vi.fn(),
  }));

  return { mockIO, mockSocket };
};
