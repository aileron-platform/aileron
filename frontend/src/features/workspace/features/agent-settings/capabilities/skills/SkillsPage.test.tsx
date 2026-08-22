import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SkillsPage from './SkillsPage';
import type { AgentSelectedFile } from '../../model/documents';

interface TestWorkbenchState {
  documents: AgentSelectedFile[];
  activeTabId: string | null;
  contents: Record<string, string>;
  originalContents: Record<string, string>;
}

const {
  useWorkspaceMock,
  createAgentSettingsApiMock,
  getSkillMock,
  getSkillBlobMock,
  getCodexFileMock,
  getCodexFileBlobMock,
  updateSkillMock,
  updateCodexFileMock,
} = vi.hoisted(() => ({
  useWorkspaceMock: vi.fn(),
  createAgentSettingsApiMock: vi.fn(),
  getSkillMock: vi.fn(),
  getSkillBlobMock: vi.fn(),
  getCodexFileMock: vi.fn(),
  getCodexFileBlobMock: vi.fn(),
  updateSkillMock: vi.fn(),
  updateCodexFileMock: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => useWorkspaceMock(),
}));

vi.mock('../../api/agentSettingsApi', () => ({
  createAgentSettingsApi: createAgentSettingsApiMock,
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
    adapter: {
      readBlob?: (path: string) => Promise<Blob>;
      saveFile?: (path: string, content: string) => Promise<void>;
    };
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
              aria-label={`preview-${activeTab.id}`}
              onClick={() => void adapter.readBlob?.(activeTab.id)}
            >
              preview
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
      getKey: (document: AgentSelectedFile) => string;
      getName: (document: AgentSelectedFile) => string;
      readFile: (document: AgentSelectedFile) => Promise<string>;
      readBlob?: (document: AgentSelectedFile) => Promise<Blob>;
      saveFile?: (document: AgentSelectedFile, content: string) => Promise<void>;
      isWritable?: (document: AgentSelectedFile) => boolean;
    };
    initialState?: TestWorkbenchState;
    onStateChange?: (state: TestWorkbenchState) => void;
  }) => {
    const onStateChange = options.onStateChange;
    const [documents, setDocuments] = React.useState<AgentSelectedFile[]>(() => [
      ...(options.initialState?.documents ?? []),
    ]);
    const [activeTabId, setActiveTabId] = React.useState<string | null>(() => (
      options.initialState?.activeTabId ?? null
    ));
    const [contents, setContents] = React.useState<Record<string, string>>(() => ({
      ...(options.initialState?.contents ?? {}),
    }));
    const [originalContents, setOriginalContents] = React.useState<Record<string, string>>(() => ({
      ...(options.initialState?.originalContents ?? {}),
    }));

    React.useLayoutEffect(() => {
      onStateChange?.({
        documents,
        activeTabId,
        contents,
        originalContents,
      });
    }, [activeTabId, contents, documents, onStateChange, originalContents]);

    const getDocumentByPath = React.useCallback((path: string) => (
      documents.find(document => options.adapter.getKey(document) === path)
    ), [documents, options.adapter]);

    const openDocument = React.useCallback((document: AgentSelectedFile) => {
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
      readBlob: options.adapter.readBlob
        ? async (path: string) => {
            const document = getDocumentByPath(path);
            if (!document) throw new Error('Managed document not found');
            return options.adapter.readBlob!(document);
          }
        : undefined,
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

const buildFile = (
  path: string,
  scope: AgentSelectedFile['scope'] = 'project',
  pluginId?: string,
): AgentSelectedFile => ({
  path,
  scope,
  pluginId,
});

describe('SkillsPage multi-tab', () => {
  beforeEach(() => {
    useWorkspaceMock.mockReset();
    createAgentSettingsApiMock.mockReset();
    getSkillMock.mockReset();
    getSkillBlobMock.mockReset();
    getCodexFileMock.mockReset();
    getCodexFileBlobMock.mockReset();
    updateSkillMock.mockReset();
    updateCodexFileMock.mockReset();
    createAgentSettingsApiMock.mockImplementation(() => ({
      getSkill: getSkillMock,
      getSkillBlob: getSkillBlobMock,
      getCodexFile: getCodexFileMock,
      getCodexFileBlob: getCodexFileBlobMock,
      updateSkill: updateSkillMock,
      updateCodexFile: updateCodexFileMock,
    }));
    useWorkspaceMock.mockReturnValue({
      workspaceRuntime: {
        workspaceId: 'ws-1',
        runtimeBaseUrl: 'http://runtime.local',
      },
    });
    getSkillMock.mockImplementation((_baseUrl: string, _ws: string, path: string) => Promise.resolve({ content: `content of ${path}` }));
    getSkillBlobMock.mockResolvedValue(new Blob(['image'], { type: 'image/png' }));
    getCodexFileMock.mockImplementation((_baseUrl: string, _ws: string, _resource: string, _scope: string, path: string) => (
      Promise.resolve({ content: `content of ${path}` })
    ));
    getCodexFileBlobMock.mockResolvedValue(new Blob(['plugin image'], { type: 'image/png' }));
    updateSkillMock.mockResolvedValue({ success: true });
    updateCodexFileMock.mockResolvedValue({ content: 'saved' });
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

  it('loads project binary previews with the original scoped document path', async () => {
    render(<SkillsPage selectedFile={buildFile('review assets/logo.png')} />);

    const preview = await screen.findByLabelText('preview-project||review assets/logo.png');
    fireEvent.click(preview);

    await waitFor(() => {
      expect(getSkillBlobMock).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        'review assets/logo.png',
        'project',
      );
    });
    expect(getSkillBlobMock).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      'project||review assets/logo.png',
      expect.anything(),
    );
  });

  it('uses generic raw Skills content for Codex project previews', async () => {
    render(
      <SkillsPage
        apiPrefix="codex"
        selectedFile={buildFile('review/assets/logo.png')}
      />,
    );

    fireEvent.click(await screen.findByLabelText('preview-project||review/assets/logo.png'));

    await waitFor(() => {
      expect(getSkillBlobMock).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        'review/assets/logo.png',
        'project',
      );
    });
    expect(getCodexFileBlobMock).not.toHaveBeenCalled();
  });

  it('preserves Codex plugin identity when loading a binary preview', async () => {
    render(
      <SkillsPage
        apiPrefix="codex"
        selectedFile={buildFile('review/SKILL.md', 'plugin', 'demo tools@local')}
      />,
    );

    fireEvent.click(await screen.findByLabelText('preview-plugin|demo tools@local|review/SKILL.md'));

    await waitFor(() => {
      expect(getCodexFileBlobMock).toHaveBeenCalledWith(
        'http://runtime.local',
        'ws-1',
        'skills',
        'plugin',
        'review/SKILL.md',
        'demo tools@local',
      );
    });
    expect(getSkillBlobMock).not.toHaveBeenCalled();
  });

  it('keeps drafts provider-scoped and clears them when workspace identity changes', async () => {
    const selectedFile = buildFile('shared/logo.png');
    let workspaceRuntime = {
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
    };
    useWorkspaceMock.mockImplementation(() => ({ workspaceRuntime }));

    const claudeRead = vi.fn((_baseUrl: string, workspaceId: string) => (
      Promise.resolve({ content: `claude content for ${workspaceId}` })
    ));
    const claudeSave = vi.fn().mockResolvedValue({ success: true });
    const openCodeRead = vi.fn((_baseUrl: string, workspaceId: string) => (
      Promise.resolve({ content: `opencode content for ${workspaceId}` })
    ));
    const openCodeSave = vi.fn().mockResolvedValue({ success: true });
    const codexRead = vi.fn((_baseUrl: string, workspaceId: string) => (
      Promise.resolve({ content: `codex content for ${workspaceId}` })
    ));
    const codexSave = vi.fn().mockResolvedValue({ content: 'codex content' });
    createAgentSettingsApiMock.mockImplementation((apiPrefix: string) => {
      if (apiPrefix === 'codex') {
        return {
          getCodexFile: codexRead,
          getSkillBlob: getSkillBlobMock,
          updateCodexFile: codexSave,
        };
      }
      if (apiPrefix === 'opencode') {
        return {
          getSkill: openCodeRead,
          getSkillBlob: getSkillBlobMock,
          updateSkill: openCodeSave,
        };
      }
      return {
        getSkill: claudeRead,
        getSkillBlob: getSkillBlobMock,
        updateSkill: claudeSave,
      };
    });

    const view = render(
      <SkillsPage
        apiPrefix="claude-code"
        selectedFile={selectedFile}
      />,
    );

    const editor = await screen.findByDisplayValue('claude content for ws-1');
    fireEvent.change(editor, { target: { value: 'unsaved claude content' } });

    view.rerender(
      <SkillsPage
        apiPrefix="opencode"
        selectedFile={selectedFile}
      />,
    );

    expect(await screen.findByDisplayValue('opencode content for ws-1')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('unsaved claude content')).not.toBeInTheDocument();
    expect(claudeSave).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('save'));

    await waitFor(() => expect(openCodeSave).toHaveBeenCalledWith(
      'http://runtime.local',
      'ws-1',
      'shared/logo.png',
      { content: 'opencode content for ws-1' },
      'project',
    ));
    expect(claudeSave).not.toHaveBeenCalled();
    expect(codexSave).not.toHaveBeenCalled();

    view.rerender(
      <SkillsPage
        apiPrefix="codex"
        selectedFile={selectedFile}
      />,
    );

    expect(await screen.findByDisplayValue('codex content for ws-1')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('unsaved claude content')).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('save'));

    await waitFor(() => expect(codexSave).toHaveBeenCalledWith(
      'http://runtime.local',
      'ws-1',
      'skills',
      'project',
      'shared/logo.png',
      'codex content for ws-1',
    ));
    expect(claudeSave).not.toHaveBeenCalled();
    expect(openCodeSave).toHaveBeenCalledTimes(1);

    view.rerender(
      <SkillsPage
        apiPrefix="claude-code"
        selectedFile={selectedFile}
      />,
    );

    expect(await screen.findByDisplayValue('unsaved claude content')).toBeInTheDocument();
    expect(claudeRead).toHaveBeenCalledTimes(1);
    expect(claudeSave).not.toHaveBeenCalled();

    workspaceRuntime = {
      workspaceId: 'ws-2',
      runtimeBaseUrl: 'http://runtime-2.local',
    };
    view.rerender(
      <SkillsPage
        apiPrefix="claude-code"
        selectedFile={selectedFile}
      />,
    );

    expect(await screen.findByDisplayValue('claude content for ws-2')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('unsaved claude content')).not.toBeInTheDocument();
    expect(claudeRead).toHaveBeenLastCalledWith(
      'http://runtime-2.local',
      'ws-2',
      'shared/logo.png',
      'project',
    );

    workspaceRuntime = {
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
    };
    view.rerender(
      <SkillsPage
        apiPrefix="claude-code"
        selectedFile={selectedFile}
      />,
    );

    expect(await screen.findByDisplayValue('claude content for ws-1')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('unsaved claude content')).not.toBeInTheDocument();
    expect(claudeRead).toHaveBeenCalledTimes(3);
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
