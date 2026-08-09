// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useShowInitMessages } from './useShowInitMessages';

beforeEach(() => {
  localStorage.clear();
});

describe('useShowInitMessages', () => {
  it('defaults to hidden and persists a toggle to true', () => {
    const { result } = renderHook(() => useShowInitMessages());

    expect(result.current[0]).toBe(false);

    act(() => {
      result.current[1](true);
    });

    expect(result.current[0]).toBe(true);
    expect(localStorage.getItem('aichat.showInitMessages')).toBe('true');
  });

  it('keeps separate hook instances in sync through the shared store', () => {
    const first = renderHook(() => useShowInitMessages());
    const second = renderHook(() => useShowInitMessages());

    act(() => {
      first.result.current[1](true);
    });

    expect(second.result.current[0]).toBe(true);
  });
});
