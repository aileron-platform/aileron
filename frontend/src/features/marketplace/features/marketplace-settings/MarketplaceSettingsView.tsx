import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  AlertTriangle,
  Clock3,
  CheckCircle2,
  FileDiff,
  GitBranch,
  History,
  KeyRound,
  Save,
  Settings,
  UserRound,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Tabs, TabsContent } from '@/shared/components/ui/tabs';
import { Textarea } from '@/shared/components/ui/textarea';
import { TopTabsBar, TopTabsList, TopTabsTrigger } from '@/shared/components/navigation/TopTabs';
import { useI18n } from '@/shared/hooks/useI18n';
import { useApp } from '@/app/providers/AppProvider';
import { ApiError, apiClient } from '@/shared/api/apiClient';
import type {
  MarketplaceRegistryGitFileChange,
  MarketplaceRegistryGitStatus,
  MarketplaceRegistryRepositoryStatus,
  MarketplaceRegistryRootMetadataSavePayload,
} from '@/shared/types/marketplace';
import type {
  UserSettings,
  UserSettingsResponse,
  UserSettingsSSH,
} from '@/shared/types/user';
import type {
  VersionControlChangesResponse,
  VersionControlCommitSummary,
  VersionControlFileChange,
} from '@/shared/types/versionControl';
import {
  VersionControlChangesSidebar,
  VersionControlHistorySidebar,
  VersionControlLayout,
  VersionControlMainDiff,
  VersionControlModeRail,
  VersionControlRemoteSettingsDialog,
  useVersionControlFileSelection,
  type VersionControlActionMenuItem,
  type VersionControlFileGroup,
  type VersionControlRemoteSettingsState,
} from '@/shared/components/version-control';
import {
  cloneRegistry,
  commitRegistryChanges,
  fetchRegistry,
  getRegistryCommitFileDiff,
  getRegistryCommitFiles,
  getRegistryCommits,
  getRegistryFileDiff,
  getRegistryGitStatus,
  getRegistryRepository,
  getRegistrySettings,
  initializeRegistryGit,
  pullRegistry,
  pushRegistry,
  saveRegistrySettings,
  setRegistryRemote,
  stageRegistryFiles,
  unstageRegistryFiles,
} from '../../api/marketplaceApi';

