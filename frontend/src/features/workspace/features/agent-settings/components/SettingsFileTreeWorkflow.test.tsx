import React from 'react';
import { File } from 'lucide-react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import {
  createFileTreeResourceIdentity,
  type FileTreeDataAdapter,
} from '@/shared/components/file-workbench';
import { SettingsFileTreeWorkflow } from './SettingsFileTreeWorkflow';

const workflowSpy = vi.fn();

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/file-workbench', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/components/file-workbench')>();
  return {
    ...actual,
    FileManagementSidebarWorkflow: (props: Record<string, unknown>) => {
      workflowSpy(props);
      const capabilities = props.capabilities as { canCreateFile?: boolean; canCreateFolder?: boolean; canUpload?: boolean } | undefined;
      return (
        <div>
          <div>shared-sidebar-workflow</div>
          <div>{String(capabilities?.canCreateFile ?? true)}</div>
          <div>{String(capabilities?.canCreateFolder ?? true)}</div>
          <div>{String(capabilities?.canUpload ?? true)}</div>
        </div>
      );
    },
    FileTreePanel: () => <div>file-tree-panel</div>,
    FileTreeContextMenu: () => null,
    FileCreateDialog: () => null,
    FileRenameDialog: () => null,
    FileDeleteDialog: () => null,
    useFileTreeContextMenu: () => [],
    useFileTreeManager: () => ({
      state: {
        isLoading: false,
        searchQuery: '',
        setSearchQuery: vi.fn(),
        clearSearch: vi.fn(),
        contextMenu: null,
        closeContextMenu: vi.fn(),
        clearSelection: vi.fn(),
        selectNodeWithModifier: vi.fn(),
        openContextMenu: vi.fn(),
      },
      operations: {
        uploadFiles: vi.fn(),
        createFile: vi.fn(),
        renameFile: vi.fn(),
        deleteFile: vi.fn(),
        moveFile: vi.fn(),
      },
      loadTree: vi.fn().mockResolvedValue(undefined),
      createFileAndOpen: vi.fn().mockResolvedValue(undefined),
      batchDeleteAndCloseTabs: vi.fn().mockResolvedValue(undefined),
    }),
  };
});

const createAdapter = (): FileTreeDataAdapter => ({
  getTree: vi.fn().mockResolvedValue([]),
  getChildren: vi.fn().mockResolvedValue([]),
  getContent: vi.fn().mockResolvedValue(''),
  create: vi.fn().mockResolvedValue({ success: true }),
  update: vi.fn().mockResolvedValue({ success: true }),
  delete: vi.fn().mockResolvedValue({ success: true }),
  batchDelete: vi.fn().mockResolvedValue({
    success: true,
    deleted: [],
    failed: [],
    total: 0,
    successCount: 0,
    failedCount: 0,
  }),
  move: vi.fn().mockResolvedValue({ success: true }),
  upload: vi.fn().mockResolvedValue([]),
  download: vi.fn().mockResolvedValue(undefined),
});

const resourceIdentity = createFileTreeResourceIdentity('agent-settings', {
  key: 'settings-workflow',
});

describe('SettingsFileTreeWorkflow', () => {
  it('renders the shared sidebar workflow and maps read-only scopes to disabled capabilities', () => {
    workflowSpy.mockClear();
    const onRefresh = vi.fn();

    render(
      <SettingsFileTreeWorkflow
        adapter={createAdapter()}
        resourceIdentity={resourceIdentity}
        scope="plugin"
        scopeOptions={[
          { value: 'project', label: 'Project' },
          { value: 'plugin', label: 'Plugin' },
        ]}
        readOnlyScopes={['plugin']}
        labels={{
          title: 'Agent files',
          scopeLabel: 'Scope',
          searchPlaceholder: 'Search files',
        }}
        icon={File}
        isCollapsed={false}
        onToggleCollapse={vi.fn()}
        onScopeChange={vi.fn()}
        onSelect={vi.fn()}
        onRefresh={onRefresh}
      />,
    );

    expect(screen.getByText('shared-sidebar-workflow')).toBeInTheDocument();
    expect(workflowSpy).toHaveBeenCalled();
    expect(workflowSpy.mock.calls.at(-1)?.[0]).toMatchObject({
      capabilities: {
        canCreateFile: false,
        canCreateFolder: false,
        canUpload: false,
      },
      loadEnabled: true,
      onCreateFile: undefined,
      onCreateFolder: undefined,
      onUpload: undefined,
      onRefresh: undefined,
      dialogs: undefined,
    });
    expect(workflowSpy.mock.calls.at(-1)?.[0]).not.toHaveProperty('autoLoad');
  });

  it('routes toolbar create dialogs through the shared interaction state', () => {
    workflowSpy.mockClear();
    const setDialogState = vi.fn();

    render(
      <SettingsFileTreeWorkflow
        adapter={createAdapter()}
        resourceIdentity={resourceIdentity}
        scope="project"
        scopeOptions={[
          { value: 'project', label: 'Project' },
          { value: 'plugin', label: 'Plugin' },
        ]}
        labels={{
          title: 'Agent files',
          scopeLabel: 'Scope',
          searchPlaceholder: 'Search files',
        }}
        icon={File}
        isCollapsed={false}
        onToggleCollapse={vi.fn()}
        onScopeChange={vi.fn()}
        onSelect={vi.fn()}
      />,
    );

    const workflowProps = workflowSpy.mock.calls.at(-1)?.[0] as {
      onCreateFile: (
        manager: { state: { contextMenu: null } },
        interactionState: { setDialogState: typeof setDialogState },
      ) => void;
      onCreateFolder: (
        manager: { state: { contextMenu: null } },
        interactionState: { setDialogState: typeof setDialogState },
      ) => void;
    };
    const manager = { state: { contextMenu: null } };
    const interactionState = { setDialogState };

    workflowProps.onCreateFile(manager, interactionState);
    workflowProps.onCreateFolder(manager, interactionState);

    expect(setDialogState).toHaveBeenNthCalledWith(1, { type: 'create-file', parentPath: '/' });
    expect(setDialogState).toHaveBeenNthCalledWith(2, { type: 'create-folder', parentPath: '/' });
  });
});
