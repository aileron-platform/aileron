/**
 * React Router Mock 工廠
 * 用於模擬路由相關功能
 */

import { vi } from 'vitest';

/**
 * Mock useNavigate
 */
export const mockNavigate = vi.fn();

/**
 * Mock useParams
 */
export const mockParams: Record<string, string> = {};

/**
 * Mock useLocation
 */
export const mockLocation = {
  pathname: '/',
  search: '',
  hash: '',
  state: null,
  key: 'default',
};

/**
 * Mock useSearchParams
 */
export const mockSearchParams = new URLSearchParams();

/**
 * 設置路由參數
 */
export const setMockParams = (params: Record<string, string>) => {
  Object.assign(mockParams, params);
};

/**
 * 設置模擬位置
 */
export const setMockLocation = (location: Partial<typeof mockLocation>) => {
  Object.assign(mockLocation, location);
};

/**
 * 清除路由 mocks
 */
export const clearRouterMocks = () => {
  mockNavigate.mockClear();
  Object.keys(mockParams).forEach(key => delete mockParams[key]);
  setMockLocation({
    pathname: '/',
    search: '',
    hash: '',
    state: null,
    key: 'default',
  });
};

/**
 * Mock react-router-dom 模組
 */
export const setupReactRouterMock = () => {
  vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
      ...actual,
      useNavigate: () => mockNavigate,
      useParams: () => mockParams,
      useLocation: () => mockLocation,
      useSearchParams: () => [mockSearchParams, vi.fn()],
    };
  });
};
