import type React from 'react';
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { VersionControlFileChange } from '@/shared/version-control';
import { useVersionControlFileSelection } from './useVersionControlFileSelection';

const file = (path: string): VersionControlFileChange => ({
  name: path.split('/').at(-1) ?? path,
  path,
  status: 'M',
});

const mouseEvent = (init: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean } = {}) => ({
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  preventDefault: vi.fn(),
  ...init,
}) as unknown as React.MouseEvent;

describe('useVersionControlFileSelection', () => {
  it('selects one file and clears the opposite group', () => {
    const onFileSelect = vi.fn();
    const staged = [file('staged-a.md'), file('staged-b.md')];
    const unstaged = [file('unstaged-a.md'), file('unstaged-b.md')];

    const { result } = renderHook(() => useVersionControlFileSelection({ stagedFiles: staged, unstagedFiles: unstaged, onFileSelect }));

    act(() => result.current.selectFile(unstaged[0], 'unstaged', mouseEvent()));
    expect(result.current.selectedUnstagedPaths).toEqual(new Set(['unstaged-a.md']));
    expect(result.current.selectedStagedPaths).toEqual(new Set());
    expect(onFileSelect).toHaveBeenLastCalledWith(unstaged[0], 'unstaged');

    act(() => result.current.selectFile(staged[0], 'staged', mouseEvent()));
    expect(result.current.selectedStagedPaths).toEqual(new Set(['staged-a.md']));
    expect(result.current.selectedUnstagedPaths).toEqual(new Set());
    expect(onFileSelect).toHaveBeenLastCalledWith(staged[0], 'staged');
  });

  it('toggles selected files with Ctrl or Cmd', () => {
    const unstaged = [file('a.md'), file('b.md')];
    const { result } = renderHook(() => useVersionControlFileSelection({ stagedFiles: [], unstagedFiles: unstaged }));

    act(() => result.current.selectFile(unstaged[0], 'unstaged', mouseEvent({ ctrlKey: true })));
    act(() => result.current.selectFile(unstaged[1], 'unstaged', mouseEvent({ metaKey: true })));
    expect(result.current.selectedUnstagedPaths).toEqual(new Set(['a.md', 'b.md']));

    act(() => result.current.selectFile(unstaged[0], 'unstaged', mouseEvent({ ctrlKey: true })));
    expect(result.current.selectedUnstagedPaths).toEqual(new Set(['b.md']));
  });

  it('selects a visible range with Shift', () => {
    const staged = [file('a.md'), file('b.md'), file('c.md'), file('d.md')];
    const { result } = renderHook(() => useVersionControlFileSelection({ stagedFiles: staged, unstagedFiles: [] }));

    act(() => result.current.selectFile(staged[0], 'staged', mouseEvent()));
    act(() => result.current.selectFile(staged[2], 'staged', mouseEvent({ shiftKey: true })));

    expect(result.current.selectedStagedPaths).toEqual(new Set(['a.md', 'b.md', 'c.md']));
  });

  it('resolves action paths from active selected files', () => {
    const unstaged = [file('a.md'), file('b.md')];
    const { result } = renderHook(() => useVersionControlFileSelection({ stagedFiles: [], unstagedFiles: unstaged }));

    act(() => result.current.selectFile(unstaged[0], 'unstaged', mouseEvent({ ctrlKey: true })));
    act(() => result.current.selectFile(unstaged[1], 'unstaged', mouseEvent({ ctrlKey: true })));

    expect(result.current.getActionPaths(unstaged[1], 'unstaged')).toEqual(['a.md', 'b.md']);
    expect(result.current.getActionPaths(file('c.md'), 'unstaged')).toEqual(['c.md']);
  });

  it('clears one group or the full selection', () => {
    const staged = [file('staged.md')];
    const unstaged = [file('unstaged.md')];
    const { result } = renderHook(() => useVersionControlFileSelection({ stagedFiles: staged, unstagedFiles: unstaged }));

    act(() => result.current.selectFile(staged[0], 'staged', mouseEvent()));
    act(() => result.current.clearSelection('staged'));
    expect(result.current.selectedStagedPaths).toEqual(new Set());

    act(() => result.current.selectFile(unstaged[0], 'unstaged', mouseEvent()));
    act(() => result.current.clearSelection());
    expect(result.current.selectedUnstagedPaths).toEqual(new Set());
    expect(result.current.selectedUnstagedPath).toBeNull();
  });
});
