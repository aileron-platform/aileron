import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Settings, Save, ArrowLeft } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Separator } from '@/shared/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { apiClient } from '@/shared/api/apiClient';
import { ROUTES } from '@/shared/constants/routes';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('TemplateCenterSettingsView');
import { GitChangeLogTab } from './components/GitChangeLogTab';
import { GitUserConfigTab } from './components/GitUserConfigTab';
import { SSHKeysTab } from './components/SSHKeysTab';
import type { SSHKeys } from '@/shared/services/templateSshApi';
import {
  getGitStatus,
  getGitUserConfig,
  type GitStatus,
  type GitUserConfigRequest,
  updateGitUserConfig,
  cloneRepository,
} from '@/shared/services/templateGitApi';

interface MarketplaceConfig {
  name: string;
  version: string;
  description: string;
  ownerName: string;
  ownerEmail: string;
  homepage: string;
}

export const TemplateCenterSettingsView: React.FC = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { t } = useI18n();

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('basic');
  const [config, setConfig] = useState<MarketplaceConfig>({
    name: 'claude-code-marketplace',
    version: '1.0.0',
    description: '',
    ownerName: '',
    ownerEmail: '',
    homepage: '',
  });
  const [sshKeys, setSshKeys] = useState<SSHKeys | null>(null);
  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [gitRepoUrl, setGitRepoUrl] = useState<string>('');
  const [gitUserConfig, setGitUserConfig] = useState<GitUserConfigRequest | null>(null);
  const [isSavingGitUserConfig, setIsSavingGitUserConfig] = useState(false);
  const [isCloningRepository, setIsCloningRepository] = useState(false);

  // 載入配置和 Git 狀態
  useEffect(() => {
    const loadConfig = async () => {
      try {
        setIsLoading(true);

        // 並行載入配置和 Git 狀態
        const [configResponse, gitStatusResponse, gitUserConfigResponse] = await Promise.all([
          apiClient.get<{
            success: boolean;
            data?: {
              name: string;
              owner: { name: string; email: string };
              metadata: { description: string; version: string; homepage: string };
            };
          }>('/templates/marketplace/config'),
          getGitStatus(),
          getGitUserConfig(),
        ]);

        // 設定基本配置
        if (configResponse.success && configResponse.data) {
          setConfig({
            name: configResponse.data.name,
            version: configResponse.data.metadata.version,
            description: configResponse.data.metadata.description,
            ownerName: configResponse.data.owner.name,
            ownerEmail: configResponse.data.owner.email,
            homepage: configResponse.data.metadata.homepage,
          });
        }

        // 設定 Git 狀態
        if (gitStatusResponse.success && gitStatusResponse.data) {
          setGitStatus(gitStatusResponse.data);
          setGitRepoUrl(gitStatusResponse.data.remote_url || '');
        }

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

  const handleFieldChange = <K extends keyof MarketplaceConfig>(
    key: K,
    value: MarketplaceConfig[K]
  ) => {
    setConfig((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // 儲存基本設定
      await apiClient.put('/templates/marketplace/config', {
        name: config.name,
        owner: {
          name: config.ownerName,
          email: config.ownerEmail,
        },
        metadata: {
          description: config.description,
          version: config.version,
          homepage: config.homepage,
        },
      });

      // SSH Keys 在產生時已自動儲存，這裡只需要提示
      let description = t('template.center.settingsDialog.toasts.saved.description');
      if (sshKeys && (sshKeys.publicKey || sshKeys.privateKey)) {
        description += ' ' + t('template.center.settingsDialog.toasts.saved.sshKeysAutoSaved');
      }

      toast({
        title: t('template.center.settingsDialog.toasts.saved.title'),
        description,
        variant: 'success',
      });
    } catch (error) {
      logger.error('儲存失敗', { error });
      toast({
        title: t('template.center.settingsDialog.toasts.failed.title'),
        description: t('template.center.settingsDialog.toasts.failed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

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

          // 重新載入 Git 狀態
          const gitStatusResponse = await getGitStatus();
          if (gitStatusResponse.success && gitStatusResponse.data) {
            setGitStatus(gitStatusResponse.data);
          }
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
            <Button size="sm" className="h-7 px-2 text-xs" onClick={handleSave} disabled={isSaving}>
              <Save className="h-3.5 w-3.5 mr-1.5" />
              {isSaving
                ? t('template.center.settingsDialog.actions.saveProcessing')
                : t('template.center.settingsDialog.actions.save')}
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-4xl p-6">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="basic">
                {t('template.center.settingsDialog.tabs.basic')}
              </TabsTrigger>
              <TabsTrigger value="changeLog">
                {t('template.center.settingsDialog.tabs.changeLog')}
              </TabsTrigger>
              <TabsTrigger value="gitUser">
                {t('template.center.settingsDialog.tabs.gitUser')}
              </TabsTrigger>
              <TabsTrigger value="sshKeys">
                {t('template.center.settingsDialog.tabs.sshKeys')}
              </TabsTrigger>
            </TabsList>

            {/* 基本設定 Tab */}
            <TabsContent value="basic" className="mt-6">
              <div className="space-y-8">
            {/* 基本資訊 */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">
                {t('template.center.settingsDialog.basicInfo.title')}
              </h3>

              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">
                    {t('template.center.settingsDialog.basicInfo.nameLabel')}
                  </Label>
                  <Input
                    id="name"
                    value={config.name}
                    onChange={(e) => handleFieldChange('name', e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="version">
                    {t('template.center.settingsDialog.basicInfo.versionLabel')}
                  </Label>
                  <Input
                    id="version"
                    value={config.version}
                    onChange={(e) => handleFieldChange('version', e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">
                  {t('template.center.settingsDialog.basicInfo.descriptionLabel')}
                </Label>
                <Textarea
                  id="description"
                  rows={4}
                  value={config.description}
                  onChange={(e) => handleFieldChange('description', e.target.value)}
                  placeholder={t('template.center.settingsDialog.basicInfo.descriptionPlaceholder')}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="homepage">
                  {t('template.center.settingsDialog.basicInfo.homepageLabel')}
                </Label>
                <Input
                  id="homepage"
                  type="url"
                  value={config.homepage}
                  onChange={(e) => handleFieldChange('homepage', e.target.value)}
                  placeholder={t('template.center.settingsDialog.basicInfo.homepagePlaceholder')}
                />
              </div>
            </div>

            <Separator />

            {/* 擁有者資訊 */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">
                {t('template.center.settingsDialog.owner.title')}
              </h3>

              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="ownerName">
                    {t('template.center.settingsDialog.owner.nameLabel')}
                  </Label>
                  <Input
                    id="ownerName"
                    value={config.ownerName}
                    onChange={(e) => handleFieldChange('ownerName', e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="ownerEmail">
                    {t('template.center.settingsDialog.owner.emailLabel')}
                  </Label>
                  <Input
                    id="ownerEmail"
                    type="email"
                    value={config.ownerEmail}
                    onChange={(e) => handleFieldChange('ownerEmail', e.target.value)}
                  />
                </div>
              </div>
            </div>
              </div>
            </TabsContent>

            {/* 變更記錄 Tab */}
            <TabsContent value="changeLog" className="mt-6">
              <GitChangeLogTab />
            </TabsContent>

            {/* Git 使用者設定 Tab */}
            <TabsContent value="gitUser" className="mt-6">
              <GitUserConfigTab
                value={gitUserConfig}
                remoteUrl={gitRepoUrl}
                onSave={handleSaveGitUserConfig}
                onCloneRepository={handleCloneRepository}
                isSaving={isSavingGitUserConfig}
                isCloningRepository={isCloningRepository}
              />
            </TabsContent>

            {/* SSH Keys Tab */}
            <TabsContent value="sshKeys" className="mt-6">
              <SSHKeysTab value={sshKeys} onChange={setSshKeys} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default TemplateCenterSettingsView;

