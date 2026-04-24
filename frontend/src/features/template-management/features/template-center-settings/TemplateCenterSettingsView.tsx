import React, { useCallback, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Settings, ArrowLeft, GitBranch, Cloud, KeyRound, UserRound } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Tabs, TabsContent } from '@/shared/components/ui/tabs';
import { TopTabsBar, TopTabsList, TopTabsTrigger } from '@/shared/components/navigation/TopTabs';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('TemplateCenterSettingsView');
import { GitUserConfigTab } from './components/GitUserConfigTab';
import { SSHKeysTab } from './components/SSHKeysTab';
import { TemplateRegistryVersionControlTab } from './components/TemplateRegistryVersionControlTab';
import type { SSHKeys } from '@/shared/services/templateSshApi';
import {
  getRepositoryStatus,
  getGitUserConfig,
  initRepository,
  setGitRemoteUrl,
  type GitRepositoryStatus,
  type GitUserConfigRequest,
  updateGitUserConfig,
  cloneRepository,
} from '@/shared/services/templateGitApi';

export const TemplateCenterSettingsView: React.FC = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { t } = useI18n();

  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('versionControl');
  const [sshKeys, setSshKeys] = useState<SSHKeys | null>(null);
  const [gitRepoUrl, setGitRepoUrl] = useState<string>('');
  const [repositoryStatus, setRepositoryStatus] = useState<GitRepositoryStatus | null>(null);
  const [gitUserConfig, setGitUserConfig] = useState<GitUserConfigRequest | null>(null);
  const [isSavingGitUserConfig, setIsSavingGitUserConfig] = useState(false);
  const [isCloningRepository, setIsCloningRepository] = useState(false);
  const [isInitializingRepository, setIsInitializingRepository] = useState(false);
  const [isSavingRemoteUrl, setIsSavingRemoteUrl] = useState(false);

  const refreshRepositoryStatus = useCallback(async () => {
    const nextStatus = await getRepositoryStatus();
    setRepositoryStatus(nextStatus);
    setGitRepoUrl(nextStatus.remoteUrl || '');
    return nextStatus;
  }, []);

  // 載入 Git 設定
  useEffect(() => {
    const loadConfig = async () => {
      try {
        setIsLoading(true);

        const [repositoryStatusResponse, gitUserConfigResponse] = await Promise.all([
          getRepositoryStatus(),
          getGitUserConfig(),
        ]);

        setRepositoryStatus(repositoryStatusResponse);
        setGitRepoUrl(repositoryStatusResponse.remoteUrl || '');

        if (gitUserConfigResponse.success && gitUserConfigResponse.data) {
          setGitUserConfig({
            userName: gitUserConfigResponse.data.userName ?? '',
            userEmail: gitUserConfigResponse.data.userEmail ?? '',
          });
        } else {
          setGitUserConfig({ userName: '', userEmail: '' });
        }
      } catch (err) {
        logger.error('載入配置失敗', { error: err });
        toast({
          title: t('template.center.settingsDialog.toasts.failed.title'),
          description: t('template.center.settingsDialog.toasts.failed.description'),
          variant: 'destructive',
        });
      } finally {
        setIsLoading(false);
      }
    };

    loadConfig();
  }, [t, toast]);

  const handleBack = () => {
    navigate(ROUTES.TEMPLATE_CENTER);
  };

  const handleSaveGitUserConfig = async (value: GitUserConfigRequest) => {
    if (!value.userName.trim() || !value.userEmail.trim()) {
      toast({
        title: t('template.center.settingsDialog.toasts.gitUserConfigFailed.title'),
        description: t('template.center.settingsDialog.toasts.gitUserConfigFailed.description', {
          error: t('template.center.settingsDialog.git.userConfig.validation.required'),
        }),
        variant: 'destructive',
      });
      return;
    }

    setIsSavingGitUserConfig(true);
    try {
      const response = await updateGitUserConfig({
        userName: value.userName.trim(),
        userEmail: value.userEmail.trim(),
      });

      if (response.success) {
        setGitUserConfig({
          userName: value.userName.trim(),
          userEmail: value.userEmail.trim(),
        });

        toast({
          title: t('template.center.settingsDialog.toasts.gitUserConfigSaved.title'),
          description: t('template.center.settingsDialog.toasts.gitUserConfigSaved.description'),
          variant: 'success',
        });
      } else {
        toast({
          title: t('template.center.settingsDialog.toasts.gitUserConfigFailed.title'),
          description: t('template.center.settingsDialog.toasts.gitUserConfigFailed.description', {
            error: response.error || response.message,
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('更新 Git 使用者資訊失敗', { error });
      toast({
        title: t('template.center.settingsDialog.toasts.gitUserConfigFailed.title'),
        description: t('template.center.settingsDialog.toasts.gitUserConfigFailed.description', {
          error: error instanceof Error ? error.message : t('template.center.settingsDialog.unknownError'),
        }),
        variant: 'destructive',
      });
    } finally {
      setIsSavingGitUserConfig(false);
    }
  };

  const handleSaveRemoteUrl = async (remoteUrl: string) => {
    if (!remoteUrl.trim()) {
      toast({
        title: t('template.center.settingsDialog.toasts.remoteUrlFailed.title'),
        description: t('template.center.settingsDialog.toasts.remoteUrlFailed.description', {
          error: t('template.center.settingsDialog.git.remote.validation.required'),
        }),
        variant: 'destructive',
      });
      return;
    }

    setIsSavingRemoteUrl(true);
    try {
      const response = await setGitRemoteUrl({ remoteUrl: remoteUrl.trim() });
      if (response.success) {
        await refreshRepositoryStatus();
        toast({
          title: t('template.center.settingsDialog.toasts.remoteUrlSaved.title'),
          description: t('template.center.settingsDialog.toasts.remoteUrlSaved.description'),
          variant: 'success',
        });
      } else {
        toast({
          title: t('template.center.settingsDialog.toasts.remoteUrlFailed.title'),
          description: t('template.center.settingsDialog.toasts.remoteUrlFailed.description', {
            error: response.error || response.message,
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('更新 Template Center Git remote 失敗', { error });
      toast({
        title: t('template.center.settingsDialog.toasts.remoteUrlFailed.title'),
        description: t('template.center.settingsDialog.toasts.remoteUrlFailed.description', {
          error: error instanceof Error ? error.message : t('template.center.settingsDialog.unknownError'),
        }),
        variant: 'destructive',
      });
    } finally {
      setIsSavingRemoteUrl(false);
    }
  };

  const handleInitRepository = async () => {
    setIsInitializingRepository(true);
    try {
      const response = await initRepository();
      if (response.success) {
        await refreshRepositoryStatus();
        toast({
          title: t('template.center.settingsDialog.toasts.initRepoSuccess.title'),
          description: t('template.center.settingsDialog.toasts.initRepoSuccess.description'),
          variant: 'success',
        });
      } else {
        toast({
          title: t('template.center.settingsDialog.toasts.initRepoFailed.title'),
          description: t('template.center.settingsDialog.toasts.initRepoFailed.description', {
            error: response.error || response.message,
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('初始化 Template Center Git repository 失敗', { error });
      toast({
        title: t('template.center.settingsDialog.toasts.initRepoFailed.title'),
        description: t('template.center.settingsDialog.toasts.initRepoFailed.description', {
          error: error instanceof Error ? error.message : t('template.center.settingsDialog.unknownError'),
        }),
        variant: 'destructive',
      });
    } finally {
      setIsInitializingRepository(false);
    }
  };

  const handleCloneRepository = async (url: string, branch?: string) => {
    setIsCloningRepository(true);
    try {
      const response = await cloneRepository({
        url,
        branch,
      });

      if (response.success) {
        setGitRepoUrl(url);

        // 如果返回了任務 ID，表示是後台任務
        if (response.task_id) {
          toast({
            title: t('template.center.settingsDialog.toasts.cloneRepoStarted.title'),
            description: t('template.center.settingsDialog.toasts.cloneRepoStarted.description'),
            variant: 'default',
          });

          // 返回任務 ID 給子組件
          return { task_id: response.task_id };
        } else {
          // 舊的同步 API 響應
          toast({
            title: t('template.center.settingsDialog.toasts.cloneRepoSuccess.title'),
            description: t('template.center.settingsDialog.toasts.cloneRepoSuccess.description'),
            variant: 'success',
          });

          await refreshRepositoryStatus();
        }
      } else {
        toast({
          title: t('template.center.settingsDialog.toasts.cloneRepoFailed.title'),
          description: t('template.center.settingsDialog.toasts.cloneRepoFailed.description', {
            error: response.error || response.message,
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('Clone 倉庫失敗', { error });
      toast({
        title: t('template.center.settingsDialog.toasts.cloneRepoFailed.title'),
        description: t('template.center.settingsDialog.toasts.cloneRepoFailed.description', {
          error: error instanceof Error ? error.message : t('template.center.settingsDialog.unknownError'),
        }),
        variant: 'destructive',
      });
    } finally {
      setIsCloningRepository(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-muted-foreground">{t('template.center.loading')}</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('template.center.settingsDialog.title')}
        icon={Settings}
        info={
          <div className="text-xs text-muted-foreground">
            {t('template.center.settingsDialog.description')}
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={handleBack}>
              <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
              {t('template.center.settingsDialog.actions.back')}
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-hidden">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex h-full flex-col">
          <TopTabsBar>
            <TopTabsList>
              <TopTabsTrigger value="versionControl">
                <GitBranch className="h-4 w-4" />
                {t('template.center.settings.tabs.versionControl')}
              </TopTabsTrigger>
              <TopTabsTrigger value="remote">
                <Cloud className="h-4 w-4" />
                {t('template.center.settings.tabs.remote')}
              </TopTabsTrigger>
              <TopTabsTrigger value="gitUser">
                <UserRound className="h-4 w-4" />
                {t('template.center.settings.tabs.gitUser')}
              </TopTabsTrigger>
              <TopTabsTrigger value="sshKeys">
                <KeyRound className="h-4 w-4" />
                {t('template.center.settings.tabs.sshKeys')}
              </TopTabsTrigger>
            </TopTabsList>
          </TopTabsBar>

          <TabsContent value="versionControl" className="flex-1 overflow-hidden !m-0 !p-0">
            <TemplateRegistryVersionControlTab
              repositoryStatus={repositoryStatus}
              onOpenRemoteSettings={() => setActiveTab('remote')}
            />
          </TabsContent>

          <TabsContent value="remote" className="flex-1 overflow-auto !m-0 !p-0">
            <div className="mx-auto w-full max-w-7xl p-6">
              <GitUserConfigTab
                value={gitUserConfig}
                remoteUrl={gitRepoUrl}
                repositoryStatus={repositoryStatus}
                onSave={handleSaveGitUserConfig}
                onSaveRemoteUrl={handleSaveRemoteUrl}
                onCloneRepository={handleCloneRepository}
                onInitRepository={handleInitRepository}
                onRepositoryStatusRefresh={refreshRepositoryStatus}
                isSaving={isSavingGitUserConfig}
                isSavingRemoteUrl={isSavingRemoteUrl}
                isCloningRepository={isCloningRepository}
                isInitializingRepository={isInitializingRepository}
                showUserConfig={false}
              />
            </div>
          </TabsContent>

          <TabsContent value="gitUser" className="flex-1 overflow-auto !m-0 !p-0">
            <div className="mx-auto w-full max-w-7xl p-6">
              <GitUserConfigTab
                value={gitUserConfig}
                remoteUrl={gitRepoUrl}
                repositoryStatus={repositoryStatus}
                onSave={handleSaveGitUserConfig}
                onSaveRemoteUrl={handleSaveRemoteUrl}
                onCloneRepository={handleCloneRepository}
                onInitRepository={handleInitRepository}
                onRepositoryStatusRefresh={refreshRepositoryStatus}
                isSaving={isSavingGitUserConfig}
                isSavingRemoteUrl={isSavingRemoteUrl}
                isCloningRepository={isCloningRepository}
                isInitializingRepository={isInitializingRepository}
                showRepositorySettings={false}
              />
            </div>
          </TabsContent>

          <TabsContent value="sshKeys" className="flex-1 overflow-auto !m-0 !p-0">
            <div className="mx-auto w-full max-w-7xl p-6">
              <SSHKeysTab value={sshKeys} onChange={setSshKeys} />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default TemplateCenterSettingsView;
