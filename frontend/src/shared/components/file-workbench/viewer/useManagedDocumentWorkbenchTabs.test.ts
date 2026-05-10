import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ManagedDocumentWorkbenchAdapter } from './useManagedDocumentWorkbenchTabs';
import { useManagedDocumentWorkbenchTabs } from './useManagedDocumentWorkbenchTabs';

type TestDocument = {
  path: string;
  name: string;
  content: string;
};

const buildDocument = (path: string, content: string): TestDocument => ({
  path,
  name: path.split('/').pop() || path,
  content,
});

describe('useManagedDocumentWorkbenchTabs', () => {
  it('opens a document, loads content, and keeps the tab deduplicated', async () => {
    const readFile = vi.fn(async (document: TestDocument) => document.content);
    const adapter: ManagedDocumentWorkbenchAdapter<TestDocument> = {
      getKey: document => document.path,
      getName: document => document.name,
      readFile,
    };

    const { result } = renderHook(() => useManagedDocumentWorkbenchTabs({ adapter }));

    act(() => {
      result.current.openDocument(buildDocument('/skills/review-checklist/SKILL.md', '# Review'));
      result.current.openDocument(buildDocument('/skills/review-checklist/SKILL.md', '# Review'));
    });

    await waitFor(() => {
      expect(result.current.tabs).toHaveLength(1);
      expect(result.current.tabs[0]).toMatchObject({
        id: '/skills/review-checklist/SKILL.md',
        name: 'SKILL.md',
        content: '# Review',
        originalContent: '# Review',
        isModified: false,
      });
    });

    expect(result.current.activeTabId).toBe('/skills/review-checklist/SKILL.md');
    expect(readFile).toHaveBeenCalledTimes(1);
  });

  it('persists saved content and removes deleted paths from state', async () => {
    const saveFile = vi.fn(async () => undefined);
    const adapter: ManagedDocumentWorkbenchAdapter<TestDocument> = {
      getKey: document => document.path,
      getName: document => document.name,
      readFile: async (document) => document.content,
      saveFile,
    };

    const { result } = renderHook(() => useManagedDocumentWorkbenchTabs({ adapter }));

    act(() => {
      result.current.openDocument(buildDocument('/skills/review-checklist/SKILL.md', '# Review'));
    });

    await waitFor(() => {
      expect(result.current.tabs).toHaveLength(1);
    });

    await act(async () => {
      await result.current.adapter.saveFile?.('/skills/review-checklist/SKILL.md', '# Updated review');
    });

    expect(saveFile).toHaveBeenCalledWith(
      expect.objectContaining({ path: '/skills/review-checklist/SKILL.md' }),
      '# Updated review',
    );
    expect(result.current.tabs[0]).toMatchObject({
      content: '# Updated review',
      originalContent: '# Updated review',
      isModified: false,
    });

    act(() => {
      result.current.removePaths(['/skills/review-checklist']);
    });

    expect(result.current.tabs).toHaveLength(0);
    expect(result.current.activeTabId).toBeNull();
    expect(result.current.getDocumentByPath('/skills/review-checklist/SKILL.md')).toBeUndefined();
  });
});
