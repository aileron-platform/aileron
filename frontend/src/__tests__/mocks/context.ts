/**
 * Context Mock 工廠
 * 用於模擬 React Context
 */

import { vi } from 'vitest';

/**
 * Mock Auth Context
 */
export const createMockAuthContext = (overrides = {}) => ({
  user: {
    id: 'user-1',
    email: 'test@example.com',
    username: 'testuser',
    role: 'user',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  isAuthenticated: true,
  isLoading: false,
  error: null,
  login: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
  token: 'mock-token',
  ...overrides,
});

/**
 * Mock Workspace Context
 */
export const createMockWorkspaceContext = (overrides = {}) => ({
  workspace: {
    id: 'ws-1',
    name: 'Test Workspace',
    description: 'Test Description',
    status: 'running',
    userId: 'user-1',
    containerImage: 'node:latest',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  isLoading: false,
  error: null,
  updateWorkspace: vi.fn(),
  deleteWorkspace: vi.fn(),
  refreshWorkspace: vi.fn(),
  ...overrides,
});

/**
 * Mock Claude Code Context
 */
export const createMockClaudeCodeContext = (overrides = {}) => ({
  isEnabled: true,
  isConnected: false,
  status: 'idle',
  connect: vi.fn(),
  disconnect: vi.fn(),
  sendMessage: vi.fn(),
  ...overrides,
});

/**
 * Mock I18n Context
 */
export const createMockI18nContext = (overrides = {}) => ({
  language: 'zh-TW',
  t: vi.fn((key: string) => key),
  changeLanguage: vi.fn(),
  languages: ['zh-TW', 'en'],
  ...overrides,
});

/**
 * Mock Theme Context
 */
export const createMockThemeContext = (overrides = {}) => ({
  theme: 'light',
  setTheme: vi.fn(),
  toggleTheme: vi.fn(),
  ...overrides,
});

/**
 * Mock Realtime Context
 */
export const createMockRealtimeContext = (overrides = {}) => ({
  isConnected: false,
  connectionStatus: 'disconnected',
  connect: vi.fn(),
  disconnect: vi.fn(),
  subscribe: vi.fn(),
  unsubscribe: vi.fn(),
  ...overrides,
});
