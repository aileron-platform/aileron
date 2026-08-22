import { createElement, startTransition, Suspense, type PropsWithChildren } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ManagedDocumentWorkbenchAdapter } from './useManagedDocumentWorkbenchTabs';
import { useManagedDocumentWorkbenchTabs } from './useManagedDocumentWorkbenchTabs';

type TestDocument = {
  path: string;
  name: string;
  content: string;
  scope?: 'project' | 'plugin';
  pluginId?: string;
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

  it('resolves blob reads back to the scoped plugin document instead of forwarding the tab key', async () => {
    const readBlob = vi.fn(async () => new Blob(['image'], { type: 'image/png' }));
    const projectDocument: TestDocument = {
      ...buildDocument('assets/logo.png', ''),
      scope: 'project',
    };
    const pluginDocument: TestDocument = {
      ...buildDocument('assets/logo.png', ''),
      scope: 'plugin',
      pluginId: 'review-tools@official',
    };
    const getKey = (document: TestDocument) => (
      `${document.scope}|${document.pluginId ?? ''}|${document.path}`
    );
    const adapter: ManagedDocumentWorkbenchAdapter<TestDocument> = {
      getKey,
      getName: document => document.name,
      readFile: async document => document.content,
      readBlob,
    };

    const { result } = renderHook(() => useManagedDocumentWorkbenchTabs({ adapter }));

    act(() => {
      result.current.openDocument(projectDocument);
      result.current.openDocument(pluginDocument);
    });

    await waitFor(() => {
      expect(result.current.tabs).toHaveLength(2);
    });

    const pluginTabKey = getKey(pluginDocument);
    let blob: Blob | undefined;
    await act(async () => {
      blob = await result.current.adapter.readBlob?.(pluginTabKey);
    });

    expect(blob).toBeInstanceOf(Blob);
    expect(readBlob).toHaveBeenCalledTimes(1);
    expect(readBlob).toHaveBeenCalledWith(pluginDocument);
    expect(readBlob).not.toHaveBeenCalledWith(pluginTabKey);
  });

  it('opens an image through the blob reader without scheduling a text read', async () => {
    const imageDocument = buildDocument('/skills/review-checklist/assets/logo.png', 'binary image');
    const imageBlob = new Blob(['image'], { type: 'image/png' });
    const readFile = vi.fn(async (document: TestDocument) => document.content);
    const readBlob = vi.fn(async () => imageBlob);
    const adapter: ManagedDocumentWorkbenchAdapter<TestDocument> = {
      getKey: document => document.path,
      getName: document => document.name,
      readFile,
      readBlob,
    };

    const { result } = renderHook(() => useManagedDocumentWorkbenchTabs({ adapter }));

    act(() => {
      result.current.openDocument(imageDocument);
      result.current.openDocument(imageDocument);
    });

    await waitFor(() => {
      expect(result.current.tabs).toEqual([{
        id: imageDocument.path,
        path: imageDocument.path,
        name: imageDocument.name,
        content: '',
        originalContent: '',
        isModified: false,
        isLoading: false,
      }]);
    });

    expect(result.current.activeTabId).toBe(imageDocument.path);
    expect(result.current.getDocumentByPath(imageDocument.path)).toBe(imageDocument);
    expect(readFile).not.toHaveBeenCalled();

    let blob: Blob | undefined;
    await act(async () => {
      blob = await result.current.adapter.readBlob?.(imageDocument.path);
    });

    expect(blob).toBe(imageBlob);
    expect(readBlob).toHaveBeenCalledTimes(1);
    expect(readBlob).toHaveBeenCalledWith(imageDocument);
    expect(readFile).not.toHaveBeenCalled();
    expect(result.current.tabs).toEqual([{
      id: imageDocument.path,
      path: imageDocument.path,
      name: imageDocument.name,
      content: '',
      originalContent: '',
      isModified: false,
      isLoading: false,
    }]);
    expect(result.current.activeTabId).toBe(imageDocument.path);
  });

  it('restores a draft snapshot without reading and publishes committed changes', () => {
    const document = buildDocument('/skills/review-checklist/SKILL.md', '# Server copy');
    const readFile = vi.fn(async () => document.content);
    const onStateChange = vi.fn();
    const adapter: ManagedDocumentWorkbenchAdapter<TestDocument> = {
      getKey: item => item.path,
      getName: item => item.name,
      readFile,
    };

    const { result } = renderHook(() => useManagedDocumentWorkbenchTabs({
      adapter,
      initialState: {
        documents: [document],
        activeTabId: document.path,
        contents: { [document.path]: '# Unsaved draft' },
        originalContents: { [document.path]: '# Server copy' },
      },
      onStateChange,
    }));

    expect(readFile).not.toHaveBeenCalled();
    expect(result.current.tabs[0]).toMatchObject({
      id: document.path,
      content: '# Unsaved draft',
      originalContent: '# Server copy',
      isModified: true,
    });
    expect(onStateChange).toHaveBeenLastCalledWith(expect.objectContaining({
      documents: [document],
      activeTabId: document.path,
      contents: { [document.path]: '# Unsaved draft' },
    }));

    act(() => {
      result.current.applyTabsChange([{ ...result.current.tabs[0], content: '# Newer draft' }]);
    });

    expect(onStateChange).toHaveBeenLastCalledWith(expect.objectContaining({
      contents: { [document.path]: '# Newer draft' },
      originalContents: { [document.path]: '# Server copy' },
    }));
  });

  it('keeps document callbacks on committed state while a removal render is suspended', async () => {
    const document = buildDocument('/skills/committed/SKILL.md', '# Committed');
    const adapter: ManagedDocumentWorkbenchAdapter<TestDocument> = {
      getKey: item => item.path,
      getName: item => item.name,
      readFile: async item => item.content,
    };
    let shouldSuspendRemoval = false;
    let releaseSuspension = () => undefined;
    const suspendedRemoval = new Promise<void>((resolve) => {
      releaseSuspension = resolve;
    });
    const suspendedRender = vi.fn();
    const wrapper = ({ children }: PropsWithChildren) => createElement(
      Suspense,
      { fallback: null },
      children,
    );

    const { result } = renderHook(() => {
      const workbench = useManagedDocumentWorkbenchTabs({
        adapter,
        initialState: {
          documents: [document],
          activeTabId: document.path,
          contents: { [document.path]: document.content },
          originalContents: { [document.path]: document.content },
        },
      });
      if (shouldSuspendRemoval && workbench.tabs.length === 0) {
        suspendedRender();
        throw suspendedRemoval;
      }
      return workbench;
    }, { wrapper });
    const getCommittedDocument = result.current.getDocumentByPath;

    expect(getCommittedDocument(document.path)).toBe(document);

    shouldSuspendRemoval = true;
    act(() => {
      startTransition(() => {
        result.current.removePaths([document.path]);
      });
    });

    await waitFor(() => expect(suspendedRender).toHaveBeenCalled());
    expect(getCommittedDocument(document.path)).toBe(document);

    await act(async () => {
      shouldSuspendRemoval = false;
      releaseSuspension();
      await suspendedRemoval;
    });

    await waitFor(() => expect(getCommittedDocument(document.path)).toBeUndefined());
  });

  it('preserves incoming tab order when applying document-backed tabs change', async () => {
    const adapter: ManagedDocumentWorkbenchAdapter<TestDocument> = {
      getKey: document => document.path,
      getName: document => document.name,
      readFile: async (document) => document.content,
    };

    const { result } = renderHook(() => useManagedDocumentWorkbenchTabs({ adapter }));

    act(() => {
      result.current.openDocument(buildDocument('/skills/a.md', 'A'));
      result.current.openDocument(buildDocument('/skills/b.md', 'B'));
      result.current.openDocument(buildDocument('/skills/c.md', 'C'));
    });

    await waitFor(() => {
      expect(result.current.tabs.map(tab => tab.id)).toEqual([
        '/skills/a.md',
        '/skills/b.md',
        '/skills/c.md',
      ]);
    });

    act(() => {
      result.current.applyTabsChange([
        { ...result.current.tabs[2], content: 'C updated', originalContent: 'C' },
        result.current.tabs[0],
        result.current.tabs[1],
      ]);
    });

    expect(result.current.tabs.map(tab => tab.id)).toEqual([
      '/skills/c.md',
      '/skills/a.md',
      '/skills/b.md',
    ]);
    expect(result.current.tabs[0]).toMatchObject({
      id: '/skills/c.md',
      content: 'C updated',
      originalContent: 'C',
      isModified: true,
    });
    expect(result.current.activeTabId).toBe('/skills/c.md');
  });
});
