import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseVersionControlTab } from './KnowledgeBaseVersionControlTab';

const apiMocks = vi.hoisted(() => ({
  getKnowledgeBaseGitRepositoryStatus: vi.fn(),
  enableKnowledgeBaseGitRepository: vi.fn(),
  enableKnowledgeBaseGitLfs: vi.fn(),
  getStatus: vi.fn(),
  getChanges: vi.fn(),
  getBranches: vi.fn(),
  getCommits: vi.fn(),
  getCommitFiles: vi.fn(),
  getDiff: vi.fn(),
  getBlob: vi.fn(),
  stage: vi.fn(),
  unstage: vi.fn(),
  discard: vi.fn(),
  commit: vi.fn(),
  checkoutBranch: vi.fn(),
  fetch: vi.fn(),
  pull: vi.fn(),
  push: vi.fn(),
  setRemoteUrl: vi.fn(),
  revert: vi.fn(),
  rollback: vi.fn(),
}));

const toastMock = vi.hoisted(() => vi.fn());
const translateMock = vi.hoisted(() => {
  const translations: Record<string, string> = {
    'knowledgeBase.versionControl.loading': '載入版本控制',
    'knowledgeBase.versionControl.setup.title': '為這個知識庫啟用 Git',
    'knowledgeBase.versionControl.setup.description': 'Git 是選用功能。',
    'knowledgeBase.versionControl.setup.defaultBranch': '預設分支',
    'knowledgeBase.versionControl.setup.defaultBranchPlaceholder': 'main',
    'knowledgeBase.versionControl.setup.enableLfs': '啟用 Git LFS',
    'knowledgeBase.versionControl.setup.enableLfsDescription': '大型檔案追蹤',
    'knowledgeBase.versionControl.setup.enableAction': '啟用 Git',
    'knowledgeBase.versionControl.setup.enabling': '正在啟用',
    'knowledgeBase.versionControl.setup.initialCommitMessage': 'Initialize knowledge base version control',
    'knowledgeBase.versionControl.mode.title': '版本控制',
    'shared.versionControl.mode.fileChanges': '檔案變更',
    'shared.versionControl.mode.commitHistory': '變更記錄',
    'shared.versionControl.branchDialog.title': '建立分支',
    'shared.versionControl.remoteDialog.title': '遠端設定',
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

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => ({
  getKnowledgeBaseGitRepositoryStatus: apiMocks.getKnowledgeBaseGitRepositoryStatus,
  enableKnowledgeBaseGitRepository: apiMocks.enableKnowledgeBaseGitRepository,
  enableKnowledgeBaseGitLfs: apiMocks.enableKnowledgeBaseGitLfs,
  knowledgeBaseVersionControlApi: {
    getStatus: apiMocks.getStatus,
    getChanges: apiMocks.getChanges,
    getBranches: apiMocks.getBranches,
    getCommits: apiMocks.getCommits,
    getCommitFiles: apiMocks.getCommitFiles,
    getDiff: apiMocks.getDiff,
    getBlob: apiMocks.getBlob,
    stage: apiMocks.stage,
    unstage: apiMocks.unstage,
    discard: apiMocks.discard,
    commit: apiMocks.commit,
    checkoutBranch: apiMocks.checkoutBranch,
    fetch: apiMocks.fetch,
    pull: apiMocks.pull,
    push: apiMocks.push,
    setRemoteUrl: apiMocks.setRemoteUrl,
    revert: apiMocks.revert,
    rollback: apiMocks.rollback,
  },
}));

vi.mock('@/shared/components/version-control', () => ({
  VersionControlLayout: ({ modeRail, sidebar, main }: {
    modeRail: React.ReactNode;
    sidebar: React.ReactNode;
    main: React.ReactNode;
  }) => (
    <div data-testid="version-control-layout">
      {modeRail}
      {sidebar}
      {main}
    </div>
  ),
  VersionControlModeRail: ({ title, items, onChange, footer }: {
    title: string;
    items: Array<{ label: string; count?: number }>;
    onChange: (id: string) => void;
    footer?: React.ReactNode;
  }) => (
    <div data-testid="version-control-mode-rail">
      <span>{title}</span>
      {items.map((item) => (
        <button key={item.label} type="button" onClick={() => onChange(item.label === '變更記錄' ? 'history' : 'changes')}>
          {item.label}:{item.count}
        </button>
      ))}
      {footer}
    </div>
  ),
  VersionControlChangesSidebar: ({ currentBranch, stagedFiles, unstagedFiles, onCreateBranch, actions }: {
    currentBranch: string;
    stagedFiles: unknown[];
    unstagedFiles: unknown[];
    onCreateBranch?: () => void;
    actions: Array<{ id: string; onClick: () => void }>;
  }) => (
    <div data-testid="version-control-changes-sidebar">
      {currentBranch}:{stagedFiles.length}:{unstagedFiles.length}
      {onCreateBranch && <button type="button" onClick={onCreateBranch}>create branch</button>}
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
    onCreate: (payload: { branch: string; startPoint?: string; stashChanges?: boolean }) => void;
  }) => open ? (
    <div role="dialog" aria-label="建立分支">
      <button type="button" onClick={() => onCreate({ branch: 'feature/wiki', startPoint: 'main', stashChanges: true })}>
        confirm branch
      </button>
    </div>
  ) : null,
  VersionControlRemoteSettingsDialog: ({ open, onSaveRemoteUrl }: {
    open: boolean;
    onSaveRemoteUrl: (remoteUrl: string) => void;
  }) => open ? (
    <div role="dialog" aria-label="遠端設定">
      <button type="button" onClick={() => onSaveRemoteUrl('git@example.com:team/wiki.git')}>
        save remote
      </button>
    </div>
  ) : null,
}));

describe('KnowledgeBaseVersionControlTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getKnowledgeBaseGitRepositoryStatus.mockResolvedValue({
      isGitRepo: false,
      currentBranch: null,
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: true,
      cloneBlockedReason: null,
    });
    apiMocks.enableKnowledgeBaseGitRepository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    apiMocks.enableKnowledgeBaseGitLfs.mockResolvedValue({ success: true, message: 'ok' });
    apiMocks.getStatus.mockResolvedValue({
      branch: 'main',
      ahead: 0,
      behind: 0,
      detached: false,
      hasConflicts: false,
      stagedCount: 1,
      unstagedCount: 1,
      untrackedCount: 0,
    });
    apiMocks.getChanges.mockResolvedValue({
      staged: [{ name: 'README.md', path: 'README.md', status: 'modified' }],
      unstaged: [{ name: 'notes.md', path: 'notes.md', status: 'modified' }],
      untracked: [],
    });
    apiMocks.getBranches.mockResolvedValue([{ name: 'main', isActive: true }]);
    apiMocks.getCommits.mockResolvedValue({ page: 1, pageSize: 20, total: 0, items: [] });
    apiMocks.getCommitFiles.mockResolvedValue({ commitId: 'commit-1', files: [] });
    apiMocks.getBlob.mockResolvedValue({ path: 'wiki/overview.md', revision: 'commit-1', content: '# Overview' });
    apiMocks.setRemoteUrl.mockResolvedValue({ success: true, message: 'ok' });
    apiMocks.revert.mockResolvedValue({ success: true, message: 'ok' });
    apiMocks.rollback.mockResolvedValue({ success: true, message: 'ok' });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('renders the enable card when the knowledge base has no Git repository', async () => {
    render(<KnowledgeBaseVersionControlTab knowledgeBaseId="kb-1" accessRole="owner" />);

    expect(await screen.findByText('為這個知識庫啟用 Git')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '啟用 Git' })).toBeEnabled();
  });

  it('enables Git with the configured default branch and LFS option', async () => {
    const user = userEvent.setup();
    render(<KnowledgeBaseVersionControlTab knowledgeBaseId="kb-1" accessRole="owner" />);

    await user.click(await screen.findByRole('button', { name: '啟用 Git' }));

    await waitFor(() => {
      expect(apiMocks.enableKnowledgeBaseGitRepository).toHaveBeenCalledWith('kb-1', {
        defaultBranch: 'main',
        initialMessage: 'Initialize knowledge base version control',
      });
      expect(apiMocks.enableKnowledgeBaseGitLfs).not.toHaveBeenCalled();
    });
  });

  it('uses the shared Template Center version control components for an enabled repository', async () => {
    apiMocks.getKnowledgeBaseGitRepositoryStatus.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: 'git@example.com:team/wiki.git',
      hasOrigin: true,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });

    render(<KnowledgeBaseVersionControlTab knowledgeBaseId="kb-1" accessRole="owner" versionControlEnabled />);

    expect(await screen.findByTestId('version-control-layout')).toBeInTheDocument();
    expect(screen.getByTestId('version-control-mode-rail')).toHaveTextContent('版本控制');
    expect(screen.getByTestId('version-control-changes-sidebar')).toHaveTextContent('main:1:1');
    expect(screen.getByTestId('version-control-main-diff')).toHaveTextContent('empty');
  });

  it('loads a revision blob when a history file has no inline patch', async () => {
    const user = userEvent.setup();
    apiMocks.getKnowledgeBaseGitRepositoryStatus.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });
    apiMocks.getCommits.mockResolvedValue({
      page: 1,
      pageSize: 20,
      total: 1,
      items: [{
        id: 'commit-1',
        message: 'Update overview',
        author: 'User',
        timestamp: 1777435200000,
      }],
    });
    apiMocks.getCommitFiles.mockResolvedValue({
      commitId: 'commit-1',
      files: [{ name: 'overview.md', path: 'wiki/overview.md', status: 'modified' }],
    });
    apiMocks.getBlob.mockResolvedValue({
      path: 'wiki/overview.md',
      revision: 'commit-1',
      content: '# Overview',
    });

    render(<KnowledgeBaseVersionControlTab knowledgeBaseId="kb-1" accessRole="owner" versionControlEnabled />);

    await user.click(await screen.findByRole('button', { name: '變更記錄:1' }));
    await user.click(await screen.findByRole('button', { name: 'Update overview' }));
    await user.click(await screen.findByRole('button', { name: 'wiki/overview.md' }));

    await waitFor(() => {
      expect(apiMocks.getBlob).toHaveBeenCalledWith('kb-1', 'wiki/overview.md', 'commit-1');
      expect(screen.getByTestId('version-control-main-diff')).toHaveTextContent('# Overview');
    });
  });

  it('uses shared dialogs for branch and remote workflows without sidebar recovery controls', async () => {
    const user = userEvent.setup();
    apiMocks.getKnowledgeBaseGitRepositoryStatus.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: '',
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
      cloneBlockedReason: null,
    });

    render(<KnowledgeBaseVersionControlTab knowledgeBaseId="kb-1" accessRole="owner" versionControlEnabled />);

    await user.click(await screen.findByRole('button', { name: 'create branch' }));
    await user.click(screen.getByRole('button', { name: 'confirm branch' }));

    await user.click(screen.getByRole('button', { name: 'remoteSettings' }));
    await user.click(screen.getByRole('button', { name: 'save remote' }));

    await waitFor(() => {
      expect(apiMocks.checkoutBranch).toHaveBeenCalledWith('kb-1', 'feature/wiki', {
        create: true,
        startPoint: 'main',
        stashChanges: true,
      });
      expect(apiMocks.setRemoteUrl).toHaveBeenCalledWith('kb-1', 'git@example.com:team/wiki.git');
    });
    expect(screen.queryByText('復原操作')).not.toBeInTheDocument();
    expect(screen.queryByText('ahead 0 / behind 0')).not.toBeInTheDocument();
    expect(apiMocks.revert).not.toHaveBeenCalled();
    expect(apiMocks.rollback).not.toHaveBeenCalled();
  });
});