export const MarketplaceSettingsView: React.FC = () => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { state: appState } = useApp();
  const userId = appState.user.id;
  const [activeTab, setActiveTab] = React.useState('general');
  const [gitUserName, setGitUserName] = React.useState('Marketplace Registry');
  const [gitUserEmail, setGitUserEmail] = React.useState('');
  const [userSettings, setUserSettings] = React.useState<UserSettings | null>(null);
  const [sshKeys, setSshKeys] = React.useState<UserSettingsSSH>({
    publicKey: null,
    privateKey: null,
    fingerprint: null,
    lastRotatedAt: null,
  });
  const [showPrivateKey, setShowPrivateKey] = React.useState(false);
  const [registryRepository, setRegistryRepository] = React.useState<MarketplaceRegistryRepositoryStatus | null>(null);
  const [registryRootPath, setRegistryRootPath] = React.useState('');
  const [rootMetadata, setRootMetadata] = React.useState<MarketplaceRootMetadata>({
    name: '',
    maintainerName: '',
    maintainerEmail: '',
    description: '',
  });
  const [isSavingGeneral, setIsSavingGeneral] = React.useState(false);

  React.useEffect(() => {
    let isActive = true;
    void getRegistrySettings().then(settings => {
      if (!isActive) return;
      setRegistryRootPath(settings.rootPath);
      setRootMetadata({
        name: settings.displayName,
        maintainerName: settings.maintainerName,
        maintainerEmail: settings.maintainerEmail,
        description: settings.description ?? '',
      });
      setGitUserName(settings.gitUserName ?? '');
      setGitUserEmail(settings.gitUserEmail ?? '');
    });
    void getRegistryRepository().then(repository => {
      if (!isActive) return;
      setRegistryRepository(repository);
    });
    return () => {
      isActive = false;
    };
  }, []);

  React.useEffect(() => {
    if (!userId) return;
    let isActive = true;
    void apiClient.get<UserSettingsResponse>(`/users/${userId}/settings`).then(response => {
      if (!isActive) return;
      setUserSettings(response.data);
      setSshKeys(response.data.ssh);
    });
    return () => {
      isActive = false;
    };
  }, [userId]);

  const handleSaveGeneral = async () => {
    setIsSavingGeneral(true);
    try {
      const result = await saveRegistrySettings({
        name: rootMetadata.name,
        owner: {
          name: rootMetadata.maintainerName,
          email: rootMetadata.maintainerEmail,
        },
        description: rootMetadata.description,
      });
      setRegistryRootPath(result.settings.rootPath);
      setRootMetadata({
        name: result.settings.displayName,
        maintainerName: result.settings.maintainerName,
        maintainerEmail: result.settings.maintainerEmail,
        description: result.settings.description ?? '',
      });
    } finally {
      setIsSavingGeneral(false);
    }
  };

  const handleSaveSshKeys = async () => {
    if (!userId || !userSettings) return;
    const response = await apiClient.put<UserSettingsResponse>(`/users/${userId}/settings`, {
      ...userSettings,
      ssh: sshKeys,
    });
    setUserSettings(response.data);
    setSshKeys(response.data.ssh);
  };

  const handleGenerateSshKey = async () => {
    if (!userId) return;
    const response = await apiClient.post<{
      publicKey: string;
      privateKey: string;
      fingerprint: string;
      generatedAt: string;
    }>(`/users/${userId}/ssh-keys/generate`);
    const nextSshKeys = {
      publicKey: response.publicKey,
      privateKey: response.privateKey,
      fingerprint: response.fingerprint,
      lastRotatedAt: response.generatedAt,
    };
    setSshKeys(nextSshKeys);
    setUserSettings(previous => previous ? { ...previous, ssh: nextSshKeys } : previous);
  };

  const copyToClipboard = (value: string | null) => {
    if (!value) return;
    void navigator.clipboard?.writeText(value);
  };

  const handleRepositoryChange = React.useCallback((repository: MarketplaceRegistryRepositoryStatus) => {
    setRegistryRepository(repository);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('marketplace.settings.title')}
        icon={Settings}
        info={(
          <div className="text-xs text-muted-foreground">
            {t('marketplace.settings.description')}
          </div>
        )}
        actions={(
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => navigate('/marketplace/packages')}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              {t('marketplace.common.actions.back')}
            </Button>
          </div>
        )}
      />

      <div className="flex-1 overflow-hidden">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex h-full flex-col">
          <TopTabsBar>
            <TopTabsList>
              <TopTabsTrigger value="general">
                <Settings className="h-4 w-4" />
                {t('marketplace.settings.tabs.general')}
              </TopTabsTrigger>
              <TopTabsTrigger value="versionControl">
                <GitBranch className="h-4 w-4" />
                {t('marketplace.settings.tabs.versionControl')}
              </TopTabsTrigger>
              <TopTabsTrigger value="gitUser">
                <UserRound className="h-4 w-4" />
                {t('marketplace.settings.tabs.gitUser')}
              </TopTabsTrigger>
              <TopTabsTrigger value="sshKeys">
                <KeyRound className="h-4 w-4" />
                {t('marketplace.settings.tabs.sshKeys')}
              </TopTabsTrigger>
              <TopTabsTrigger value="activity">
                <Clock3 className="h-4 w-4" />
                {t('marketplace.settings.tabs.activity')}
              </TopTabsTrigger>
            </TopTabsList>
          </TopTabsBar>

          <TabsContent value="general" className="flex-1 overflow-auto !m-0 !p-0">
            <div className="mx-auto w-full max-w-7xl p-6">
              <MarketplaceGeneralTab
                metadata={rootMetadata}
                rootPath={registryRootPath}
                isSaving={isSavingGeneral}
                onMetadataChange={setRootMetadata}
                onSave={() => void handleSaveGeneral()}
              />
            </div>
          </TabsContent>

          <TabsContent value="versionControl" className="flex-1 overflow-hidden !m-0 !p-0">
            <MarketplaceVersionControlTab
              repository={registryRepository}
              onRepositoryChange={handleRepositoryChange}
            />
          </TabsContent>

          <TabsContent value="gitUser" className="flex-1 overflow-auto !m-0 !p-0">
            <div className="mx-auto w-full max-w-7xl p-6">
              <MarketplaceGitUserTab
                userName={gitUserName}
                userEmail={gitUserEmail}
                onUserNameChange={setGitUserName}
                onUserEmailChange={setGitUserEmail}
              />
            </div>
          </TabsContent>

          <TabsContent value="sshKeys" className="flex-1 overflow-auto !m-0 !p-0">
            <div className="mx-auto w-full max-w-7xl p-6">
              <MarketplaceSshKeysTab
                sshKeys={sshKeys}
                showPrivateKey={showPrivateKey}
                onSshKeysChange={setSshKeys}
                onShowPrivateKeyChange={setShowPrivateKey}
                onGenerateSshKey={() => void handleGenerateSshKey()}
                onSaveSshKeys={() => void handleSaveSshKeys()}
                onCopy={copyToClipboard}
              />
            </div>
          </TabsContent>

          <TabsContent value="activity" className="flex-1 overflow-auto !m-0 !p-0">
            <div className="mx-auto w-full max-w-7xl p-6">
              <MarketplaceActivityTab />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

