import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FileDiff, GitBranch, History, Loader2, ShieldCheck } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  VersionControlChangesSidebar,
  VersionControlHistorySidebar,
  VersionControlLayout,
  VersionControlMainDiff,
  VersionControlModeRail,
  VersionControlCreateBranchDialog,
  VersionControlRemoteSettingsDialog,
  type VersionControlActionMenuItem,
  type VersionControlCreateBranchPayload,
} from '@/shared/components/version-control';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  enableKnowledgeBaseGitLfs,
  enableKnowledgeBaseGitRepository,
  getKnowledgeBaseGitRepositoryStatus,
  knowledgeBaseVersionControlApi,
} from '@/features/knowledge-base/api/knowledgeBaseApi';
import type {
  KnowledgeBaseGitRepositoryStatus,
  KnowledgeBaseRole,
} from '@/shared/types/knowledgeBase';
import type {
  VersionControlBranch,
  VersionControlChangesResponse,
  VersionControlCommitSummary,
  VersionControlFileChange,
  VersionControlStatus,
} from '@/shared/types/versionControl';

interface KnowledgeBaseVersionControlTabProps {
  knowledgeBaseId: string;
  accessRole: KnowledgeBaseRole;
  versionControlEnabled?: boolean;
  gitLfsEnabled?: boolean;
}

type FileGroup = 'staged' | 'unstaged';
type VersionControlMode = 'changes' | 'history';

const emptyChanges: VersionControlChangesResponse = {
  staged: [],
  unstaged: [],
  untracked: [],
};

const canManageGit = (role: KnowledgeBaseRole): boolean => role === 'owner' || role === 'manager';
const canWriteGit = (role: KnowledgeBaseRole): boolean => role === 'owner' || role === 'manager' || role === 'editor';

const blobToContextPatch = (path: string, content: string): string => {
  const lines = content.split('\n');
  const lineCount = Math.max(lines.length, 1);
  return [
    `@@ -1,${lineCount} +1,${lineCount} @@ ${path}`,
    ...lines.map((line) => ` ${line}`),
  ].join('\n');
};

