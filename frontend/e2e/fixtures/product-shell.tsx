import React from 'react';
import ReactDOM from 'react-dom/client';
import { Settings } from 'lucide-react';
import { KnowledgeBaseVersionControlPresentation } from '@/features/knowledge-base/components/KnowledgeBaseVersionControlPresentation';
import { KnowledgeBaseShellAdapter } from '@/features/knowledge-base/components/KnowledgeBaseShellAdapter';
import { MarketplaceShellAdapter } from '@/features/marketplace/components/MarketplaceShellAdapter';
import { I18nProvider } from '@/shared/contexts/I18nContext';
import { useI18n } from '@/shared/hooks/useI18n';
import { ProductShell } from '@/shared/components/shell';
import { EntryFrame } from '@/shared/components/entry/EntryFrame';
import { projectWorkspaceEntry } from '@/features/workspace/public';
import type { WorkspaceEntryActionId } from '@/shared/components/entry/workspaceEntryTypes';
import { VersionControlChangesSidebar } from '@/shared/components/version-control/VersionControlChangesSidebar';
import { VersionControlChangesSkeleton } from '@/shared/components/version-control/VersionControlChangesSkeleton';
import { VersionControlDiscardDialog } from '@/shared/components/version-control/VersionControlDiscardDialog';
import { VersionControlHistorySidebar } from '@/shared/components/version-control/VersionControlHistorySidebar';
import { VersionControlMainDiff } from '@/shared/components/version-control/VersionControlMainDiff';
import { VersionControlRenameBranchDialog } from '@/shared/components/version-control/VersionControlBranchDialogs';
import { VersionControlRepositorySetup } from '@/shared/components/version-control/VersionControlRepositorySetup';
import type { VersionControlWorkbenchMode } from '@/shared/components/version-control';
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from '@/shared/components/ui/context-menu';
import type {
  VersionControlBranch,
  VersionControlCommitSummary,
  VersionControlFileChange,
} from '@/shared/version-control';
import '@/shared/design-system/styles/globals.css';
import './product-shell.css';

type FixtureProduct = 'workspace' | 'knowledge-base' | 'marketplace';
type FixtureState = 'content' | 'empty' | 'loading' | 'error';

const parameters = new URLSearchParams(window.location.search);
const product = (parameters.get('product') ?? 'workspace') as FixtureProduct;
const initialMode = (parameters.get('mode') ?? 'changes') as VersionControlWorkbenchMode;
const state = (parameters.get('state') ?? 'content') as FixtureState;
const surface = parameters.get('surface') ?? 'workbench';
const initialEntryState = parameters.get('entryState') ?? 'pending';
const useProductShellWorkspace = parameters.get('shell') === 'product';
const dialogType = parameters.get('dialog') ?? 'confirm';
const readOnly = parameters.get('readOnly') === '1';
const withConflict = parameters.get('conflict') !== '0';
const withMultiSelection = parameters.get('multi') !== '0';

const longBranch = 'feature/unified-version-control-workbench-with-an-intentionally-long-branch-name';
const longPath = 'packages/shared/version-control/fixtures/an-intentionally-long-directory-name/another-long-segment/component-with-a-long-name.tsx';

const branches: VersionControlBranch[] = [
  {
    name: longBranch,
    displayName: longBranch,
    kind: 'local',
    isCurrent: true,
    capabilities: {
      switch: { allowed: false },
      rename: { allowed: true },
      delete: { allowed: false },
    },
  },
  {
    name: 'feature/secondary',
    displayName: 'feature/secondary',
    kind: 'local',
    capabilities: {
      switch: { allowed: true },
      rename: { allowed: true },
      delete: { allowed: true },
    },
  },
];

const stagedFiles: VersionControlFileChange[] = [
  {
    name: 'component-with-a-long-name.tsx',
    path: longPath,
    status: 'M',
    type: 'modified',
    additions: 128,
    deletions: 31,
  },
  {
    name: 'new-contract.ts',
    path: 'packages/shared/version-control/new-contract.ts',
    status: 'A',
    type: 'added',
    additions: 44,
    deletions: 0,
  },
];