interface MarketplaceRootMetadata {
  name: string;
  maintainerName: string;
  maintainerEmail: string;
  description: string;
}

interface MarketplaceGeneralTabProps {
  metadata: MarketplaceRootMetadata;
  rootPath: string;
  isSaving: boolean;
  onMetadataChange: (metadata: MarketplaceRootMetadata) => void;
  onSave: () => void;
}

const MarketplaceGeneralTab: React.FC<MarketplaceGeneralTabProps> = ({
  metadata,
  rootPath,
  isSaving,
  onMetadataChange,
  onSave,
}) => {
  const { t } = useI18n();
  const updateMetadata = (updates: Partial<MarketplaceRootMetadata>) => {
    onMetadataChange({ ...metadata, ...updates });
  };
  const savePayload: MarketplaceRegistryRootMetadataSavePayload = {
    name: metadata.name,
    owner: {
      name: metadata.maintainerName,
      email: metadata.maintainerEmail,
    },
    description: metadata.description,
  };
  const claudePreview = JSON.stringify({
    ...savePayload,
    plugins: [],
  }, null, 2);
  const codexPreview = JSON.stringify({
    name: savePayload.name,
    description: savePayload.description,
    plugins: [],
  }, null, 2);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          {t('marketplace.settings.general.title')}
        </CardTitle>
        <CardDescription>{t('marketplace.settings.general.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <section className="space-y-4">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-foreground">{t('marketplace.settings.general.rootMetadataTitle')}</h3>
            <p className="text-xs text-muted-foreground">{t('marketplace.settings.general.rootMetadataDescription')}</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <SettingsEditableField
              label={t('marketplace.settings.general.displayName')}
              value={metadata.name}
              onChange={value => updateMetadata({ name: value })}
            />
            <SettingsEditableField
              label={t('marketplace.settings.general.maintainerName')}
              value={metadata.maintainerName}
              onChange={value => updateMetadata({ maintainerName: value })}
            />
            <SettingsEditableField
              label={t('marketplace.settings.general.maintainerEmail')}
              value={metadata.maintainerEmail}
              onChange={value => updateMetadata({ maintainerEmail: value })}
            />
            <div className="md:col-span-2">
              <SettingsTextAreaField
                label={t('marketplace.settings.general.descriptionField')}
                value={metadata.description}
                onChange={value => updateMetadata({ description: value })}
              />
            </div>
            <div className="md:col-span-2">
              <SettingsReadOnlyField label={t('marketplace.settings.general.rootPath')} value={rootPath} monospace />
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={onSave} disabled={isSaving}>
              <Save className="mr-2 h-4 w-4" />
              {t('marketplace.common.actions.save')}
            </Button>
          </div>
        </section>

        <section className="space-y-4 border-t border-border pt-6">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-foreground">{t('marketplace.settings.general.generatedPreviewTitle')}</h3>
            <p className="text-xs text-muted-foreground">{t('marketplace.settings.general.generatedPreviewDescription')}</p>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <SettingsJsonPreview
              title={t('marketplace.settings.general.previews.claude.title')}
              filePath="claude-code/.claude-plugin/marketplace.json"
              value={claudePreview}
            />
            <SettingsJsonPreview
              title={t('marketplace.settings.general.previews.codex.title')}
              filePath="codex/.agents/plugins/marketplace.json"
              value={codexPreview}
            />
          </div>
        </section>

      </CardContent>
    </Card>
  );
};

interface SettingsEditableFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

const SettingsEditableField: React.FC<SettingsEditableFieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input value={value} onChange={event => onChange(event.target.value)} />
  </div>
);