export const KnowledgeBaseVersionControlTab: React.FC<KnowledgeBaseVersionControlTabProps> = ({
  knowledgeBaseId,
  accessRole,
  gitLfsEnabled = false,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [mode, setMode] = useState<VersionControlMode>('changes');
  const [repositoryStatus, setRepositoryStatus] = useState<KnowledgeBaseGitRepositoryStatus | null>(null);
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
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [defaultBranch, setDefaultBranch] = useState('main');
  const [enableLfs, setEnableLfs] = useState(gitLfsEnabled);
  const [createBranchOpen, setCreateBranchOpen] = useState(false);
  const [remoteSettingsOpen, setRemoteSettingsOpen] = useState(false);

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
    () => branches.find((branch) => branch.isActive)?.name ?? status?.branch ?? repositoryStatus?.currentBranch ?? '',
    [branches, repositoryStatus?.currentBranch, status?.branch],
  );
  const changeCount = stagedFiles.length + allUnstagedFiles.length;
  const selectedDiffFile = mode === 'history' ? selectedCommitFile : selectedFile;

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const repo = await getKnowledgeBaseGitRepositoryStatus(knowledgeBaseId);
      setRepositoryStatus(repo);

      if (!repo.isGitRepo) {
        setStatus(null);
        setChanges(emptyChanges);
        setBranches([]);
        setCommits([]);
        return;
      }

      const [nextStatus, nextChanges, nextBranches, nextCommits] = await Promise.all([
        knowledgeBaseVersionControlApi.getStatus(knowledgeBaseId),
        knowledgeBaseVersionControlApi.getChanges(knowledgeBaseId),
        knowledgeBaseVersionControlApi.getBranches(knowledgeBaseId),
        knowledgeBaseVersionControlApi.getCommits(knowledgeBaseId),
      ]);
      setStatus(nextStatus);
      setChanges(nextChanges);
      setBranches(nextBranches);
      setCommits(nextCommits.items ?? []);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : t('knowledgeBase.versionControl.loadFailed');
      setError(message);
      toast({
        title: t('knowledgeBase.versionControl.toasts.loadFailed.title'),
        description: message,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [knowledgeBaseId, t, toast]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const loadDiff = async () => {
      if (mode === 'history') {
        if (!selectedCommitFile) {
          setDiffContent('');
          setDiffError(null);
          setIsDiffLoading(false);
          return;
        }

        const inlinePatch = selectedCommitFile.patch || selectedCommitFile.diff;
        if (inlinePatch) {
          setDiffError(null);
          setIsDiffLoading(false);
          setDiffContent(inlinePatch);
          return;
        }

        setIsDiffLoading(true);
        setDiffError(null);
        try {
          const response = await knowledgeBaseVersionControlApi.getBlob(
            knowledgeBaseId,
            selectedCommitFile.path,
            selectedCommitId,
          );
          setDiffContent(blobToContextPatch(response.path, response.content));
        } catch (blobLoadError) {
          setDiffError(blobLoadError instanceof Error ? blobLoadError.message : t('shared.versionControl.diff.loadFailed'));
          setDiffContent('');
        } finally {
          setIsDiffLoading(false);
        }
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
        const response = await knowledgeBaseVersionControlApi.getDiff(knowledgeBaseId, selectedFile.path, head);
        setDiffContent(response.patch || response.diff || '');
      } catch (diffLoadError) {
        setDiffError(diffLoadError instanceof Error ? diffLoadError.message : t('shared.versionControl.diff.loadFailed'));
        setDiffContent('');
      } finally {
        setIsDiffLoading(false);
      }
    };

    void loadDiff();
  }, [knowledgeBaseId, mode, selectedCommitFile, selectedCommitId, selectedFile, selectedGroup, t]);

  useEffect(() => {
    const loadCommitFiles = async () => {
      if (!selectedCommitId) {
        setCommitFiles([]);
        setSelectedCommitFile(null);
        return;
      }
      try {
        const response = await knowledgeBaseVersionControlApi.getCommitFiles(knowledgeBaseId, selectedCommitId);
        setCommitFiles(response.files ?? []);
        setSelectedCommitFile(null);
      } catch {
        setCommitFiles([]);
        setSelectedCommitFile(null);
      }
    };

    void loadCommitFiles();
  }, [knowledgeBaseId, selectedCommitId]);

  const runMutation = useCallback(async (
    action: () => Promise<unknown>,
    options?: { successKey?: string },
  ) => {
    setIsMutating(true);
    try {
      await action();
      if (options?.successKey) {
        toast({ title: t(options.successKey), variant: 'success' });
      }
      await loadData();
    } catch (mutationError) {
      toast({
        title: t('knowledgeBase.versionControl.toasts.operationFailed.title'),
        description: mutationError instanceof Error
          ? mutationError.message
          : t('knowledgeBase.versionControl.toasts.operationFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsMutating(false);
    }
  }, [loadData, t, toast]);

  const handleEnable = useCallback(async () => {
    setIsMutating(true);
    setError(null);
    try {
      await enableKnowledgeBaseGitRepository(knowledgeBaseId, {
        defaultBranch: defaultBranch.trim() || 'main',
        initialMessage: t('knowledgeBase.versionControl.setup.initialCommitMessage'),
      });
      if (enableLfs && !gitLfsEnabled) {
        await enableKnowledgeBaseGitLfs(knowledgeBaseId);
      }
      toast({
        title: t('knowledgeBase.versionControl.toasts.enableSuccess.title'),
        description: t('knowledgeBase.versionControl.toasts.enableSuccess.description'),
        variant: 'success',
      });
      await loadData();
    } catch (enableError) {
      const message = enableError instanceof Error ? enableError.message : t('knowledgeBase.versionControl.toasts.enableFailed.description');
      setError(message);
      toast({
        title: t('knowledgeBase.versionControl.toasts.enableFailed.title'),
        description: message,
        variant: 'destructive',
      });
    } finally {
      setIsMutating(false);
    }
  }, [defaultBranch, enableLfs, gitLfsEnabled, knowledgeBaseId, loadData, t, toast]);

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
        ? knowledgeBaseVersionControlApi.unstage(knowledgeBaseId, paths)
        : knowledgeBaseVersionControlApi.stage(knowledgeBaseId, paths)
    ));
  };

  const handleDiscard = (file: VersionControlFileChange) => {
    const confirmed = window.confirm(t('knowledgeBase.versionControl.confirmDiscard', { path: file.path }));
    if (!confirmed) {
      return;
    }
    void runMutation(() => knowledgeBaseVersionControlApi.discard(knowledgeBaseId, [file.path]));
    if (selectedFile?.path === file.path) {
      setSelectedFile(null);
    }
  };

  const handleCommit = ({ message }: { message: string }) => {
    void runMutation(() => knowledgeBaseVersionControlApi.commit(knowledgeBaseId, message), {
      successKey: 'knowledgeBase.versionControl.toasts.commitSuccess.title',
    });
    setSelectedFile(null);
  };

  const handleRemoteAction = (action: 'fetch' | 'pull' | 'push') => {
    void runMutation(
      () => knowledgeBaseVersionControlApi[action](knowledgeBaseId, { branch: activeBranch || undefined }),
      { successKey: `knowledgeBase.versionControl.toasts.${action}Success.title` },
    );
  };

  const handleCheckout = (branch: string) => {
    if (!branch || branch === activeBranch) {
      return;
    }
    void runMutation(() => knowledgeBaseVersionControlApi.checkoutBranch(knowledgeBaseId, branch, { create: false }), {
      successKey: 'knowledgeBase.versionControl.toasts.checkoutSuccess.title',
    });
    setSelectedFile(null);
  };

  const handleCreateBranch = ({
    branch,
    startPoint,
    stashChanges,
  }: VersionControlCreateBranchPayload) => {
    if (!branch) {
      return;
    }
    void runMutation(() => knowledgeBaseVersionControlApi.checkoutBranch(knowledgeBaseId, branch, {
      create: true,
      startPoint,
      stashChanges: stashChanges ?? false,
    }), {
      successKey: 'knowledgeBase.versionControl.toasts.checkoutSuccess.title',
    });
    setCreateBranchOpen(false);
    setSelectedFile(null);
  };

  const handleSetRemoteUrl = (remoteUrl: string) => {
    const nextUrl = remoteUrl.trim();
    if (!nextUrl) {
      return;
    }
    void runMutation(() => knowledgeBaseVersionControlApi.setRemoteUrl(knowledgeBaseId, nextUrl), {
      successKey: 'knowledgeBase.versionControl.toasts.remoteUrlSuccess.title',
    });
  };

  const handleStageAll = () => {
    void runMutation(() => knowledgeBaseVersionControlApi.stage(knowledgeBaseId, allUnstagedFiles.map((file) => file.path)));
  };

  const handleUnstageAll = () => {
    void runMutation(() => knowledgeBaseVersionControlApi.unstage(knowledgeBaseId, stagedFiles.map((file) => file.path)));
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {t('knowledgeBase.versionControl.loading')}
      </div>
    );
  }

  if (!repositoryStatus?.isGitRepo) {
    return (
      <GitEnableCard
        accessRole={accessRole}
        defaultBranch={defaultBranch}
        enableLfs={enableLfs}
        error={error}
        isMutating={isMutating}
        onDefaultBranchChange={setDefaultBranch}
        onEnableLfsChange={setEnableLfs}
        onEnable={handleEnable}
      />
    );
  }

  const actionItems: VersionControlActionMenuItem[] = [
    { id: 'refresh', onClick: () => void loadData() },
    ...(canManageGit(accessRole)
      ? [{ id: 'remoteSettings' as const, onClick: () => setRemoteSettingsOpen(true) }]
      : []),
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
      onCreateBranch={canWriteGit(accessRole) ? () => setCreateBranchOpen(true) : undefined}
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
      title={t('knowledgeBase.versionControl.mode.title')}
      titleIcon={GitBranch}
      activeId={mode}
      onChange={handleModeChange}
      items={[
        {
          id: 'changes',
          label: t('shared.versionControl.mode.fileChanges'),
          icon: FileDiff,
          count: changeCount,
        },
        {
          id: 'history',
          label: t('shared.versionControl.mode.commitHistory'),
          icon: History,
          count: commits.length,
        },
      ]}
    />
  );

  return (
    <>
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
      <VersionControlCreateBranchDialog
        open={createBranchOpen}
        onOpenChange={setCreateBranchOpen}
        onCreate={handleCreateBranch}
        isCreating={isMutating}
        supportsStartPoint
        supportsStashBeforeCheckout
      />
      <VersionControlRemoteSettingsDialog
        open={remoteSettingsOpen}
        onOpenChange={setRemoteSettingsOpen}
        repository={{
          isRepositoryInitialized: Boolean(repositoryStatus?.isGitRepo),
          currentBranch: activeBranch || repositoryStatus?.currentBranch,
          remoteUrl: repositoryStatus?.remoteUrl ?? null,
          hasOrigin: repositoryStatus?.hasOrigin ?? false,
          hasLocalContent: repositoryStatus?.hasLocalContent ?? false,
          canCloneSafely: false,
          canInitSafely: false,
        }}
        capabilities={{
          canConfigureRemote: canManageGit(accessRole),
          supportsRemoteInit: false,
          supportsRemoteClone: false,
        }}
        onSaveRemoteUrl={handleSetRemoteUrl}
        isSavingRemoteUrl={isMutating}
      />
    </>
  );
};