const unstagedFiles: VersionControlFileChange[] = [
  {
    name: 'layout-shell.tsx',
    path: 'frontend/src/shared/components/layout/layout-shell.tsx',
    status: 'M',
    type: 'modified',
    additions: 17,
    deletions: 8,
  },
  {
    name: 'obsolete-adapter.ts',
    path: 'frontend/src/features/product/obsolete-adapter.ts',
    status: 'D',
    type: 'deleted',
    additions: 0,
    deletions: 203,
  },
];

const conflictFiles: VersionControlFileChange[] = [{
  name: 'conflicted-file-with-a-long-name.tsx',
  path: 'frontend/src/shared/version-control/conflicted-file-with-a-long-name.tsx',
  status: 'U',
  type: 'unmerged',
  additions: 12,
  deletions: 12,
}];

const commits: VersionControlCommitSummary[] = [
  {
    id: '0123456789abcdef0123456789abcdef01234567',
    message: 'Unify all three product workbenches while preserving an intentionally long commit subject for overflow verification',
    author: 'Version Control Fixture Author With A Long Name',
    timestamp: Date.now() - 60_000,
    branch: longBranch,
    additions: 192,
    deletions: 54,
    files: 7,
  },
  {
    id: 'fedcba9876543210fedcba9876543210fedcba98',
    message: 'Add deterministic viewport collision coverage',
    author: 'Fixture Bot',
    timestamp: Date.now() - 3_600_000,
    branch: longBranch,
    additions: 88,
    deletions: 4,
    files: 3,
  },
];

const noop = () => undefined;
const noopAsync = async () => undefined;

interface ProductPresentationProps {
  mode: VersionControlWorkbenchMode;
  onModeChange: (mode: VersionControlWorkbenchMode) => void;
  sidebar: React.ReactNode;
  main: React.ReactNode;
}

interface MarketplaceVersionControlModeActionsProps {
  mode: VersionControlWorkbenchMode;
  changeCount: number;
  commitCount: number;
  onModeChange: (mode: VersionControlWorkbenchMode) => void;
}

const MarketplaceVersionControlModeActions: React.FC<MarketplaceVersionControlModeActionsProps> = ({
  mode,
  changeCount,
  commitCount,
  onModeChange,
}) => {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-1" data-testid="marketplace-version-control-mode-actions">
      <button
        type="button"
        aria-pressed={mode === 'changes'}
        onClick={() => onModeChange('changes')}
      >
        {t('workspace.navigation.versionControl.changes')} ({changeCount})
      </button>
      <button
        type="button"
        aria-pressed={mode === 'history'}
        onClick={() => onModeChange('history')}
      >
        {t('workspace.navigation.versionControl.history')} ({commitCount})
      </button>
    </div>
  );
};

