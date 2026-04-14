/**
 * API Mock 工廠
 * 用於模擬 API 請求和回應
 */

import { vi } from 'vitest';

/**
 * 創建成功的 fetch mock
 */
export const mockFetch = <T>(response: T, init?: Partial<Response>) => {
  return vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: () => Promise.resolve(response),
      text: () => Promise.resolve(JSON.stringify(response)),
      blob: () => Promise.resolve(new Blob()),
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
      formData: () => Promise.resolve(new FormData()),
      headers: new Headers(),
      redirected: false,
      type: 'basic' as ResponseType,
      url: '',
      clone: () => ({} as Response),
      body: null,
      bodyUsed: false,
      ...init,
    } as Response)
  );
};

/**
 * 創建失敗的 fetch mock
 */
export const mockFetchError = (status: number, error: string | object) => {
  const errorResponse = typeof error === 'string' ? { error } : error;

  return vi.fn(() =>
    Promise.resolve({
      ok: false,
      status,
      statusText: 'Error',
      json: () => Promise.resolve(errorResponse),
      text: () => Promise.resolve(JSON.stringify(errorResponse)),
      blob: () => Promise.resolve(new Blob()),
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
      formData: () => Promise.resolve(new FormData()),
      headers: new Headers(),
      redirected: false,
      type: 'basic' as ResponseType,
      url: '',
      clone: () => ({} as Response),
      body: null,
      bodyUsed: false,
    } as Response)
  );
};

/**
 * 創建網路錯誤的 fetch mock
 */
export const mockFetchNetworkError = () => {
  return vi.fn(() => Promise.reject(new Error('Network Error')));
};

/**
 * 設置全局 fetch mock
 */
export const setupFetchMock = () => {
  global.fetch = vi.fn();
  return global.fetch;
};

/**
 * 清除 fetch mock
 */
export const clearFetchMock = () => {
  vi.clearAllMocks();
};

/**
 * 重置 fetch mock
 */
export const resetFetchMock = () => {
  vi.resetAllMocks();
};

/**
 * Mock API 回應類型
 */
export interface MockApiResponse<T = any> {
  data?: T;
  error?: string;
  message?: string;
  status?: number;
}

/**
 * 創建標準 API 回應
 */
export const createApiResponse = <T>(data: T, message?: string): MockApiResponse<T> => ({
  data,
  message,
  status: 200,
});

/**
 * 創建 API 錯誤回應
 */
export const createApiError = (error: string, status: number = 400): MockApiResponse => ({
  error,
  status,
});