interface SettingsTextAreaFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

const SettingsTextAreaField: React.FC<SettingsTextAreaFieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Textarea value={value} rows={3} onChange={event => onChange(event.target.value)} />
  </div>
);

interface SettingsJsonPreviewProps {
  title: string;
  filePath: string;
  value: string;
}

const SettingsJsonPreview: React.FC<SettingsJsonPreviewProps> = ({ title, filePath, value }) => (
  <div className="space-y-3 rounded-md border border-border bg-muted/20 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">{filePath}</span>
    </div>
    <Textarea
      aria-label={filePath}
      value={value}
      readOnly
      className="min-h-[14rem] resize-none bg-background font-mono text-xs"
    />
  </div>
);

const MarketplaceActivityTab: React.FC = () => {
  const { t } = useI18n();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock3 className="h-5 w-5" />
          {t('marketplace.settings.activity.title')}
        </CardTitle>
        <CardDescription>{t('marketplace.settings.activity.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          {t('marketplace.settings.activity.empty')}
        </div>
      </CardContent>
    </Card>
  );
};

interface SettingsReadOnlyFieldProps {
  label: string;
  value: string;
  monospace?: boolean;
}

const SettingsReadOnlyField: React.FC<SettingsReadOnlyFieldProps> = ({ label, value, monospace = false }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input value={value} readOnly className={monospace ? 'bg-muted font-mono text-sm' : 'bg-muted'} />
  </div>
);

type MarketplaceVersionControlMode = 'changes' | 'history';
type MarketplaceVersionControlFileGroup = 'staged' | 'unstaged';
type MarketplaceVersionControlError = 'conflict' | 'unsupportedBranch' | 'permissionDenied';

const toVersionControlFile = (file: MarketplaceRegistryGitFileChange): VersionControlFileChange => ({
  name: file.path.split('/').pop() ?? file.path,
  path: file.path,
  status: file.status,
  type: file.type,
  oldPath: file.oldPath,
});

const toVersionControlChanges = (status: MarketplaceRegistryGitStatus): VersionControlChangesResponse => ({
  staged: status.staged.map(toVersionControlFile),
  unstaged: status.unstaged.map(toVersionControlFile),
  untracked: status.untracked.map(toVersionControlFile),
});

interface MarketplaceVersionControlTabProps {
  repository: MarketplaceRegistryRepositoryStatus | null;
  onRepositoryChange: (repository: MarketplaceRegistryRepositoryStatus) => void;
}

const MarketplaceVersionControlTab: React.FC<MarketplaceVersionControlTabProps> = ({
  repository,
  onRepositoryChange,
}) => {
  const { t } = useI18n();
  const [mode, setMode] = React.useState<MarketplaceVersionControlMode>('changes');
  const [changes, setChanges] = React.useState<VersionControlChangesResponse>({ staged: [], unstaged: [], untracked: [] });
  const [currentBranch, setCurrentBranch] = React.useState('');
  const [commits, setCommits] = React.useState<VersionControlCommitSummary[]>([]);
  const [commitFiles, setCommitFiles] = React.useState<VersionControlFileChange[]>([]);
  const [selectedFile, setSelectedFile] = React.useState<VersionControlFileChange | null>(null);
  const [selectedGroup, setSelectedGroup] = React.useState<MarketplaceVersionControlFileGroup>('unstaged');
  const [selectedCommitId, setSelectedCommitId] = React.useState<string | null>(null);
  const [selectedCommitFile, setSelectedCommitFile] = React.useState<VersionControlFileChange | null>(null);
  const [diffContent, setDiffContent] = React.useState('');
  const [isMutating, setIsMutating] = React.useState(false);
  const [isRemoteDialogOpen, setIsRemoteDialogOpen] = React.useState(false);
  const [isSavingRemoteUrl, setIsSavingRemoteUrl] = React.useState(false);
  const [isInitializingRepository, setIsInitializingRepository] = React.useState(false);
  const [isCloningRepository, setIsCloningRepository] = React.useState(false);
  const [operationError, setOperationError] = React.useState<MarketplaceVersionControlError | null>(null);
  const [registryMutationAllowed, setRegistryMutationAllowed] = React.useState(true);
  const autoInitAttemptedRef = React.useRef(false);
  const statusRequestVersionRef = React.useRef(0);

  const loadRepository = React.useCallback(async () => {
    const nextRepository = await getRegistryRepository();
    onRepositoryChange(nextRepository);
    return nextRepository;
  }, [onRepositoryChange]);
  const applyRegistryGitStatus = React.useCallback((status: MarketplaceRegistryGitStatus) => {
    setCurrentBranch(status.branch);
    setChanges(toVersionControlChanges(status));
  }, []);

  const loadStatus = React.useCallback(async () => {
    const requestVersion = ++statusRequestVersionRef.current;
    const status = await getRegistryGitStatus();
    if (requestVersion !== statusRequestVersionRef.current) {
      return;
    }
    applyRegistryGitStatus(status);
  }, [applyRegistryGitStatus]);

  const loadHistory = React.useCallback(async () => {
    const history = await getRegistryCommits(1, 50);
    const nextCommits = history.items.map(commit => ({
      id: commit.id,
      message: commit.message,
      author: commit.author,
      email: commit.email,
      timestamp: new Date(commit.timestamp).getTime(),
      branch: currentBranch || null,
      additions: commit.additions,
      deletions: commit.deletions,
      files: commit.filesChanged,
    }));
    setCommits(nextCommits);
    setSelectedCommitId(current => current ?? nextCommits[0]?.id ?? null);
  }, [currentBranch]);

  React.useEffect(() => {
    let isActive = true;
    const loadInitialState = async () => {
      const nextRepository = await loadRepository();
      if (!isActive) return;
      if (
        !autoInitAttemptedRef.current
        && !nextRepository.isGitRepo
        && nextRepository.hasLocalContent
        && nextRepository.canInitSafely
      ) {
        autoInitAttemptedRef.current = true;
        setIsInitializingRepository(true);
        try {
          const result = await initializeRegistryGit();
          if (!isActive) return;
          if (result.repository) {
            onRepositoryChange(result.repository);
          } else {
            await loadRepository();
          }
        } catch {
          // Status loading can initialize read-only local registries on the server.
        } finally {
          if (isActive) {
            setIsInitializingRepository(false);
          }
        }
      }
      if (isActive) {
        await loadStatus();
      }
    };
    void loadInitialState();
    return () => {
      isActive = false;
    };
  }, [loadRepository, loadStatus, onRepositoryChange]);

  React.useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  React.useEffect(() => {
    if (!selectedCommitId) {
      setCommitFiles([]);
      return;
    }
    let isActive = true;
    void getRegistryCommitFiles(selectedCommitId).then(result => {
      if (!isActive) return;
      setCommitFiles(result.files.map(toVersionControlFile));
    });
    return () => {
      isActive = false;
    };
  }, [selectedCommitId]);

  const stagedFiles = React.useMemo(
    () => changes.staged.map(file => ({ ...file, changeType: 'staged' as const })),
    [changes.staged],
  );
  const unstagedFiles = React.useMemo(
    () => [
      ...changes.unstaged.map(file => ({ ...file, changeType: 'unstaged' as const })),
      ...changes.untracked.map(file => ({ ...file, changeType: 'untracked' as const })),
    ],
    [changes.unstaged, changes.untracked],
  );
  const selectedDiffFile = mode === 'history' ? selectedCommitFile : selectedFile;
  React.useEffect(() => {
    if (!selectedDiffFile) {
      setDiffContent('');
      return;
    }
    let isActive = true;
    const loadDiff = mode === 'history' && selectedCommitId
      ? getRegistryCommitFileDiff(selectedCommitId, selectedDiffFile.path)
      : getRegistryFileDiff(selectedDiffFile.path, selectedGroup === 'staged' ? 'INDEX' : 'WORKTREE');
    void loadDiff.then(diff => {
      if (!isActive) return;
      setDiffContent(diff.patch || diff.diff || '');
    });
    return () => {
      isActive = false;
    };
  }, [mode, selectedCommitId, selectedDiffFile, selectedGroup]);

  const fileSelection = useVersionControlFileSelection({
    stagedFiles,
    unstagedFiles,
    onFileSelect: (file, group) => {
      setSelectedFile(file);
      setSelectedGroup(group);
    },
  });
  const clearChangeSelection = React.useCallback(() => {
    setSelectedFile(null);
    setDiffContent('');
    fileSelection.clearSelection();
  }, [fileSelection]);
  const mutateStatus = async <TResult,>(
    operation: () => Promise<TResult>,
    applyResult?: (result: TResult) => void,
  ) => {
    const mutationVersion = ++statusRequestVersionRef.current;
    setIsMutating(true);
    try {
      const result = await operation();
      if (applyResult) {
        if (mutationVersion === statusRequestVersionRef.current) {
          applyResult(result);
        }
      } else {
        await loadStatus();
      }
      await loadHistory();
      setOperationError(null);
      clearChangeSelection();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setRegistryMutationAllowed(false);
        setOperationError('permissionDenied');
        await loadStatus();
        return;
      }
      throw err;
    } finally {
      setIsMutating(false);
    }
  };
  const handleStageToggle = (file: VersionControlFileChange, group: MarketplaceVersionControlFileGroup) => {
    const paths = fileSelection.getActionPaths(file, group);
    void mutateStatus(
      () => group === 'staged' ? unstageRegistryFiles(paths) : stageRegistryFiles(paths),
      applyRegistryGitStatus,
    );
  };
  const handleDiscard = (_file: VersionControlFileChange) => {
    setOperationError('unsupportedBranch');
    clearChangeSelection();
  };
  const handleStageAll = () => {
    void mutateStatus(
      () => stageRegistryFiles(unstagedFiles.map(file => file.path)),
      applyRegistryGitStatus,
    );
  };
  const handleUnstageAll = () => {
    void mutateStatus(
      () => unstageRegistryFiles(stagedFiles.map(file => file.path)),
      applyRegistryGitStatus,
    );
  };
  const handleCommit = (data: { message: string }) => {
    void mutateStatus(() => commitRegistryChanges(data.message));
  };
  const handleRemoteResult = async (operation: () => Promise<{ repository?: MarketplaceRegistryRepositoryStatus | null }>) => {
    const result = await operation();
    if (result.repository) {
      onRepositoryChange(result.repository);
      return;
    }
    await loadRepository();
  };
  const handleSaveRemoteUrl = async (remoteUrl: string) => {
    setIsSavingRemoteUrl(true);
    try {
      await handleRemoteResult(() => setRegistryRemote(remoteUrl));
    } finally {
      setIsSavingRemoteUrl(false);
    }
  };
  const handleInitRepository = async () => {
    setIsInitializingRepository(true);
    try {
      await handleRemoteResult(() => initializeRegistryGit());
      await loadStatus();
      await loadHistory();
    } finally {
      setIsInitializingRepository(false);
    }
  };
  const handleCloneRepository = async (remoteUrl: string, branch?: string) => {
    setIsCloningRepository(true);
    try {
      await handleRemoteResult(() => cloneRegistry(remoteUrl, branch));
      await loadStatus();
      await loadHistory();
    } finally {
      setIsCloningRepository(false);
    }
  };
  const actionItems: VersionControlActionMenuItem[] = [
    { id: 'refresh', onClick: () => void loadStatus() },
    { id: 'remoteSettings', onClick: () => {
      setOperationError(null);
      setIsRemoteDialogOpen(true);
    }, disabled: !registryMutationAllowed },
    { id: 'fetch', onClick: () => void mutateStatus(fetchRegistry), disabled: !registryMutationAllowed },
    { id: 'pull', onClick: () => void mutateStatus(pullRegistry), disabled: !registryMutationAllowed },
    { id: 'push', onClick: () => void mutateStatus(pushRegistry), disabled: !registryMutationAllowed },
  ];
  const remoteDialogRepository: VersionControlRemoteSettingsState | null = repository ? {
    isRepositoryInitialized: repository.isGitRepo,
    currentBranch: repository.currentBranch,
    remoteUrl: repository.remoteUrl,
    hasOrigin: repository.hasOrigin,
    hasLocalContent: repository.hasLocalContent,
    canCloneSafely: repository.canCloneSafely,
    canInitSafely: repository.canInitSafely,
  } : null;
  const modeRail = (
    <VersionControlModeRail
      title={t('marketplace.settings.versionControl.title')}
      titleIcon={GitBranch}
      activeId={mode}
      onChange={nextMode => {
        setMode(nextMode as MarketplaceVersionControlMode);
        setSelectedFile(null);
        setSelectedCommitFile(null);
        fileSelection.clearSelection();
      }}
      items={[
        {
          id: 'changes',
          label: t('shared.versionControl.mode.fileChanges'),
          icon: FileDiff,
          count: stagedFiles.length + unstagedFiles.length,
        },
        {
          id: 'history',
          label: t('shared.versionControl.mode.commitHistory'),
          icon: History,
          count: commits.length,
        },
      ]}
      footer={operationError ? (
        <Alert variant="destructive" className="p-2">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="text-xs">
            {t(`marketplace.settings.versionControl.errors.${operationError}`)}
          </AlertDescription>
        </Alert>
      ) : null}
    />
  );
  const changesSidebar = (
    <VersionControlChangesSidebar
      branches={currentBranch ? [{ name: currentBranch, displayName: currentBranch, isActive: true }] : []}
      currentBranch={currentBranch}
      actions={actionItems}
      stagedFiles={stagedFiles}
      unstagedFiles={unstagedFiles}
      selectedStagedPath={selectedGroup === 'staged' ? selectedFile?.path : null}
      selectedUnstagedPath={selectedGroup === 'unstaged' ? selectedFile?.path : null}
      selectedStagedPaths={fileSelection.selectedStagedPaths}
      selectedUnstagedPaths={fileSelection.selectedUnstagedPaths}
      isMutating={isMutating}
      mutationDisabled={!registryMutationAllowed}
      onBranchChange={() => setOperationError('unsupportedBranch')}
      onCommit={handleCommit}
      onFileSelect={(file, group, event) => fileSelection.selectFile(file, group as VersionControlFileGroup, event)}
      onStageToggle={(file, group) => handleStageToggle(file, group)}
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
      onCommitSelect={commit => {
        setSelectedCommitId(commit.id);
        setSelectedCommitFile(null);
      }}
      onFileSelect={setSelectedCommitFile}
    />
  );

  return (
    <>
      <VersionControlLayout
        className="h-full"
        modeRail={modeRail}
        sidebar={mode === 'changes' ? changesSidebar : historySidebar}
        main={(
          <VersionControlMainDiff
            selectedPath={selectedDiffFile?.path ?? null}
            diffContent={diffContent}
            emptyKey={mode === 'changes'
              ? 'shared.versionControl.main.selectFile'
              : 'shared.versionControl.main.selectCommitFile'}
          />
        )}
      />
      <VersionControlRemoteSettingsDialog
        open={isRemoteDialogOpen}
        onOpenChange={setIsRemoteDialogOpen}
        repository={remoteDialogRepository}
        capabilities={{
          canConfigureRemote: true,
          supportsRemoteInit: true,
          supportsRemoteClone: true,
        }}
        onSaveRemoteUrl={handleSaveRemoteUrl}
        onInitRepository={handleInitRepository}
        onCloneRepository={handleCloneRepository}
        isSavingRemoteUrl={isSavingRemoteUrl}
        isInitializingRepository={isInitializingRepository}
        isCloningRepository={isCloningRepository}
      />
    </>
  );
};