const ProductPresentation: React.FC<ProductPresentationProps> = ({
  mode,
  onModeChange,
  sidebar,
  main,
}) => {
  const { t } = useI18n();

  if (product === 'workspace' && !useProductShellWorkspace) {
    return (
      <div className="fixture-baseline-layout" data-testid="workspace-version-control-presentation">
        <div className="fixture-baseline-column" data-testid="workspace-version-control-sidebar">
          {mode === 'changes' ? (
            <div className="fixture-context" data-testid="workspace-worktree-extension">
              Worktree fixture: {longBranch}
            </div>
          ) : null}
          <div className="min-h-0 flex-1">{sidebar}</div>
        </div>
        <div className="fixture-baseline-main" data-testid="workspace-version-control-main">
          {main}
        </div>
      </div>
    );
  }

  if (product === 'workspace') {
    return (
      <div className="h-screen w-screen" data-testid="workspace-version-control-presentation">
        <ProductShell
          body={{
            kind: 'regions',
            navigator: {
              content: () => (
                <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden" data-testid="workspace-version-control-sidebar">
                  {mode === 'changes' ? (
                    <div className="fixture-context" data-testid="workspace-worktree-extension">
                      Worktree fixture: {longBranch}
                    </div>
                  ) : null}
                  {sidebar}
                </div>
              ),
              behavior: {
                collapsible: false,
                resizable: true,
                defaultWidth: window.innerWidth / 2,
                minWidth: 320,
                maxWidth: 900,
              },
              presentation: {
                accessibleLabel: t('workspace.versionControl.sidebar.title.changes'),
                responsive: 'always',
              },
            },
            main: {
              accessibleLabel: t('workspace.layout.mainContent'),
              content: <div data-testid="workspace-version-control-main">{main}</div>,
            },
          }}
        />
      </div>
    );
  }

  if (product === 'knowledge-base') {
    return (
      <KnowledgeBaseVersionControlPresentation
        mode={mode}
        count={mode === 'changes'
          ? stagedFiles.length + unstagedFiles.length + conflictFiles.length
          : commits.length}
        sidebar={sidebar}
        main={main}
        renderRegions={({ navigator, navigatorTitle, navigatorIcon, navigatorInfo, main: mainRegion }) => (
          <div className="h-screen w-screen" data-testid="knowledge-base-version-control-presentation">
            <KnowledgeBaseShellAdapter
              surface={{
                kind: 'regions',
                navigator: {
                  content: navigator,
                  accessibleLabel: navigatorTitle,
                  title: navigatorTitle,
                  icon: navigatorIcon,
                  info: navigatorInfo,
                },
                main: {
                  content: mainRegion,
                  accessibleLabel: t('knowledgeBase.navigation.versionControl'),
                },
              }}
            />
          </div>
        )}
      />
    );
  }

  return (
    <div className="h-screen w-screen" data-testid="marketplace-version-control-presentation">
      <MarketplaceShellAdapter
        surface={{
          kind: 'settings',
          header: (
            <div className="flex items-center gap-1 px-3">
              <MarketplaceVersionControlModeActions
                mode={mode}
                changeCount={stagedFiles.length + unstagedFiles.length + conflictFiles.length}
                commitCount={commits.length}
                onModeChange={onModeChange}
              />
            </div>
          ),
          navigator: {
            content: () => <div className="flex h-full min-w-0 flex-col" data-testid="marketplace-version-control-sidebar">{sidebar}</div>,
            accessibleLabel: t('marketplace.settings.versionControl.title'),
            preset: 'settings-navigator',
          },
          main: {
            accessibleLabel: t('marketplace.settings.main.label'),
            content: <div className="h-full min-w-0 overflow-hidden" data-testid="marketplace-version-control-main">{main}</div>,
          },
        }}
      />
    </div>
  );
};

interface SharedSidebarProps {
  mode: VersionControlWorkbenchMode;
  fixtureState: FixtureState;
}

