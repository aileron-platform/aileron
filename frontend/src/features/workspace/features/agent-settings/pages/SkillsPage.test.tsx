import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SkillsPage from './SkillsPage';
import type { AgentSelectedFile } from '../types';

const { useWorkspaceMock, getSkillMock, updateSkillMock } = vi.hoisted(() => ({
  useWorkspaceMock: vi.fn(),
  getSkillMock: vi.fn(),
  updateSkillMock: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => useWorkspaceMock(),
}));

vi.mock('../services/agentSettingsApi', () => ({
  createAgentSettingsApi: () => ({
    getSkill: getSkillMock,
    updateSkill: updateSkillMock,
  }),
}));

vi.mock('@/shared/components/file-workbench/viewer-entry', () => ({
  FileViewerWorkbench: ({
    tabs,
    activeTabId,
    onTabsChange,
    onActiveTabChange,
    adapter,
  }: {
    tabs: { id: string; name: string; content: string; originalContent: string; isModified: boolean }[];
    activeTabId: string | null;
    onTabsChange: (next: { id: string; name: string; content: string; originalContent: string; isModified: boolean }[]) => void;
    onActiveTabChange: (next: string | null) => void;
    adapter: { saveFile?: (path: string, content: string) => Promise<void> };
  }) => {
    const activeTab = tabs.find(tab => tab.id === activeTabId) ?? null;
    return (
      <div>
        <div data-testid="tab-list">
          {tabs.map(tab => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={tab.id === activeTabId}
              onClick={() => onActiveTabChange(tab.id)}
            >
              {tab.name}
            </button>
          ))}
        </div>
        <div data-testid="tab-count">{tabs.length}</div>
        {activeTab && (
          <>
            <textarea
              aria-label={activeTab.id}
              value={activeTab.content}
              onChange={(event) => onTabsChange(tabs.map(tab => (
                tab.id === activeTab.id
                  ? { ...tab, content: event.target.value, isModified: event.target.value !== tab.originalContent }
                  : tab
              )))}
            />
            <button
              type="button"
              aria-label="save"
              onClick={() => void adapter.saveFile?.(activeTab.id, activeTab.content)}
            >
              save
            </button>
            <button
              type="button"
              aria-label={`close-${activeTab.id}`}
              onClick={() => onTabsChange(tabs.filter(tab => tab.id !== activeTab.id))}
            >
              close
            </button>
          </>
        )}
      </div>
    );
  },
  useManagedDocumentWorkbenchTabs: (options: {
    adapter: {
      getKey: (document: { path: string }) => string;
      getName: (document: { path: string }) => string;
      readFile: (document: { path: string }) => Promise<string>;
      saveFile?: (document: { path: string }, content: string) => Promise<void>;
      isWritable?: (document: { path: string }) => boolean;
    };
  }) => {
    const [documents, setDocuments] = React.useState<Array<{ path: string }>>([]);
    const [activeTabId, setActiveTabId] = React.useState<string | null>(null);
    const [contents, setContents] = React.useState<Record<string, string>>({});
    const [originalContents, setOriginalContents] = React.useState<Record<string, string>>({});

    const getDocumentByPath = React.useCallback((path: string) => (
      documents.find(document => options.adapter.getKey(document) === path)
    ), [documents, options.adapter]);

    const openDocument = React.useCallback((document: { path: string }) => {
      const path = options.adapter.getKey(document);
      setDocuments(prev => (prev.some(item => options.adapter.getKey(item) === path) ? prev : [...prev, document]));
      setActiveTabId(path);
      if (contents[path] === undefined) {
        void options.adapter.readFile(document).then(content => {
          setContents(prev => ({ ...prev, [path]: content }));
          setOriginalContents(prev => ({ ...prev, [path]: content }));
        });
      }
    }, [contents, options.adapter]);

    const applyTabsChange = React.useCallback((nextTabs: Array<{ id: string; name: string; content: string; originalContent: string }>) => {
      const nextPaths = new Set(nextTabs.map(tab => tab.id));
      setDocuments(prev => prev.filter(document => nextPaths.has(options.adapter.getKey(document))));
      setContents(Object.fromEntries(nextTabs.map(tab => [tab.id, tab.content])));
      setOriginalContents(Object.fromEntries(nextTabs.map(tab => [tab.id, tab.originalContent])));
      setActiveTabId(current => (current && nextPaths.has(current) ? current : nextTabs.at(-1)?.id ?? null));
    }, [options.adapter]);

    const tabs = documents.map(document => {
      const path = options.adapter.getKey(document);
      const name = options.adapter.getName(document);
      const content = contents[path] ?? '';
      const originalContent = originalContents[path] ?? '';
      return {
        id: path,
        path,
        name,
        content,
        originalContent,
        isModified: content !== originalContent,
      };
    });

    const adapter = {
      readFile: async (path: string) => contents[path] ?? '',
      saveFile: options.adapter.saveFile
        ? async (path: string, content: string) => {
            const document = getDocumentByPath(path);
            if (!document) return;
            await options.adapter.saveFile(document, content);
            setContents(prev => ({ ...prev, [path]: content }));
            setOriginalContents(prev => ({ ...prev, [path]: content }));
          }
        : undefined,
    };

    return {
      tabs,
      activeTabId,
      activeTab: tabs.find(tab => tab.id === activeTabId) ?? null,
      contents,
      openDocument,
      setActiveTabId,
      applyTabsChange,
      adapter,
      isPathWritable: options.adapter.isWritable ?? (() => true),
      isSavingActive: false,
      canSaveActive: true,
      getDocumentByPath,
    };
  },
}));