interface MarketplaceGitUserTabProps {
  userName: string;
  userEmail: string;
  onUserNameChange: (value: string) => void;
  onUserEmailChange: (value: string) => void;
}

const MarketplaceGitUserTab: React.FC<MarketplaceGitUserTabProps> = ({
  userName,
  userEmail,
  onUserNameChange,
  onUserEmailChange,
}) => {
  const { t } = useI18n();

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserRound className="h-5 w-5" />
            {t('marketplace.settings.git.user.title')}
          </CardTitle>
          <CardDescription>
            {t('marketplace.settings.git.user.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="marketplaceGitUserName">{t('marketplace.settings.git.user.name')}</Label>
              <Input
                id="marketplaceGitUserName"
                value={userName}
                onChange={event => onUserNameChange(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="marketplaceGitUserEmail">{t('marketplace.settings.git.user.email')}</Label>
              <Input
                id="marketplaceGitUserEmail"
                value={userEmail}
                onChange={event => onUserEmailChange(event.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end">
            <Button>
              <Save className="mr-2 h-4 w-4" />
              {t('marketplace.settings.git.user.save')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

interface MarketplaceSshKeysTabProps {
  sshKeys: UserSettingsSSH;
  showPrivateKey: boolean;
  onSshKeysChange: (value: UserSettingsSSH) => void;
  onShowPrivateKeyChange: (value: boolean) => void;
  onGenerateSshKey: () => void;
  onSaveSshKeys: () => void;
  onCopy: (value: string | null) => void;
}

const MarketplaceSshKeysTab: React.FC<MarketplaceSshKeysTabProps> = ({
  sshKeys,
  showPrivateKey,
  onSshKeysChange,
  onShowPrivateKeyChange,
  onGenerateSshKey,
  onSaveSshKeys,
  onCopy,
}) => {
  const { t } = useI18n();

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="h-5 w-5" />
            {t('pages.settings.sections.ssh.title')}
          </CardTitle>
          <CardDescription>
            {t('pages.settings.sections.ssh.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="marketplaceUserPrivateKey">{t('pages.settings.sections.ssh.privateKey.label')}</Label>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => onShowPrivateKeyChange(!showPrivateKey)}>
                  {showPrivateKey
                    ? t('pages.settings.sections.ssh.privateKey.actions.hide')
                    : t('pages.settings.sections.ssh.privateKey.actions.show')}
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => onCopy(sshKeys.privateKey)}>
                  {t('pages.settings.sections.ssh.privateKey.actions.copy')}
                </Button>
              </div>
            </div>
            <Textarea
              id="marketplaceUserPrivateKey"
              placeholder={t('pages.settings.sections.ssh.privateKey.placeholder')}
              value={showPrivateKey ? (sshKeys.privateKey || '') : '••••••••••••'}
              onChange={event => onSshKeysChange({ ...sshKeys, privateKey: event.target.value })}
              className="font-mono text-sm"
              disabled={!showPrivateKey}
              rows={8}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="marketplaceUserPublicKey">{t('pages.settings.sections.ssh.publicKey.label')}</Label>
              <Button type="button" variant="outline" size="sm" onClick={() => onCopy(sshKeys.publicKey)}>
                {t('pages.settings.sections.ssh.publicKey.copy')}
              </Button>
            </div>
            <Textarea
              id="marketplaceUserPublicKey"
              placeholder={t('pages.settings.sections.ssh.publicKey.placeholder')}
              value={sshKeys.publicKey || ''}
              onChange={event => onSshKeysChange({ ...sshKeys, publicKey: event.target.value })}
              className="font-mono text-sm"
              rows={4}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onGenerateSshKey}>
              {t('pages.settings.sections.ssh.generate')}
            </Button>
            <Button onClick={onSaveSshKeys}>
              <Save className="mr-2 h-4 w-4" />
              {t('pages.settings.actions.save')}
            </Button>
          </div>
        </CardContent>
      </Card>

    </div>
  );
};

export default MarketplaceSettingsView;
