/**
 */

import { afterEach, beforeEach, beforeAll, afterAll } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
  configurable: true,
  value: () => {},
});

beforeEach(() => {
  document.body.style.pointerEvents = '';
});

afterEach(() => {
  cleanup();
  document.body.style.pointerEvents = '';
});

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {}, // deprecated
    removeListener: () => {}, // deprecated
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return [];
  }
  unobserve() {}
} as any;

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
} as any;

// Mock localStorage
class LocalStorageMock implements Storage {
  private store: Record<string, string> = {};

  getItem(key: string): string | null {
    return this.store[key] || null;
  }

  setItem(key: string, value: string): void {
    this.store[key] = value.toString();
  }

  removeItem(key: string): void {
    delete this.store[key];
  }

  clear(): void {
    this.store = {};
  }

  get length(): number {
    return Object.keys(this.store).length;
  }

  key(index: number): string | null {
    const keys = Object.keys(this.store);
    return keys[index] || null;
  }

  // Make keys enumerable for Object.keys() to work
  [key: string]: any;
}

const localStorageMock = new LocalStorageMock();

// Proxy to make stored keys enumerable
const localStorageProxy = new Proxy(localStorageMock, {
  ownKeys(target) {
    return Object.keys((target as any).store);
  },
  getOwnPropertyDescriptor(target, prop) {
    if (typeof prop === 'string' && (target as any).store[prop] !== undefined) {
      return {
        enumerable: true,
        configurable: true,
        value: (target as any).store[prop],
      };
    }
    return Object.getOwnPropertyDescriptor(target, prop);
  },
});

Object.defineProperty(window, 'localStorage', {
  value: localStorageProxy,
  writable: true,
});

// Mock sessionStorage
Object.defineProperty(window, 'sessionStorage', {
  value: localStorageProxy,
  writable: true,
});

// Mock DataTransfer for drag and drop testing
class DataTransferMock {
  private data: Record<string, string> = {};
  effectAllowed: string = 'all';
  dropEffect: string = 'none';
  files: FileList = [] as any;
  items: DataTransferItemList = [] as any;
  types: string[] = [];

  setData(format: string, data: string): void {
    this.data[format] = data;
    if (!this.types.includes(format)) {
      this.types.push(format);
    }
  }

  getData(format: string): string {
    return this.data[format] || '';
  }

  clearData(format?: string): void {
    if (format) {
      delete this.data[format];
      this.types = this.types.filter(t => t !== format);
    } else {
      this.data = {};
      this.types = [];
    }
  }

  setDragImage(): void {}
}

global.DataTransfer = DataTransferMock as any;

// Mock window.location
delete (window as any).location;
window.location = {
  ...window.location,
  href: 'http://localhost:8082',
  origin: 'http://localhost:8082',
  protocol: 'http:',
  host: 'localhost:8082',
  hostname: 'localhost',
  port: '8082',
  pathname: '/',
  search: '',
  hash: '',
  reload: () => {},
  replace: () => {},
  assign: () => {},
} as any;

// Suppress console errors in tests (optional)
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: ReactDOM.render') ||
        args[0].includes('Not implemented: HTMLFormElement.prototype.submit'))
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});
