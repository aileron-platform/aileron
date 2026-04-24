import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  FileDiff,
  GitBranch,
  History,
  Loader2,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { useTaskProgress } from '@/shared/hooks/useTaskProgress';
import { TaskProgressDialog } from '@/shared/components/task-progress/TaskProgressDialog';
import {
  getRebuildProgress,
  type GitRepositoryStatus,
  rebuildTemplates,
  templateVersionControlApi,
} from '@/shared/services/templateGitApi';
import type {
  VersionControlBranch,
  VersionControlChangesResponse,
  VersionControlCommitSummary,
  VersionControlFileChange,
  VersionControlStatus,
} from '@/shared/types/versionControl';
import {
  VersionControlChangesSidebar,
  VersionControlHistorySidebar,
  VersionControlLayout,
  VersionControlMainDiff,
  VersionControlModeRail,
  type VersionControlActionMenuItem,
} from '@/shared/components/version-control';

type FileGroup = 'staged' | 'unstaged';
type VersionControlMode = 'changes' | 'history';

const emptyChanges: VersionControlChangesResponse = {
  staged: [],
  unstaged: [],
  untracked: [],
};

interface TemplateRegistryVersionControlTabProps {
  repositoryStatus: GitRepositoryStatus | null;
  onOpenRemoteSettings: () => void;
}