const SharedSidebar: React.FC<SharedSidebarProps> = ({ mode, fixtureState }) => {
  if (fixtureState === 'loading') {
    return <VersionControlChangesSkeleton testId="fixture-loading" />;
  }

  if (fixtureState === 'error') {
    return (
      <div className="fixture-state fixture-error" data-testid="fixture-error">
        Fixture refresh error
      </div>
    );
  }

  if (mode === 'history') {
    const visibleCommits = fixtureState === 'empty' ? [] : commits;
    const visibleCommitFiles = fixtureState === 'empty' ? [] : stagedFiles;
    return (
      <VersionControlHistorySidebar
        commits={visibleCommits}
        files={visibleCommitFiles}
        selectedCommitId={visibleCommits[0]?.id ?? null}
        selectedFile={visibleCommitFiles[0] ?? null}
        onCommitSelect={noop}
        onFileSelect={noop}
        onSearchChange={noop}
        branches={branches}
        branchFilter={longBranch}
        onBranchFilterChange={noop}
        onRevertCommit={noop}
        mutationDisabled={readOnly}
      />
    );
  }

  const visibleStaged = fixtureState === 'empty' ? [] : stagedFiles;
  const visibleUnstaged = fixtureState === 'empty' ? [] : unstagedFiles;
  const selectedStagedPaths = withMultiSelection
    ? new Set(stagedFiles.map(file => file.path))
    : new Set<string>();

  return (
    <VersionControlChangesSidebar
      branches={branches}
      currentBranch={longBranch}
      actions={[
        { id: 'refresh', onClick: noop },
        { id: 'fetch', onClick: noop, disabled: readOnly },
        { id: 'pull', onClick: noop, disabled: readOnly },
        { id: 'push', onClick: noop, disabled: readOnly },
      ]}
      actionExtensions={product === 'workspace' ? [{
        key: 'worktree-settings',
        labelKey: 'workspace.versionControl.worktree.menu.settings',
        icon: <Settings className="h-3 w-3" />,
        onClick: noop,
        disabled: readOnly,
      }] : undefined}
      stagedFiles={visibleStaged}
      unstagedFiles={visibleUnstaged}
      conflictFiles={withConflict && fixtureState === 'content' ? conflictFiles : []}
      selectedStagedPath={visibleStaged[0]?.path ?? null}
      selectedStagedPaths={selectedStagedPaths}
      selectedUnstagedPaths={new Set()}
      mutationDisabled={readOnly}
      onBranchChange={noop}
      onCreateBranch={noop}
      onRenameBranch={noop}
      onDeleteBranch={noop}
      onCommit={noop}
      onFileSelect={noop}
      onStageToggle={noop}
      onMarkResolved={noop}
      onAbortConflict={noop}
      onDiscard={noop}
      onStageAll={noop}
      onUnstageAll={noop}
    />
  );
};

const SharedMain: React.FC<{ mode: VersionControlWorkbenchMode; fixtureState: FixtureState }> = ({
  mode,
  fixtureState,
}) => (
  <div className="fixture-main">
    <VersionControlMainDiff
      selectedPath={fixtureState === 'empty' ? null : longPath}
      diffContent={fixtureState === 'content'
        ? '@@ -1,2 +1,3 @@\n-export const oldValue = true;\n+export const unifiedWorkbench = true;\n+export const viewportSafe = true;'
        : null}
      isLoading={fixtureState === 'loading'}
      error={fixtureState === 'error' ? 'Fixture refresh error' : null}
      emptyKey={mode === 'changes'
        ? 'shared.versionControl.main.selectFile'
        : 'shared.versionControl.main.selectCommitFile'}
    />
  </div>
);

const WorkbenchSurface = () => {
  const [mode, setMode] = React.useState<VersionControlWorkbenchMode>(initialMode);
  return (
    <ProductPresentation
      mode={mode}
      onModeChange={setMode}
      sidebar={<SharedSidebar mode={mode} fixtureState={state} />}
      main={<SharedMain mode={mode} fixtureState={state} />}
    />
  );
};

const EdgeMenuSurface = () => {
  const [mode, setMode] = React.useState<VersionControlWorkbenchMode>('changes');
  return (
    <ProductPresentation
      mode={mode}
      onModeChange={setMode}
      sidebar={<SharedSidebar mode={mode} fixtureState="content" />}
      main={(
        <div data-testid="edge-menu-surface">
          {(['top-left', 'top-right', 'bottom-left', 'bottom-right'] as const).map(edge => (
            <ContextMenu key={edge}>
              <ContextMenuTrigger asChild>
                <button
                  type="button"
                  className={`fixture-edge-trigger fixture-edge-${edge}`}
                  data-testid={`edge-trigger-${edge}`}
                  aria-label={`Fixture ${edge}`}
                />
              </ContextMenuTrigger>
              <ContextMenuContent data-testid={`edge-menu-${edge}`}>
                <ContextMenuItem>Fixture menu action with a long label</ContextMenuItem>
                <ContextMenuItem>Secondary fixture action</ContextMenuItem>
              </ContextMenuContent>
            </ContextMenu>
          ))}
        </div>
      )}
    />
  );
};

