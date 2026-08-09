import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MouseEvent, ReactNode } from 'react';
import { KnowledgeBaseVersionControlTab } from './KnowledgeBaseVersionControlTab';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';

const apiMocks = vi.hoisted(() => ({
  repository: vi.fn(),
  initializeRepository: vi.fn(),
  cloneRepository: vi.fn(),
  updateLfsPatterns: vi.fn(),
  changes: vi.fn(),
  status: vi.fn(),
  branches: vi.fn(),
  commits: vi.fn(),
  commitFiles: vi.fn(),
  diff: vi.fn(),
  blob: vi.fn(),
  setRemote: vi.fn(),
}));

// The session owns the API boundary. Route each request to a focused fixture so
// component tests exercise only the public changes/history/remote capabilities.
const { sharedClient, MockApiError } = vi.hoisted(() => {
  class MockApiError extends Error {
    status: number;

    errorCode?: string;

    messageKey?: string;

    stale?: boolean;

    canForceUnlock?: boolean;

    constructor(
      message: string,
      status: number,
      errorCode?: string,
      metadata?: { messageKey?: string; stale?: boolean; canForceUnlock?: boolean },
    ) {
      super(message);
      this.status = status;
      this.errorCode = errorCode;
      this.messageKey = metadata?.messageKey;
      this.stale = metadata?.stale;
      this.canForceUnlock = metadata?.canForceUnlock;
    }
  }
  return {
    sharedClient: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      patch: vi.fn(),
    },
    MockApiError,
  };
});

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => sharedClient),
  ApiError: MockApiError,
}));

