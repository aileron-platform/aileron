import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getThreadApiMock, integration } = vi.hoisted(() => ({
  getThreadApiMock: vi.fn(),
  integration: { runtimeBaseUrl: 'http://runtime.test' as string | null },
}));

vi.mock('../api/threadApi', () => ({
  getThreadApi: getThreadApiMock,
}));

vi.mock('../contexts/AiChatIntegrationContext', () => ({
  useAiChatIntegration: () => integration,
}));

import { useThreadApi } from './useThreadApi';

describe('useThreadApi', () => {
  beforeEach(() => {
    getThreadApiMock.mockReset();
    integration.runtimeBaseUrl = 'http://runtime.test';
  });

  it('creates the HTTP API from the current workspace runtime URL', () => {
    const api = { getThread: vi.fn() };
    getThreadApiMock.mockReturnValue(api);

    const { result } = renderHook(() => useThreadApi());

    expect(getThreadApiMock).toHaveBeenCalledWith('http://runtime.test');
    expect(result.current).toBe(api);
  });

  it('returns null until the workspace runtime URL is available', () => {
    integration.runtimeBaseUrl = null;

    const { result } = renderHook(() => useThreadApi());

    expect(result.current).toBeNull();
    expect(getThreadApiMock).not.toHaveBeenCalled();
  });

  it('uses an explicit Runtime URL outside the workspace provider', () => {
    integration.runtimeBaseUrl = null;
    const api = { getThread: vi.fn() };
    getThreadApiMock.mockReturnValue(api);

    const { result } = renderHook(() => useThreadApi('http://automation-runtime.test'));

    expect(getThreadApiMock).toHaveBeenCalledWith('http://automation-runtime.test');
    expect(result.current).toBe(api);
  });
});
