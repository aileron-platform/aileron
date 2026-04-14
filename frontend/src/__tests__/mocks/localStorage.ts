/**
 * localStorage Mock 工廠
 * 用於測試 localStorage 操作
 */

import { vi } from 'vitest';

/**
 * 創建 localStorage mock
 */
export const createLocalStorageMock = () => {
  let store: Record<string, string> = {};

  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value.toString();
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((index: number) => {
      const keys = Object.keys(store);
      return keys[index] || null;
    }),
  };
};

/**
 * 設置 localStorage mock
 */
export const setupLocalStorageMock = () => {
  const localStorageMock = createLocalStorageMock();

  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
    writable: true,
  });

  return localStorageMock;
};

/**
 * 設置 localStorage 初始資料
 */
export const setLocalStorageData = (data: Record<string, any>) => {
  Object.entries(data).forEach(([key, value]) => {
    window.localStorage.setItem(
      key,
      typeof value === 'string' ? value : JSON.stringify(value)
    );
  });
};

/**
 * 獲取 localStorage 資料
 */
export const getLocalStorageData = () => {
  const data: Record<string, string> = {};
  for (let i = 0; i < window.localStorage.length; i++) {
    const key = window.localStorage.key(i);
    if (key) {
      data[key] = window.localStorage.getItem(key) || '';
    }
  }
  return data;
};

/**
 * 清除 localStorage
 */
export const clearLocalStorage = () => {
  window.localStorage.clear();
};