const GitEnableCard: React.FC<{
  accessRole: KnowledgeBaseRole;
  defaultBranch: string;
  enableLfs: boolean;
  error: string | null;
  isMutating: boolean;
  onDefaultBranchChange: (value: string) => void;
  onEnableLfsChange: (value: boolean) => void;
  onEnable: () => void;
}> = ({
  accessRole,
  defaultBranch,
  enableLfs,
  error,
  isMutating,
  onDefaultBranchChange,
  onEnableLfsChange,
  onEnable,
}) => {
  const { t } = useI18n();
  const manager = canManageGit(accessRole);

  return (
    <div className="h-full overflow-auto p-6">
      <div className="space-y-6">
        <Card>
          <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2 text-base">
                <GitBranch className="h-4 w-4 text-sky-600" />
                {t('knowledgeBase.versionControl.setup.title')}
              </CardTitle>
              <CardDescription>{t('knowledgeBase.versionControl.setup.description')}</CardDescription>
            </div>
            <Button type="button" disabled={!manager || isMutating} onClick={onEnable}>
              {isMutating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitBranch className="mr-2 h-4 w-4" />}
              {isMutating
                ? t('knowledgeBase.versionControl.setup.enabling')
                : t('knowledgeBase.versionControl.setup.enableAction')}
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertTitle>{t('knowledgeBase.versionControl.errorTitle')}</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="grid gap-2">
              <Label htmlFor="kb-git-default-branch">{t('knowledgeBase.versionControl.setup.defaultBranch')}</Label>
              <Input
                id="kb-git-default-branch"
                value={defaultBranch}
                disabled={!manager || isMutating}
                onChange={(event) => onDefaultBranchChange(event.target.value)}
                placeholder={t('knowledgeBase.versionControl.setup.defaultBranchPlaceholder')}
              />
            </div>
            <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
              <Checkbox
                checked={enableLfs}
                disabled={!manager || isMutating}
                onCheckedChange={(checked) => onEnableLfsChange(checked === true)}
              />
              <span className="space-y-1">
                <span className="block font-medium">{t('knowledgeBase.versionControl.setup.enableLfs')}</span>
                <span className="block text-muted-foreground">{t('knowledgeBase.versionControl.setup.enableLfsDescription')}</span>
              </span>
            </label>
            {!manager && (
              <Alert>
                <ShieldCheck className="h-4 w-4" />
                <AlertTitle>{t('knowledgeBase.versionControl.setup.permissionTitle')}</AlertTitle>
                <AlertDescription>{t('knowledgeBase.versionControl.setup.permissionDescription')}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default KnowledgeBaseVersionControlTab;