const toastMock = vi.hoisted(() => vi.fn());
const selectionActionPathsMock = vi.hoisted(() => vi.fn((file: { path: string }) => [file.path]));
const selectionClearMock = vi.hoisted(() => vi.fn());
const selectionSelectAllMock = vi.hoisted(() => vi.fn());
const selectionSelectFileMock = vi.hoisted(() => vi.fn((
  file: { path: string },
  group: 'staged' | 'unstaged',
  onFileSelect?: (file: { path: string }, group: 'staged' | 'unstaged') => void,
) => onFileSelect?.(file, group)));
const translateMock = vi.hoisted(() => {
  const translations: Record<string, string> = {
    'knowledgeBase.versionControl.loading': '\u8f09\u5165\u7248\u672c\u63a7\u5236',
    'shared.versionControl.repositorySetup.title': '\u5c1a\u672a\u8a2d\u5b9a\u7248\u672c\u63a7\u5236',
    'shared.versionControl.repositorySetup.actions.init': '\u521d\u59cb\u5316 Git',
    'shared.versionControl.repositorySetup.actions.clone': 'Clone \u5132\u5b58\u5eab',
    'knowledgeBase.versionControl.lfs.enableAction': '\u555f\u7528 Git LFS',
    'knowledgeBase.versionControl.setup.initialCommitMessage': 'Initialize knowledge base version control',
    'knowledgeBase.versionControl.setup.permissionTitle': '\u6b0a\u9650\u4e0d\u8db3',
    'knowledgeBase.versionControl.setup.permissionDescription': '\u53ea\u6709\u64c1\u6709\u8005\u6216\u7ba1\u7406\u8005\u53ef\u4ee5\u555f\u7528 Git\u3002',
    'shared.versionControl.mode.fileChanges': '\u6a94\u6848\u8b8a\u66f4',
    'shared.versionControl.mode.commitHistory': '\u8b8a\u66f4\u8a18\u9304',
    'shared.versionControl.actions.refresh.label': '\u91cd\u65b0\u6574\u7406',
    'shared.versionControl.fileChanges.conflictsTitle': '\u885d\u7a81',
    'shared.versionControl.branchDialog.title': '\u5efa\u7acb\u5206\u652f',
    'shared.versionControl.remoteDialog.title': '\u9060\u7aef\u8a2d\u5b9a',
    'knowledgeBase.versionControl.confirmDiscardMultiple': '\u6368\u68c4 {{count}} \u500b\u6a94\u6848',
    'knowledgeBase.versionControl.toasts.operationInProgress.title': 'Git operation in progress',
    'knowledgeBase.versionControl.toasts.operationInProgress.description': 'Wait for the current Git operation to finish.',
    'shared.versionControl.conflict.title': 'Git lock conflict',
    'shared.versionControl.conflict.staleDescription': 'A stuck Git lock was detected.',
    'shared.versionControl.conflict.collisionDescription': 'Another Git operation is in progress. Please try again shortly.',
    'shared.versionControl.conflict.forceUnlock': 'Force unlock',
    'shared.versionControl.conflict.forceUnlockSuccess.title': 'Git lock cleared',
    'shared.versionControl.conflict.forceUnlockFailed.title': 'Unable to clear Git lock',
    'shared.versionControl.conflict.forceUnlockFailed.description': 'Try force unlocking again.',
  };
  return vi.fn((key: string, values?: Record<string, string | number>) => {
    let value = translations[key] ?? key;
    Object.entries(values ?? {}).forEach(([name, replacement]) => {
      value = value.replace(`{{${name}}}`, String(replacement));
    });
    return value;
  });
});

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/shared/components/version-control', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/components/version-control')>();
  return {
  ...actual,
  useVersionControlFileSelection: ({ onFileSelect }: {
    onFileSelect?: (file: { path: string }, group: 'staged' | 'unstaged') => void;
  }) => ({
    selectedStagedPath: null,
    selectedUnstagedPath: null,
    selectedStagedPaths: new Set<string>(),
    selectedUnstagedPaths: new Set<string>(),
    clearSelection: selectionClearMock,
    getActionPaths: selectionActionPathsMock,
    selectAll: selectionSelectAllMock,
    selectFile: (file: { path: string }, group: 'staged' | 'unstaged') => selectionSelectFileMock(file, group, onFileSelect),
  }),
  VersionControlChangesSkeleton: () => <div data-testid="vc-changes-skeleton" />,
  VersionControlChangesSidebar: ({ currentBranch, stagedFiles, unstagedFiles, conflictFiles = [], onCreateBranch, actions, onFileSelect, onStageToggle, onDiscard, onStageAll, onUnstageAll, isMutating }: {
    currentBranch: string;
    stagedFiles: Array<{ path: string; name: string }>;
    unstagedFiles: Array<{ path: string; name: string }>;
    conflictFiles?: Array<{ path: string; name: string }>;
    onCreateBranch?: () => void;
    actions: Array<{ id: string; onClick: () => void }>;
    onFileSelect: (file: { path: string; name: string }, group: 'staged' | 'unstaged', event: MouseEvent) => void;
    onStageToggle: (file: { path: string; name: string }, group: 'staged' | 'unstaged') => void;
    onDiscard?: (file: { path: string; name: string }) => void;
    onStageAll: () => void;
    onUnstageAll: () => void;
    isMutating?: boolean;
  }) => (
    <div data-testid="version-control-changes-sidebar" data-mutating={isMutating ? 'true' : 'false'}>
      {currentBranch}:{stagedFiles.length}:{unstagedFiles.length}:{conflictFiles.length}
      {onCreateBranch && <button type="button" onClick={onCreateBranch}>create branch</button>}
      <button type="button" onClick={onStageAll}>stage all</button>
      <button type="button" onClick={onUnstageAll}>unstage all</button>
      {stagedFiles.map((file) => (
        <div key={`staged-${file.path}`}>
          <button type="button" onClick={(event) => onFileSelect(file, 'staged', event)}>
            select staged {file.name}
          </button>
          <button type="button" onClick={() => onStageToggle(file, 'staged')}>
            unstage {file.name}
          </button>
        </div>
      ))}
      {unstagedFiles.map((file) => (
        <button key={`select-${file.path}`} type="button" onClick={(event) => onFileSelect(file, 'unstaged', event)}>
          select {file.name}
        </button>
      ))}
      {unstagedFiles.map((file) => (
        <button key={`stage-${file.path}`} type="button" onClick={() => onStageToggle(file, 'unstaged')}>
          stage {file.name}
        </button>
      ))}
      {unstagedFiles.map((file) => (
        <button key={`discard-${file.path}`} type="button" onClick={() => onDiscard?.(file)}>
          discard {file.name}
        </button>
      ))}
      {conflictFiles.length > 0 && (
        <section>
          <h3>{translateMock('shared.versionControl.fileChanges.conflictsTitle')}</h3>
          {conflictFiles.map((file) => (
            <div key={`conflict-${file.path}`}>{file.name}:{file.path}</div>
          ))}
        </section>
      )}
      {actions.map((action) => (
        <button key={action.id} type="button" onClick={action.onClick}>
          {action.id}
        </button>
      ))}
    </div>
  ),
  VersionControlHistorySidebar: ({ commits, files, onCommitSelect, onFileSelect }: {
    commits: Array<{ id: string; message: string }>;
    files: Array<{ path: string; name: string; status: string }>;
    onCommitSelect: (commit: { id: string; message: string }) => void;
    onFileSelect: (file: { path: string; name: string; status: string }) => void;
  }) => (
    <div data-testid="version-control-history-sidebar">
      {commits.map((commit) => (
        <button key={commit.id} type="button" onClick={() => onCommitSelect(commit)}>
          {commit.message}
        </button>
      ))}
      {files.map((file) => (
        <button key={file.path} type="button" onClick={() => onFileSelect(file)}>
          {file.path}
        </button>
      ))}
    </div>
  ),
  VersionControlMainDiff: ({ selectedPath, diffContent }: { selectedPath: string | null; diffContent?: string | null }) => (
    <div data-testid="version-control-main-diff">
      {selectedPath ?? 'empty'}
      <pre>{diffContent}</pre>
    </div>
  ),
  VersionControlCreateBranchDialog: ({ open, onCreate }: {
    open: boolean;
    onCreate: (payload: { branch: string; startPoint?: string }) => void;
  }) => open ? (
    <div role="dialog" aria-label="\u5efa\u7acb\u5206\u652f">
      <button type="button" onClick={() => onCreate({ branch: 'feature/docs', startPoint: 'main' })}>
        confirm branch
      </button>
    </div>
  ) : null,
  VersionControlRenameBranchDialog: () => null,
  VersionControlDeleteBranchDialog: () => null,
  VersionControlPublishBranchDialog: () => null,
  VersionControlDiscardDialog: ({ open, paths, onConfirm }: {
    open: boolean;
    paths: string[];
    onConfirm: (paths: string[]) => Promise<void>;
  }) => open ? (
    <button type="button" onClick={() => void onConfirm(paths)}>confirm discard</button>
  ) : null,
  VersionControlAbortConflictDialog: () => null,
  VersionControlRevertCommitDialog: () => null,
  VersionControlRemoteSettingsDialog: ({ open, onSaveRemoteUrl, initializedSlot }: {
    open: boolean;
    onSaveRemoteUrl: (remoteUrl: string) => void;
    initializedSlot?: ReactNode;
  }) => open ? (
    <div role="dialog" aria-label="\u9060\u7aef\u8a2d\u5b9a">
      <button type="button" onClick={() => onSaveRemoteUrl('git@example.com:team/knowledge.git')}>
        save remote
      </button>
      {initializedSlot}
    </div>
  ) : null,
  VersionControlDialogHost: ({ controller, onSaveRemoteUrl, onDiscard, lfs }: {
    controller: {
      dialogs: {
        remoteSettingsOpen: boolean;
        lfsSettingsOpen: boolean;
        discardPaths: string[];
      };
    };
    onSaveRemoteUrl?: (remoteUrl: string) => void;
    onDiscard?: (paths: string[]) => Promise<void>;
    lfs?: { onSavePatterns: (patterns: string[]) => Promise<unknown> };
  }) => (
    <>
      {controller.dialogs.remoteSettingsOpen && onSaveRemoteUrl ? (
        <div role="dialog" aria-label="\u9060\u7aef\u8a2d\u5b9a">
          <button type="button" onClick={() => onSaveRemoteUrl('git@example.com:team/knowledge.git')}>
            save remote
          </button>
        </div>
      ) : null}
      {controller.dialogs.discardPaths.length > 0 && onDiscard ? (
        <button type="button" onClick={() => void onDiscard(controller.dialogs.discardPaths)}>
          confirm discard
        </button>
      ) : null}
      {controller.dialogs.lfsSettingsOpen && lfs ? (
        <button type="button" onClick={() => void lfs.onSavePatterns(['*.bin'])}>
          save lfs patterns
        </button>
      ) : null}
    </>
  ),
  VersionControlRepositorySetup: ({
    capability,
    remoteEffects,
    onSetupComplete,
  }: {
    capability: { canMutate: boolean };
    remoteEffects: {
      initialize: (defaultBranch: string) => Promise<unknown>;
      clone: (remoteUrl: string, branch?: string) => Promise<unknown>;
    };
    onSetupComplete?: (kind: 'initialize' | 'clone') => void | Promise<void>;
  }) => (
    <div data-testid="version-control-repository-setup">
      <div>{translateMock('shared.versionControl.repositorySetup.title')}</div>
      {capability.canMutate && (
        <>
          <button
            type="button"
            onClick={() => void remoteEffects.initialize('main').then(() => onSetupComplete?.('initialize'))}
          >
            {translateMock('shared.versionControl.repositorySetup.actions.init')}
          </button>
          <button
            type="button"
            onClick={() => void remoteEffects.clone(
              'git@example.com:team/knowledge.git',
              'develop',
            ).then(() => onSetupComplete?.('clone'))}
          >
            {translateMock('shared.versionControl.repositorySetup.actions.clone')}
          </button>
        </>
      )}
    </div>
  ),
  };
});

