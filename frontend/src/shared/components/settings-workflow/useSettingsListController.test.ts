import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useSettingsListController } from './useSettingsListController';

interface TestItem {
  id: string;
  name: string;
  description?: string;
  scope: string;
}

const items: TestItem[] = [
  { id: 'one', name: 'foo server', description: 'alpha', scope: 'project' },
  { id: 'two', name: 'bar server', description: 'foo beta', scope: 'user' },
  { id: 'three', name: 'baz server', description: 'gamma', scope: 'user' },
];

describe('useSettingsListController', () => {
  it('filters items by query', () => {
    const { result } = renderHook(() => useSettingsListController(items));

    act(() => result.current.setQuery('foo'));

    expect(result.current.filteredItems.map((item) => item.id)).toEqual(['one', 'two']);
  });

  it('filters items by scope', () => {
    const { result } = renderHook(() => useSettingsListController(items));

    act(() => result.current.setScope('project'));

    expect(result.current.filteredItems.map((item) => item.id)).toEqual(['one']);
  });

  it('applies query and scope filters together', () => {
    const { result } = renderHook(() => useSettingsListController(items));

    act(() => {
      result.current.setQuery('foo');
      result.current.setScope('user');
    });

    expect(result.current.filteredItems.map((item) => item.id)).toEqual(['two']);
  });

  it('opens create mode with a seed object', () => {
    const { result } = renderHook(() => useSettingsListController<TestItem>(items));
    const seed = { name: 'draft' };

    act(() => result.current.openCreate(seed));

    expect(result.current.editorOpen).toBe(true);
    expect(result.current.editorMode).toBe('create');
    expect(result.current.editorSeed).toEqual(seed);
    expect(result.current.selectedItem).toBeNull();
  });

  it('opens edit mode with the selected item', () => {
    const { result } = renderHook(() => useSettingsListController(items));

    act(() => result.current.openEdit(items[1]));

    expect(result.current.editorOpen).toBe(true);
    expect(result.current.editorMode).toBe('edit');
    expect(result.current.selectedItem).toEqual(items[1]);
  });
});