const DialogSurface = () => {
  const [mode, setMode] = React.useState<VersionControlWorkbenchMode>('changes');
  const [open, setOpen] = React.useState(false);

  let dialogMain: React.ReactNode;
  if (dialogType === 'setup') {
    dialogMain = (
      <div className="fixture-dialog-surface" data-testid="fixture-setup">
        <VersionControlRepositorySetup
          target={{
            scopeKey: `${product}:fixture`,
            repository: {
              isGitRepo: false,
              currentBranch: null,
              remoteUrl: null,
              hasOrigin: false,
              hasLocalContent: false,
              canCloneSafely: true,
              canInitSafely: true,
              cloneBlockedReason: null,
            },
          }}
          capability={{ canMutate: true }}
          remoteEffects={{
            initialize: noopAsync,
            clone: noopAsync,
            discoverBranches: async () => ({ branches: ['main'], defaultBranch: 'main' }),
          }}
        />
      </div>
    );
  } else {
    dialogMain = (
      <div className="fixture-dialog-surface">
        <button type="button" data-testid="fixture-dialog-trigger" onClick={() => setOpen(true)}>
          Open fixture dialog
        </button>
        {dialogType === 'form' ? (
          <VersionControlRenameBranchDialog
            open={open}
            branch={longBranch}
            onOpenChange={setOpen}
            onConfirm={noopAsync}
          />
        ) : (
          <VersionControlDiscardDialog
            open={open}
            paths={[longPath, ...unstagedFiles.map(file => file.path)]}
            onOpenChange={setOpen}
            onConfirm={noopAsync}
          />
        )}
      </div>
    );
  }

  return (
    <ProductPresentation
      mode={mode}
      onModeChange={setMode}
      sidebar={<SharedSidebar mode={mode} fixtureState="content" />}
      main={dialogMain}
    />
  );
};

const EntrySurface = () => {
  const { t } = useI18n();
  const [entryState, setEntryState] = React.useState(initialEntryState);
  const [actionLog, setActionLog] = React.useState<WorkspaceEntryActionId[]>([]);
  const navigation = (
    <header
      className="flex h-10 shrink-0 items-center border-b border-border bg-card px-4"
      data-testid="entry-navigation"
    >
      <span className="text-sm font-medium">{t('common.entry.stages.label')}</span>
    </header>
  );

  const projection = projectWorkspaceEntry({
    identity: { status: 'authenticated' },
    workspace: { status: 'ready', canCreate: false },
    execution: entryState === 'stopped'
      ? {
          status: 'stopped',
          reasonCode: 'WORKSPACE_RUNTIME_STOPPED',
          allowedActions: ['start', 'rebuild', 'return'],
        }
      : entryState === 'uncertain'
        ? {
            status: 'uncertain',
            reasonCode: 'WORKSPACE_AVAILABILITY_UNCERTAIN',
            allowedActions: ['refresh', 'return'],
          }
        : entryState === 'ready'
          ? { status: 'ready', allowedActions: [] }
          : { status: 'checking', allowedActions: [] },
  });

  const handleAction = (action: WorkspaceEntryActionId) => {
    setActionLog(current => [...current, action]);
    if (action === 'start' || action === 'rebuild' || action === 'refresh') {
      setEntryState('ready');
    }
  };

  return (
    <div className="h-screen w-screen" data-testid="entry-surface">
      <EntryFrame
        isPending={entryState !== 'ready'}
        transitionKey="entry-fixture"
        projection={projection}
        navigationSlot={navigation}
        onAction={handleAction}
      >
        <div className="flex h-full min-h-screen flex-col bg-background">
          {navigation}
          <main className="flex min-h-0 flex-1 flex-col gap-3 p-6" data-testid="entry-ready-content">
            <h1 className="text-xl font-semibold">{t('common.entry.descriptions.execution')}</h1>
            <div data-testid="entry-action-log" data-actions={actionLog.join(',')} />
          </main>
        </div>
      </EntryFrame>
    </div>
  );
};

const FixtureApp = () => {
  if (surface === 'entry') return <EntrySurface />;
  if (surface === 'menu') return <EdgeMenuSurface />;
  if (surface === 'dialog') return <DialogSurface />;
  return <WorkbenchSurface />;
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nProvider>
      <FixtureApp />
    </I18nProvider>
  </React.StrictMode>,
);