const createQueryClient = () => new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
});

const createWrapper = (queryClient: QueryClient) => {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const renderTab = (
  props: Omit<
    Parameters<typeof KnowledgeBaseVersionControlTab>[0],
    'allowedOperations'
  > & Partial<Pick<
    Parameters<typeof KnowledgeBaseVersionControlTab>[0],
    'allowedOperations'
  >>,
) => {
  const queryClient = createQueryClient();
  const allowedOperations = props.allowedOperations ?? (
    props.accessRole === 'reader'
      ? [OPERATION_IDS.knowledgeBaseDetailRead]
      : props.accessRole === 'manager'
        ? [
            OPERATION_IDS.knowledgeBaseDetailRead,
            OPERATION_IDS.knowledgeBaseContentWrite,
          ]
        : [
            OPERATION_IDS.knowledgeBaseDetailRead,
            OPERATION_IDS.knowledgeBaseContentWrite,
            OPERATION_IDS.knowledgeBaseSettingsManage,
            OPERATION_IDS.knowledgeBaseShareManage,
            OPERATION_IDS.knowledgeBaseDelete,
          ]
  );
  const view = render(
    createWrapper(queryClient)({
      children: (
        <KnowledgeBaseVersionControlTab
          {...props}
          allowedOperations={allowedOperations}
        />
      ),
    }),
  );
  return { ...view, queryClient };
};

const routeSessionGet = async (url: string) => {
  if (url.endsWith('/version-control/repository')) return apiMocks.repository();
  if (url.includes('/version-control/changes')) return apiMocks.changes();
  if (url.includes('/version-control/status')) return apiMocks.status();
  if (url.includes('/version-control/operation-status')) return { isActive: false };
  if (url.endsWith('/version-control/branches')) {
    return { branches: await apiMocks.branches('kb-1') };
  }
  if (url.includes('/version-control/commits?')) return apiMocks.commits('kb-1');
  if (url.includes('/version-control/commits/') && url.endsWith('/files')) {
    const commitId = url.split('/commits/')[1]?.split('/')[0] ?? '';
    return apiMocks.commitFiles('kb-1', decodeURIComponent(commitId));
  }
  if (url.includes('/version-control/blob?')) {
    const params = new URLSearchParams(url.split('?')[1] ?? '');
    return apiMocks.blob('kb-1', params.get('path'), params.get('revision'));
  }
  if (url.includes('/version-control/diff?')) {
    const params = new URLSearchParams(url.split('?')[1] ?? '');
    return apiMocks.diff('kb-1', params.get('path'), params.get('head'));
  }
  if (url.endsWith('/version-control/lfs')) return { patterns: [] };
  return {};
};

const routeSessionPost = async (url: string, body?: unknown) => {
  if (url.endsWith('/version-control/init')) {
    return apiMocks.initializeRepository('kb-1', body);
  }
  if (url.endsWith('/version-control/clone')) {
    return apiMocks.cloneRepository('kb-1', body);
  }
  if (url.endsWith('/version-control/lfs')) {
    return apiMocks.updateLfsPatterns('kb-1', body);
  }
  return {};
};

const routeSessionPut = async (url: string, body?: unknown) => {
  if (url.endsWith('/version-control/remote')) {
    return apiMocks.setRemote(
      'kb-1',
      (body as { remoteUrl?: string } | undefined)?.remoteUrl,
    );
  }
  return {};
};

describe('KnowledgeBaseVersionControlTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: false,
      currentBranch: null,
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: true,
      cloneBlockedReason: null,
    });
    apiMocks.initializeRepository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    apiMocks.cloneRepository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'develop',
      remoteUrl: 'git@example.com:team/knowledge.git',
      hasOrigin: true,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    apiMocks.updateLfsPatterns.mockResolvedValue({ success: true, message: 'ok' });
    apiMocks.changes.mockResolvedValue({
      // additions/deletions present so the deferred numstat query stays idle.
      staged: { items: [{ name: 'README.md', path: 'README.md', status: 'modified', additions: 1, deletions: 0 }], total: 1, nextCursor: null, hasMore: false },
      unstaged: { items: [
        { name: 'notes.md', path: 'notes.md', status: 'modified', additions: 1, deletions: 0 },
        { name: 'draft.md', path: 'draft.md', status: 'modified', additions: 1, deletions: 0 },
      ], total: 2, nextCursor: null, hasMore: false },
      untracked: { items: [], total: 0, nextCursor: null, hasMore: false },
      conflicts: { items: [], total: 0, nextCursor: null, hasMore: false },
    });
    apiMocks.status.mockResolvedValue({
      isInitialized: true,
      currentBranch: 'main',
      detachedHead: false,
      headSha: 'commit-1',
      hasOrigin: false,
      upstream: null,
      ahead: 0,
      behind: 0,
      hasConflicts: false,
      stagedTotal: 1,
      unstagedTotal: 2,
      untrackedTotal: 0,
      conflictTotal: 0,
      operationStatus: null,
    });
    apiMocks.branches.mockResolvedValue([{
      name: 'main', displayName: 'main', kind: 'local', isCurrent: true,
      upstream: null, checkedOutTarget: null, ahead: 0, behind: 0,
      capabilities: { switch: { allowed: true }, rename: { allowed: true }, delete: { allowed: false } },
    }]);
    apiMocks.commits.mockResolvedValue({ total: 0, nextCursor: null, hasMore: false, queryScope: 'current', items: [] });
    apiMocks.commitFiles.mockResolvedValue({ commitId: 'commit-1', files: [] });
    apiMocks.diff.mockResolvedValue({ path: 'notes.md', head: 'WORKTREE', patch: '' });
    apiMocks.blob.mockResolvedValue({ path: 'docs/overview.md', revision: 'commit-1', content: '# Overview' });
    apiMocks.setRemote.mockResolvedValue({ success: true, message: 'ok' });
    sharedClient.get.mockImplementation(routeSessionGet);
    sharedClient.post.mockImplementation(routeSessionPost);
    sharedClient.put.mockImplementation(routeSessionPut);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    selectionActionPathsMock.mockImplementation((file: { path: string }) => [file.path]);
  });

  it('renders the shared setup in the navigator region when the knowledge base has no Git repository', async () => {
    renderTab({
      knowledgeBaseId: 'kb-1',
      accessRole: 'owner',
      mode: 'changes',
      renderRegions: ({ navigator, main }) => (
        <>
          <div data-testid="version-control-navigator-region">{navigator}</div>
          <div data-testid="version-control-main-region">{main}</div>
        </>
      ),
    });

    const setup = await screen.findByTestId('version-control-repository-setup');
    expect(screen.getByTestId('version-control-navigator-region')).toContainElement(setup);
    expect(screen.getByTestId('version-control-main-region')).not.toContainElement(setup);
    expect(screen.getByTestId('version-control-main-diff')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u521d\u59cb\u5316 Git' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Clone \u5132\u5b58\u5eab' })).toBeEnabled();
  });

  it('surfaces repository query failures without crashing the setup view', async () => {
    apiMocks.repository.mockRejectedValue(
      new MockApiError('repository unavailable', 400),
    );

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    expect(await screen.findByTestId('version-control-repository-setup')).toBeInTheDocument();
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
        description: 'knowledgeBase.versionControl.loadFailed',
        variant: 'destructive',
      }));
    });
  });

  it('hides Git setup mutations from a manager without settings capability', async () => {
    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'manager', mode: 'changes' });

    expect(await screen.findByTestId('version-control-repository-setup')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\u521d\u59cb\u5316 Git' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Clone \u5132\u5b58\u5eab' })).not.toBeInTheDocument();
  });

  it(
    'uses readable Git status without mounting mutation metadata for a reader',
    async () => {
      const user = userEvent.setup();
      const { queryClient } = renderTab({
        knowledgeBaseId: 'kb-1',
        accessRole: 'reader',
        mode: 'changes',
        versionControlEnabled: true,
      });

      expect(await screen.findByTestId('version-control-changes-sidebar')).toHaveTextContent('main:1:2:0');
      expect(apiMocks.repository).not.toHaveBeenCalled();
      expect(sharedClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/version-control/status'),
      );
      expect(sharedClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/version-control/changes'),
      );
      expect(queryClient.getQueryCache().findAll({
        predicate: query => (
          query.queryKey[4] === 'remote'
          && query.queryKey[5] === 'repository'
          && (query.state.data as { remoteUrl?: unknown } | undefined)?.remoteUrl != null
        ),
      })).toHaveLength(0);

      await user.click(screen.getByRole('button', { name: 'refresh' }));
      await waitFor(() => {
        expect(apiMocks.repository).not.toHaveBeenCalled();
      });
    },
  );

  it.each(['changes', 'history'] as const)(
    'renders a working second-column refresh action in %s mode',
    async (mode) => {
      const user = userEvent.setup();
      renderTab({
        knowledgeBaseId: 'kb-1',
        accessRole: 'owner',
        mode,
        versionControlEnabled: true,
        renderRegions: ({ navigator, navigatorActions, main }) => (
          <>
            <div data-testid="version-control-navigator-region">
              <div data-testid="version-control-navigator-actions">{navigatorActions}</div>
              {navigator}
            </div>
            <div data-testid="version-control-main-region">{main}</div>
          </>
        ),
      });

      await screen.findByTestId(
        mode === 'changes'
          ? 'version-control-changes-sidebar'
          : 'version-control-history-sidebar',
      );
      const changesCallsBeforeRefresh = apiMocks.changes.mock.calls.length;

      await user.click(screen.getByRole('button', { name: '\u91cd\u65b0\u6574\u7406' }));

      await waitFor(() => {
        expect(apiMocks.changes.mock.calls.length).toBeGreaterThan(changesCallsBeforeRefresh);
      });
    },
  );

  it('requests the index diff when a staged file is selected', async () => {
    const user = userEvent.setup();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    await user.click(await screen.findByRole('button', { name: 'select staged README.md' }));

    await waitFor(() => {
      expect(apiMocks.diff).toHaveBeenCalledWith('kb-1', 'README.md', 'INDEX');
    });
  });

  it('removes cached repository metadata when manager access is downgraded', async () => {
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: 'git@example.com:team/private.git',
      hasOrigin: true,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    const queryClient = createQueryClient();
    const renderWithRole = (accessRole: 'manager' | 'reader') => (
      createWrapper(queryClient)({
        children: (
          <KnowledgeBaseVersionControlTab
            knowledgeBaseId="kb-1"
            accessRole={accessRole}
            allowedOperations={accessRole === 'manager'
              ? [
                  OPERATION_IDS.knowledgeBaseDetailRead,
                  OPERATION_IDS.knowledgeBaseContentWrite,
                  OPERATION_IDS.knowledgeBaseSettingsManage,
                  OPERATION_IDS.knowledgeBaseShareManage,
                ]
              : [OPERATION_IDS.knowledgeBaseDetailRead]}
            mode="changes"
            versionControlEnabled
          />
        ),
      })
    );
    const { rerender } = render(renderWithRole('manager'));

    await waitFor(() => expect(apiMocks.repository).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      expect(queryClient.getQueryCache().findAll({
        predicate: query => (
          query.queryKey[4] === 'remote'
          && query.queryKey[5] === 'repository'
          && (query.state.data as { remoteUrl?: unknown } | undefined)?.remoteUrl
            === 'git@example.com:team/private.git'
        ),
      })).toHaveLength(1);
    });

    rerender(renderWithRole('reader'));

    await waitFor(() => {
      expect(queryClient.getQueryCache().findAll({
        predicate: query => (
          query.queryKey[4] === 'remote'
          && query.queryKey[5] === 'repository'
          && (query.state.data as { remoteUrl?: unknown } | undefined)?.remoteUrl != null
        ),
      })).toHaveLength(0);
    });
    expect(apiMocks.repository).toHaveBeenCalledTimes(1);
  });

  it('initializes Git through the shared repository contract', async () => {
    const user = userEvent.setup();
    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    await user.click(await screen.findByRole('button', { name: '\u521d\u59cb\u5316 Git' }));

    await waitFor(() => {
      expect(apiMocks.initializeRepository).toHaveBeenCalledWith('kb-1', { defaultBranch: 'main' });
    });
  });

  it('clones Git through the shared repository contract', async () => {
    const user = userEvent.setup();
    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    await user.click(await screen.findByRole('button', { name: 'Clone \u5132\u5b58\u5eab' }));

    await waitFor(() => {
      expect(apiMocks.cloneRepository).toHaveBeenCalledWith('kb-1', {
        remoteUrl: 'git@example.com:team/knowledge.git',
        branch: 'develop',
      });
    });
  });

  it('uses the shared version control components for an enabled repository', async () => {
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: 'git@example.com:team/knowledge.git',
      hasOrigin: true,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    expect(await screen.findByTestId('version-control-changes-sidebar')).toHaveTextContent('main:1:2:0');
    expect(screen.getByTestId('version-control-main-diff')).toHaveTextContent('empty');
  });

  it('passes conflict files to the shared changes sidebar and includes them in the change count', async () => {
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    apiMocks.changes.mockResolvedValue({
      staged: { items: [], total: 0, nextCursor: null, hasMore: false },
      unstaged: { items: [{ name: 'notes.md', path: 'notes.md', status: 'modified', additions: 1, deletions: 0 }], total: 1, nextCursor: null, hasMore: false },
      untracked: { items: [], total: 0, nextCursor: null, hasMore: false },
      conflicts: { items: [{ name: 'conflict.txt', path: 'conflict.txt', status: 'UU', type: 'unmerged', additions: 1, deletions: 0 }], total: 1, nextCursor: null, hasMore: false },
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    expect(await screen.findByText('\u885d\u7a81')).toBeInTheDocument();
    expect(screen.getByText('conflict.txt:conflict.txt')).toBeInTheDocument();
    expect(screen.getByTestId('knowledge-base-version-control-sidebar')).toHaveTextContent('2');
  });

  it('loads a revision blob when a history file has no inline patch', async () => {
    const user = userEvent.setup();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    apiMocks.commits.mockResolvedValue({
      total: 1,
      nextCursor: null,
      hasMore: false,
      queryScope: 'current',
      items: [{
        id: 'commit-1',
        message: 'Update overview',
        author: 'User',
        timestamp: 1777435200,
      }],
    });
    apiMocks.commitFiles.mockResolvedValue({
      commitId: 'commit-1',
      files: [{ name: 'overview.md', path: 'docs/overview.md', status: 'modified' }],
    });
    apiMocks.blob.mockResolvedValue({
      path: 'docs/overview.md',
      revision: 'commit-1',
      content: '# Overview',
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'history' });

    expect(await screen.findByTestId('version-control-history-sidebar')).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: 'Update overview' }));
    await user.click(await screen.findByRole('button', { name: 'docs/overview.md' }));

    await waitFor(() => {
      expect(apiMocks.blob).toHaveBeenCalledWith('kb-1', 'docs/overview.md', 'commit-1');
      expect(screen.getByTestId('version-control-main-diff')).toHaveTextContent('# Overview');
    });
  });

  it('uses the shared branch and remote workflows', async () => {
    const user = userEvent.setup();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: '',
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    await screen.findByTestId('version-control-changes-sidebar');
    expect(screen.getByRole('button', { name: 'create branch' })).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: 'remoteSettings' }));
    await user.click(screen.getByRole('button', { name: 'save remote' }));

    await waitFor(() => {
      expect(apiMocks.setRemote).toHaveBeenCalledWith('kb-1', 'git@example.com:team/knowledge.git');
    });
  });

  it('keeps Git LFS management after repository initialization', async () => {
    const user = userEvent.setup();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });

    renderTab({
      knowledgeBaseId: 'kb-1',
      accessRole: 'owner',
      mode: 'changes',
      gitLfsEnabled: false,
    });

    await user.click(await screen.findByRole('button', { name: 'lfs' }));
    await user.click(screen.getByRole('button', { name: 'save lfs patterns' }));

    await waitFor(() => {
      expect(apiMocks.updateLfsPatterns).toHaveBeenCalledWith('kb-1', { patterns: ['*.bin'] });
    });
    expect(screen.getByRole('button', { name: 'lfs' })).toBeEnabled();
  });

  it('reloads all Knowledge Base version-control views after a successful remote mutation', async () => {
    const user = userEvent.setup();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: '',
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    await screen.findByTestId('version-control-changes-sidebar');
    apiMocks.branches.mockClear();
    apiMocks.commits.mockClear();
    sharedClient.get.mockClear();

    await user.click(screen.getByRole('button', { name: 'remoteSettings' }));
    await user.click(screen.getByRole('button', { name: 'save remote' }));

    await waitFor(() => {
      expect(apiMocks.setRemote).toHaveBeenCalledWith('kb-1', 'git@example.com:team/knowledge.git');
      expect(apiMocks.branches).toHaveBeenCalledWith('kb-1');
      expect(apiMocks.commits).toHaveBeenCalledWith('kb-1');
    });
    // Changes and status refresh through the session-owned client.
    await waitFor(() => {
      expect(sharedClient.get).toHaveBeenCalledWith(expect.stringContaining('/version-control/changes'));
      expect(sharedClient.get).toHaveBeenCalledWith(expect.stringContaining('/version-control/status'));
    });
  });

  it('passes selected Knowledge Base file paths to batch actions', async () => {
    const user = userEvent.setup();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    await user.click(await screen.findByRole('button', { name: 'select notes.md' }));
    await user.keyboard('{Control>}');
    await user.click(screen.getByRole('button', { name: 'select draft.md' }));
    await user.keyboard('{/Control}');
    await user.click(await screen.findByRole('button', { name: 'discard notes.md' }));
    await user.click(screen.getByRole('button', { name: 'confirm discard' }));
    await waitFor(() => expect(sharedClient.post).toHaveBeenCalledWith(
      expect.stringContaining('/version-control/discard'),
      { paths: ['notes.md', 'draft.md'] },
    ));

    await user.click(screen.getByRole('button', { name: 'select notes.md' }));
    await user.keyboard('{Control>}');
    await user.click(screen.getByRole('button', { name: 'select draft.md' }));
    await user.keyboard('{/Control}');
    await user.click(screen.getByRole('button', { name: 'stage notes.md' }));
    await waitFor(() => expect(sharedClient.post).toHaveBeenCalledWith(
      expect.stringContaining('/version-control/stage'),
      { paths: ['notes.md', 'draft.md'] },
    ));
  });

  it('uses all requests for Knowledge Base header stage and unstage actions', async () => {
    const user = userEvent.setup();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    await user.click(await screen.findByRole('button', { name: 'stage all' }));
    await waitFor(() => expect(sharedClient.post).toHaveBeenCalledWith(
      expect.stringContaining('/version-control/stage'),
      { all: true },
    ));

    await user.click(screen.getByRole('button', { name: 'unstage all' }));
    await waitFor(() => expect(sharedClient.post).toHaveBeenCalledWith(
      expect.stringContaining('/version-control/unstage'),
      { all: true },
    ));
  });

  it('shows operation-in-progress toast without reloading Knowledge Base changes', async () => {
    const user = userEvent.setup();
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    sharedClient.post.mockImplementation(async (url: string) => {
      if (url.includes('/version-control/stage')) {
        throw new MockApiError('Git operation already in progress', 409, 'operation_locked');
      }
      return {};
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    await user.click(await screen.findByRole('button', { name: 'stage notes.md' }));

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Git operation in progress',
        description: 'Wait for the current Git operation to finish.',
        variant: 'destructive',
      }));
    });
    // changes fetched exactly once (initial load); not refetched on op-in-progress.
    const changesCalls = sharedClient.get.mock.calls.filter(([url]) => String(url).includes('/version-control/changes'));
    expect(changesCalls).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'stage notes.md' })).toBeInTheDocument();
  });

  it('disables writes while a version-control operation is reported active', async () => {
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    sharedClient.get.mockImplementation(async (url: string) => {
      if (url.includes('/version-control/operation-status')) {
        return { isActive: true, operation: 'changes.commit' };
      }
      return routeSessionGet(url);
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    const sidebar = await screen.findByTestId('version-control-changes-sidebar');
    await waitFor(() => expect(sidebar).toHaveAttribute('data-mutating', 'true'));
  });

  it('refreshes changes and status when the polled operation goes active to inactive', async () => {
    apiMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    let operationActive = true;
    sharedClient.get.mockImplementation(async (url: string) => {
      if (url.includes('/version-control/operation-status')) {
        return { isActive: operationActive };
      }
      return routeSessionGet(url);
    });

    renderTab({ knowledgeBaseId: 'kb-1', accessRole: 'owner', mode: 'changes' });

    // Initial fetch reports an active operation: writes are gated.
    const sidebar = await screen.findByTestId('version-control-changes-sidebar');
    await waitFor(() => expect(sidebar).toHaveAttribute('data-mutating', 'true'));

    // refetchInterval polls every 1s while active; the next poll reports the op
    // finished, the active -> inactive transition invalidates changes + status,
    // and writes re-enable.
    operationActive = false;
    await waitFor(
      () => expect(sidebar).toHaveAttribute('data-mutating', 'false'),
      { timeout: 3000 },
    );
    const changesCalls = sharedClient.get.mock.calls.filter(([url]) => String(url).includes('/version-control/changes'));
    const statusCalls = sharedClient.get.mock.calls.filter(([url]) => String(url).includes('/version-control/status'));
    expect(changesCalls.length).toBeGreaterThanOrEqual(2);
    expect(statusCalls.length).toBeGreaterThanOrEqual(2);
  });

});