export const TemplateRegistryVersionControlTab: React.FC<TemplateRegistryVersionControlTabProps> = ({
  repositoryStatus,
  onOpenRemoteSettings,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [mode, setMode] = useState<VersionControlMode>('changes');
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [status, setStatus] = useState<VersionControlStatus | null>(null);
  const [changes, setChanges] = useState<VersionControlChangesResponse>(emptyChanges);
  const [branches, setBranches] = useState<VersionControlBranch[]>([]);
  const [commits, setCommits] = useState<VersionControlCommitSummary[]>([]);
  const [commitFiles, setCommitFiles] = useState<VersionControlFileChange[]>([]);
  const [selectedFile, setSelectedFile] = useState<VersionControlFileChange | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<FileGroup>('unstaged');
  const [selectedCommitId, setSelectedCommitId] = useState<string | null>(null);
  const [selectedCommitFile, setSelectedCommitFile] = useState<VersionControlFileChange | null>(null);
  const [diffContent, setDiffContent] = useState('');
  const [diffError, setDiffError] = useState<string | null>(null);
  const [isDiffLoading, setIsDiffLoading] = useState(false);
  const [registryIndexStale, setRegistryIndexStale] = useState(false);
  const [rebuildProgressDialogOpen, setRebuildProgressDialogOpen] = useState(false);

  const {
    progress: rebuildProgress,
    startPolling: startRebuildPolling,
    resetProgress: resetRebuildProgress,
  } = useTaskProgress(null, getRebuildProgress, {
    onComplete: (result) => {
      if (result.status === 'completed') {
        setRegistryIndexStale(false);
        void loadData();
      }
    },
  });

  const stagedFiles = useMemo(
    () => changes.staged.map((file) => ({ ...file, changeType: 'staged' as const })),
    [changes.staged],
  );
  const allUnstagedFiles = useMemo(
    () => [
      ...changes.unstaged.map((file) => ({ ...file, changeType: 'unstaged' as const })),
      ...changes.untracked.map((file) => ({ ...file, changeType: 'untracked' as const })),
    ],
    [changes.unstaged, changes.untracked],
  );
  const activeBranch = useMemo(
    () => branches.find((branch) => branch.isActive)?.name ?? status?.branch ?? '',
    [branches, status?.branch],
  );
  const changeCount = stagedFiles.length + allUnstagedFiles.length;
  const selectedDiffFile = mode === 'history' ? selectedCommitFile : selectedFile;

  const loadData = useCallback(async () => {
    if (!repositoryStatus?.isGitRepo) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const [nextStatus, nextChanges, nextBranches, nextCommits] = await Promise.all([
        templateVersionControlApi.getStatus(),
        templateVersionControlApi.getChanges(),
        templateVersionControlApi.getBranches(),
        templateVersionControlApi.getCommits(),
      ]);
      setStatus(nextStatus);
      setChanges(nextChanges);
      setBranches(nextBranches);
      setCommits(nextCommits.items ?? []);
    } catch (error) {
      toast({
        title: t('template.center.settings.versionControl.toasts.loadFailed.title'),
        description: error instanceof Error
          ? error.message
          : t('template.center.settings.versionControl.toasts.loadFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [repositoryStatus?.isGitRepo, t, toast]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const loadDiff = async () => {
      if (mode === 'history') {
        setDiffError(null);
        setIsDiffLoading(false);
        setDiffContent(selectedCommitFile?.patch || selectedCommitFile?.diff || '');
        return;
      }

      if (!selectedFile) {
        setDiffContent('');
        setDiffError(null);
        return;
      }

      setIsDiffLoading(true);
      setDiffError(null);
      try {
        const head = selectedGroup === 'staged' ? 'INDEX' : 'WORKTREE';
        const response = await templateVersionControlApi.getDiff(selectedFile.path, head);
        setDiffContent(response.patch || response.diff || '');
      } catch (error) {
        setDiffError(error instanceof Error ? error.message : t('shared.versionControl.diff.loadFailed'));
        setDiffContent('');
      } finally {
        setIsDiffLoading(false);
      }
    };

    void loadDiff();
  }, [mode, selectedCommitFile, selectedFile, selectedGroup, t]);

  useEffect(() => {
    const loadCommitFiles = async () => {
      if (!selectedCommitId) {
        setCommitFiles([]);
        setSelectedCommitFile(null);
        return;
      }
      try {
        const response = await templateVersionControlApi.getCommitFiles(selectedCommitId);
        setCommitFiles(response.files ?? []);
        setSelectedCommitFile(null);
      } catch {
        setCommitFiles([]);
        setSelectedCommitFile(null);
      }
    };

    void loadCommitFiles();
  }, [selectedCommitId]);

  const runMutation = useCallback(async (
    action: () => Promise<unknown>,
    options?: { staleRegistry?: boolean; successKey?: string },
  ) => {
    setIsMutating(true);
    try {
      await action();
      if (options?.staleRegistry) {
        setRegistryIndexStale(true);
      }
      if (options?.successKey) {
        toast({ title: t(options.successKey), variant: 'success' });
      }
      await loadData();
    } catch (error) {
      toast({
        title: t('template.center.settings.versionControl.toasts.operationFailed.title'),
        description: error instanceof Error
          ? error.message
          : t('template.center.settings.versionControl.toasts.operationFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsMutating(false);
    }
  }, [loadData, t, toast]);

  const handleModeChange = (nextMode: string) => {
    const normalizedMode = nextMode as VersionControlMode;
    setMode(normalizedMode);
    if (normalizedMode === 'changes') {
      setSelectedCommitFile(null);
    } else {
      setSelectedFile(null);
    }
  };

  const handleFileSelect = (file: VersionControlFileChange, group: FileGroup) => {
    setSelectedFile(file);
    setSelectedGroup(group);
  };

  const handleStageToggle = (file: VersionControlFileChange, group: FileGroup) => {
    const paths = [file.path];
    void runMutation(() => (
      group === 'staged'
        ? templateVersionControlApi.unstage(paths)
        : templateVersionControlApi.stage(paths)
    ));
  };

  const handleDiscard = (file: VersionControlFileChange) => {
    const confirmed = window.confirm(t('template.center.settings.versionControl.confirmDiscard', { path: file.path }));
    if (!confirmed) {
      return;
    }
    void runMutation(() => templateVersionControlApi.discard([file.path]), { staleRegistry: true });
    if (selectedFile?.path === file.path) {
      setSelectedFile(null);
    }
  };

  const handleCommit = ({ message }: { message: string }) => {
    void runMutation(() => templateVersionControlApi.commit(message), {
      successKey: 'template.center.settings.versionControl.toasts.commitSuccess.title',
    });
    setSelectedFile(null);
  };

  const handleRemoteAction = (action: 'fetch' | 'pull' | 'push') => {
    const staleRegistry = action === 'pull';
    void runMutation(
      () => templateVersionControlApi[action]({ branch: activeBranch || undefined }),
      {
        staleRegistry,
        successKey: `template.center.settings.versionControl.toasts.${action}Success.title`,
      },
    );
  };

  const handleCheckout = (branch: string) => {
    if (!branch || branch === activeBranch) {
      return;
    }
    void runMutation(() => templateVersionControlApi.checkoutBranch(branch, { create: false }), {
      staleRegistry: true,
      successKey: 'template.center.settings.versionControl.toasts.checkoutSuccess.title',
    });
    setSelectedFile(null);
  };

  const handleRebuild = async () => {
    try {
      const result = await rebuildTemplates();
      if (result.success && result.task_id) {
        setRebuildProgressDialogOpen(true);
        startRebuildPolling(result.task_id);
      } else {
        toast({
          title: t('template.center.settings.versionControl.toasts.rebuildFailed.title'),
          description: result.error || t('template.center.settings.versionControl.toasts.rebuildFailed.description'),
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t('template.center.settings.versionControl.toasts.rebuildFailed.title'),
        description: error instanceof Error
          ? error.message
          : t('template.center.settings.versionControl.toasts.rebuildFailed.description'),
        variant: 'destructive',
      });
    }
  };

  const handleStageAll = () => {
    void runMutation(() => templateVersionControlApi.stage(allUnstagedFiles.map((file) => file.path)));
  };

  const handleUnstageAll = () => {
    void runMutation(() => templateVersionControlApi.unstage(stagedFiles.map((file) => file.path)));
  };

  const actionItems: VersionControlActionMenuItem[] = [
    { id: 'refresh', onClick: () => void loadData() },
    {
      id: 'fetch',
      onClick: () => handleRemoteAction('fetch'),
      disabled: !repositoryStatus?.hasOrigin,
    },
    {
      id: 'pull',
      onClick: () => handleRemoteAction('pull'),
      disabled: !repositoryStatus?.hasOrigin,
    },
    {
      id: 'push',
      onClick: () => handleRemoteAction('push'),
      disabled: !repositoryStatus?.hasOrigin,
    },
  ];

  const changesSidebar = (
    <VersionControlChangesSidebar
      branches={branches}
      currentBranch={activeBranch}
      actions={actionItems}
      stagedFiles={stagedFiles}
      unstagedFiles={allUnstagedFiles}
      selectedStagedPath={selectedGroup === 'staged' ? selectedFile?.path : null}
      selectedUnstagedPath={selectedGroup === 'unstaged' ? selectedFile?.path : null}
      isMutating={isMutating}
      onBranchChange={handleCheckout}
      onCommit={handleCommit}
      onFileSelect={handleFileSelect}
      onStageToggle={handleStageToggle}
      onDiscard={handleDiscard}
      onStageAll={handleStageAll}
      onUnstageAll={handleUnstageAll}
    />
  );

  const historySidebar = (
    <VersionControlHistorySidebar
      commits={commits}
      files={commitFiles}
      selectedCommitId={selectedCommitId}
      selectedFile={selectedCommitFile}
      onCommitSelect={(commit) => setSelectedCommitId(commit.id)}
      onFileSelect={setSelectedCommitFile}
    />
  );

  const modeRail = (
    <VersionControlModeRail
      title={t('template.center.settings.versionControl.mode.title')}
      titleIcon={GitBranch}
      activeId={mode}
      onChange={handleModeChange}
      items={[
        {
          id: 'changes',
          label: t('template.center.settings.versionControl.mode.fileChanges'),
          icon: FileDiff,
          count: changeCount,
        },
        {
          id: 'history',
          label: t('template.center.settings.versionControl.mode.commitHistory'),
          icon: History,
          count: commits.length,
        },
      ]}
      footer={(
        <div className="space-y-2 text-xs text-muted-foreground">
          {!repositoryStatus.hasOrigin && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-amber-800">
              {t('template.center.settings.versionControl.remoteMissing.inline')}
            </div>
          )}
          <Button variant="outline" size="sm" className="mt-1 h-8 w-full" onClick={handleRebuild}>
            <RotateCcw className="mr-2 h-4 w-4" />
            {t('template.center.settings.versionControl.actions.rebuild')}
          </Button>
        </div>
      )}
    />
  );

  if (isLoading) {
    return (
      <div className="flex h-72 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!repositoryStatus?.isGitRepo) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6">
        <div className="w-full max-w-xl space-y-4 rounded-lg border border-border bg-background p-6 text-center">
          <GitBranch className="mx-auto h-10 w-10 text-muted-foreground" />
          <div className="space-y-2">
            <h3 className="text-base font-semibold">
              {t('template.center.settings.versionControl.setupRequired.title')}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t('template.center.settings.versionControl.setupRequired.description')}
            </p>
          </div>
          <Button onClick={onOpenRemoteSettings}>
            {t('template.center.settings.versionControl.setupRequired.action')}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {registryIndexStale && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between gap-3">
            <span>{t('template.center.settings.versionControl.registryStale.description')}</span>
            <Button size="sm" variant="outline" onClick={handleRebuild}>
              <RotateCcw className="mr-2 h-4 w-4" />
              {t('template.center.settings.versionControl.actions.rebuild')}
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <VersionControlLayout
        className="min-h-0 flex-1"
        modeRail={modeRail}
        sidebar={mode === 'changes' ? changesSidebar : historySidebar}
        main={(
          <VersionControlMainDiff
            selectedPath={selectedDiffFile?.path ?? null}
            diffContent={diffContent}
            isLoading={isDiffLoading}
            error={diffError}
            emptyKey={mode === 'changes'
              ? 'shared.versionControl.main.selectFile'
              : 'shared.versionControl.main.selectCommitFile'}
          />
        )}
      />

      <TaskProgressDialog
        open={rebuildProgressDialogOpen}
        onOpenChange={(open) => {
          setRebuildProgressDialogOpen(open);
          if (!open) {
            resetRebuildProgress();
          }
        }}
        progress={rebuildProgress}
        title={t('template.center.settings.versionControl.rebuildProgressTitle')}
      />
    </div>
  );
};

export default TemplateRegistryVersionControlTab;