const buildFile = (path: string, scope: AgentSelectedFile['scope'] = 'project'): AgentSelectedFile => ({
  path,
  scope,
});

describe('SkillsPage multi-tab', () => {
  beforeEach(() => {
    useWorkspaceMock.mockReset();
    getSkillMock.mockReset();
    updateSkillMock.mockReset();
    useWorkspaceMock.mockReturnValue({
      workspaceRuntime: {
        workspaceId: 'ws-1',
        runtimeBaseUrl: 'http://runtime.local',
      },
    });
    getSkillMock.mockImplementation((_baseUrl: string, _ws: string, path: string) => Promise.resolve({ content: `content of ${path}` }));
    updateSkillMock.mockResolvedValue({ success: true });
  });

  it('opens a new tab when selectedFile points to an untracked file', async () => {
    const { rerender } = render(<SkillsPage selectedFile={buildFile('skills/a.md')} />);

    await waitFor(() => {
      expect(screen.getByTestId('tab-count')).toHaveTextContent('1');
    });
    expect(getSkillMock).toHaveBeenCalledTimes(1);

    rerender(<SkillsPage selectedFile={buildFile('skills/b.md')} />);

    await waitFor(() => {
      expect(screen.getByTestId('tab-count')).toHaveTextContent('2');
    });
    expect(getSkillMock).toHaveBeenCalledTimes(2);
    expect(screen.getByRole('tab', { name: 'b.md' })).toHaveAttribute('aria-selected', 'true');
  });

  it('reactivates an existing tab without reloading content', async () => {
    const { rerender } = render(<SkillsPage selectedFile={buildFile('skills/a.md')} />);

    await waitFor(() => {
      expect(screen.getByTestId('tab-count')).toHaveTextContent('1');
    });

    rerender(<SkillsPage selectedFile={buildFile('skills/b.md')} />);
    await waitFor(() => {
      expect(screen.getByTestId('tab-count')).toHaveTextContent('2');
    });

    rerender(<SkillsPage selectedFile={buildFile('skills/a.md')} />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'a.md' })).toHaveAttribute('aria-selected', 'true');
    });
    expect(getSkillMock).toHaveBeenCalledTimes(2);
  });

  it('saves through the project skill endpoint and clears modified state', async () => {
    render(<SkillsPage selectedFile={buildFile('skills/a.md')} />);

    await waitFor(() => {
      expect(screen.getByLabelText('project||skills/a.md')).toBeInTheDocument();
    });

    const textarea = screen.getByLabelText('project||skills/a.md');
    fireEvent.change(textarea, { target: { value: 'updated content' } });
    fireEvent.click(screen.getByLabelText('save'));

    await waitFor(() => {
      expect(updateSkillMock).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        'skills/a.md',
        { content: 'updated content' },
        'project',
      );
    });
  });

  it('closes a tab and removes it from the open file list', async () => {
    const { rerender } = render(<SkillsPage selectedFile={buildFile('skills/a.md')} />);
    await waitFor(() => expect(screen.getByTestId('tab-count')).toHaveTextContent('1'));

    rerender(<SkillsPage selectedFile={buildFile('skills/b.md')} />);
    await waitFor(() => expect(screen.getByTestId('tab-count')).toHaveTextContent('2'));

    fireEvent.click(screen.getByLabelText('close-project||skills/b.md'));

    await waitFor(() => expect(screen.getByTestId('tab-count')).toHaveTextContent('1'));
    expect(screen.queryByRole('tab', { name: 'b.md' })).not.toBeInTheDocument();
  });
});
