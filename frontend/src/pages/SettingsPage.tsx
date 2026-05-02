import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { Button } from '@/shared/components/ui/button';

const logger = createLogger('SettingsPage');
import { EnvironmentVariables } from '@/shared/components/ui/environment-variables';
import { Label } from '@/shared/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Separator } from '@/shared/components/ui/separator';
import { useToast } from '@/shared/components/ui/use-toast';
import GlobalNavigation from '@/app/components/navigation/GlobalNavigation';
import {
  Palette,
  Globe,
  Shield,
  Monitor,
  Moon,
  Sun,
  Save,
  RefreshCw,
  Key,
  GitBranch,
  Construction,
  Sparkles,
  Bot,
} from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useApp } from '@/app/providers/AppProvider';
import type { SupportedLanguage } from '@/app/providers/I18nProvider';
import { apiClient } from '@/shared/api/apiClient';
import { OAuthService } from '@/shared/services/oauthService';
import { OAuthApiService } from '@/shared/services/oauthApiService';
import type {
  UserSettings,
  UserSettingsGeneral,
  UserSettingsSSH,
  UserSettingsClaudeCode,
  UserSettingsCodex,
  UserSettingsGit,
  UserSettingsResponse,
} from '@/shared/types/user';

const cloneDeep = <T,>(value: T): T => {
  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value)) as T;
};

export const SettingsPage: React.FC = () => {
  const { toast } = useToast();
  const { t, changeLanguage } = useI18n();
  const { state: appState, dispatch } = useApp();
  const userId = appState.user.id;

  const [generalSettings, setGeneralSettings] = useState<UserSettingsGeneral | null>(null);
  const [sshKeys, setSshKeys] = useState<UserSettingsSSH | null>(null);
  const [claudeCodeSettings, setClaudeCodeSettings] = useState<UserSettingsClaudeCode | null>(null);
  const [codexSettings, setCodexSettings] = useState<UserSettingsCodex | null>(null);
  const [gitSettings, setGitSettings] = useState<UserSettingsGit | null>(null);
  const [showPrivateKey, setShowPrivateKey] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isCodexAuthLoading, setIsCodexAuthLoading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAuthCodeInput, setShowAuthCodeInput] = useState(false);
  const [isExchangingCode, setIsExchangingCode] = useState(false);
  const [tempAuthCode, setTempAuthCode] = useState('');
  const [needsSync, setNeedsSync] = useState(false);

  const initialSettingsRef = useRef<UserSettings | null>(null);
  const oauthVerifierRef = useRef<string | null>(null);

  const syncFromSnapshot = useCallback(
    (snapshot: UserSettings) => {
      initialSettingsRef.current = cloneDeep(snapshot);
      setGeneralSettings(cloneDeep(snapshot.general));
      setSshKeys(cloneDeep(snapshot.ssh));

      // 確保 claudeCodeSettings 有所有必要的欄位
      const claudeCodeWithDefaults = {
        authMethod: 'subscription', // 修改預設為 subscription
        environmentVariables: [],
        availableProviders: [],
        ...cloneDeep(snapshot.claudeCode)
      };
      setClaudeCodeSettings(claudeCodeWithDefaults);

      setCodexSettings({
        loginStatus: 'notConnected',
        model: 'gpt-5.3-codex',
        environmentVariables: [],
        ...cloneDeep(snapshot.codex),
      });

      setGitSettings(cloneDeep(snapshot.git));
      setShowPrivateKey(false);
      dispatch({ type: 'SET_THEME', payload: snapshot.general.theme });
      dispatch({ type: 'SET_LANGUAGE', payload: snapshot.general.language });
      void changeLanguage(snapshot.general.language as SupportedLanguage);
    },
    [changeLanguage, dispatch],
  );

  const fetchSettings = useCallback(async () => {
    if (!userId) {
      setError(t('pages.settings.notifications.loginRequired.description'));
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<UserSettingsResponse>(`/users/${userId}/settings`);
      syncFromSnapshot(response.data);
    } catch (err) {
      logger.error('load failed', { error: err });
      setError(t('pages.settings.notifications.loadFailed.description'));
      toast({
        title: t('pages.settings.notifications.loadFailed.title'),
        description: t('pages.settings.notifications.loadFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [syncFromSnapshot, t, toast, userId]);

  useEffect(() => {
    void fetchSettings();
  }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    if (!userId) {
      toast({
        title: t('pages.settings.notifications.saveLoginRequired.title'),
        description: t('pages.settings.notifications.saveLoginRequired.description'),
        variant: 'destructive',
      });
      return;
    }
    if (!generalSettings || !sshKeys || !claudeCodeSettings || !codexSettings || !gitSettings) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await apiClient.put<UserSettingsResponse>(`/users/${userId}/settings`, {
        general: generalSettings,
        ssh: {
          publicKey: sshKeys.publicKey,
          privateKey: sshKeys.privateKey,
          fingerprint: sshKeys.fingerprint,
          lastRotatedAt: sshKeys.lastRotatedAt,
        },
        claudeCode: {
          authMethod: claudeCodeSettings.authMethod,
          subscriptionAuthCode: claudeCodeSettings.subscriptionAuthCode,
          subscriptionAccessToken: claudeCodeSettings.subscriptionAccessToken,
          subscriptionRefreshToken: claudeCodeSettings.subscriptionRefreshToken,
          subscriptionExpiresAt: claudeCodeSettings.subscriptionExpiresAt,
          authKey: claudeCodeSettings.authKey,
          apiProvider: claudeCodeSettings.apiProvider,
          model: claudeCodeSettings.authMethod === 'subscription' ? '' : claudeCodeSettings.model,
          environmentVariables: claudeCodeSettings.environmentVariables,
          selectedProvider: claudeCodeSettings.selectedProvider,
          availableProviders: claudeCodeSettings.availableProviders,
        },
        codex: {
          loginStatus: codexSettings.loginStatus,
          account: codexSettings.account,
          model: codexSettings.model,
          environmentVariables: codexSettings.environmentVariables,
          authFlow: codexSettings.authFlow,
          lastSyncedAt: codexSettings.lastSyncedAt,
          lastSyncError: codexSettings.lastSyncError,
        },
        git: {
          userName: gitSettings.userName,
          userEmail: gitSettings.userEmail,
          signingKey: gitSettings.signingKey,
        },
      });

      syncFromSnapshot(response.data);

      toast({
        title: t('pages.settings.notifications.saved.title'),
        description: t('pages.settings.notifications.saved.description'),
      });

      // 儲存成功後自動同步到 workspace（不阻塞儲存流程）
      handleSync().catch(err => {
        logger.error('auto-sync failed after save', { error: err });
        // 同步失敗不影響儲存成功的提示
      });
    } catch (err) {
      logger.error('save failed', { error: err });
      setError(t('pages.settings.notifications.saveFailed.description'));
      toast({
        title: t('pages.settings.notifications.saveFailed.title'),
        description: t('pages.settings.notifications.saveFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleSync = async () => {
    if (!userId) {
      toast({
        title: t('pages.settings.notifications.syncFailed.title'),
        description: t('pages.settings.notifications.syncFailed.loginRequired'),
        variant: 'destructive',
      });
      return;
    }

    setIsSyncing(true);
    try {
      const SyncApiService = (await import('@/shared/services/syncApiService')).default;
      const result = await SyncApiService.syncSettingsToWorkspaces(userId);
      const partialWorkspaceCount = result.workspaces.filter((workspace) => {
        if (!workspace.details) {
          return false;
        }

        const statusList = [
          workspace.details.ssh.success,
          workspace.details.claude_code.success,
          workspace.details.codex?.success ?? true,
          workspace.details.git.success,
        ];

        return statusList.some(Boolean) && statusList.some((status) => !status);
      }).length;
      const failedWorkspaceCount = result.workspaces.filter((workspace) => !workspace.success).length;

      if (result.success) {
        setNeedsSync(false);
        toast({
          title: t('pages.settings.notifications.syncSuccess.title'),
          description: t('pages.settings.notifications.syncSuccess.description', { count: result.workspaces.length }),
        });
      } else if (partialWorkspaceCount > 0) {
        toast({
          title: t('pages.settings.notifications.syncPartial.title'),
          description: t('pages.settings.notifications.syncPartial.description', { count: partialWorkspaceCount }),
          variant: 'destructive',
        });
      } else if (failedWorkspaceCount > 0) {
        toast({
          title: t('pages.settings.notifications.syncFailed.title'),
          description: t('pages.settings.notifications.syncFailed.description', { count: failedWorkspaceCount }),
          variant: 'destructive',
        });
      } else {
        toast({
          title: t('pages.settings.notifications.syncFailed.title'),
          description: t('pages.settings.notifications.syncFailed.description', { count: result.workspaces.length || 0 }),
          variant: 'destructive',
        });
      }
    } catch (err) {
      logger.error('sync failed', { error: err });
      toast({
        title: t('pages.settings.notifications.syncFailed.title'),
        description: t('pages.settings.notifications.syncFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsSyncing(false);
    }
  };

  const handleReset = () => {
    if (!initialSettingsRef.current) {
      return;
    }
    syncFromSnapshot(initialSettingsRef.current);
    setError(null);
  };

  const handleCopyToClipboard = (text: string) => {
    try {
      navigator.clipboard?.writeText(text);
      toast({
        title: t('pages.settings.notifications.copied.title'),
        description: t('pages.settings.notifications.copied.description'),
      });
    } catch (err) {
      logger.error('複製內容到剪貼簿時發生錯誤', { error: err });
      toast({
        title: t('pages.settings.notifications.copyFailed.title'),
        description: t('pages.settings.notifications.copyFailed.description'),
        variant: 'destructive',
      });
    }
  };

  const handleGenerateSSHKey = async () => {
    if (!userId) {
      toast({
        title: t('pages.settings.notifications.loginRequired.title'),
        description: t('pages.settings.notifications.loginRequired.description'),
        variant: 'destructive',
      });
      return;
    }

    try {
      toast({
        title: t('pages.settings.notifications.generateKey.title'),
        description: t('pages.settings.notifications.generateKey.progress'),
      });

      const response = await apiClient.post<{
        publicKey: string;
        privateKey: string;
        fingerprint: string;
        generatedAt: string;
      }>(`/users/${userId}/ssh-keys/generate`);

      // 更新本地狀態
      setSshKeys({
        publicKey: response.publicKey,
        privateKey: response.privateKey,
        fingerprint: response.fingerprint,
        lastRotatedAt: response.generatedAt,
      });

      toast({
        title: t('pages.settings.notifications.generateKey.successTitle'),
        description: t('pages.settings.notifications.generateKey.description'),
      });
    } catch (error) {
      logger.error('產生 SSH Key 失敗', { error });
      toast({
        title: t('pages.settings.notifications.generateKey.failedTitle'),
        description: error instanceof Error ? error.message : t('pages.settings.notifications.generateKey.failedDescription'),
        variant: 'destructive',
      });
    }
  };

  // 步驟1: 點選 Claude 認證
  const handleClaudeOAuth = async () => {
    try {
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.oauthWindow.openingTitle'),
        description: t('pages.settings.sections.claudeCode.subscription.oauthWindow.openingDescription'),
      });

      // 開啟認證視窗並儲存 verifier
      const { verifier } = await OAuthService.openAuthWindow();
      oauthVerifierRef.current = verifier;

      // 步驟2: 顯示 Authentication Code 輸入欄
      setShowAuthCodeInput(true);
      setTempAuthCode('');

      toast({
        title: t('pages.settings.sections.claudeCode.subscription.oauthWindow.openedTitle'),
        description: t('pages.settings.sections.claudeCode.subscription.oauthWindow.openedDescription'),
      });
    } catch (error) {
      logger.error('開啟 OAuth 視窗失敗', { error });
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.oauthWindow.failedTitle'),
        description: error instanceof Error
          ? error.message
          : t('pages.settings.sections.claudeCode.subscription.oauthWindow.failedDescription'),
        variant: 'destructive',
      });
    }
  };

  // 取消認證輸入
  const handleCancelAuth = () => {
    setShowAuthCodeInput(false);
    setTempAuthCode('');
    oauthVerifierRef.current = null;
    OAuthService.clearVerifier();
  };

  // 儲存 Authentication Code 並呼叫後端 authenticate API（會自動儲存到資料庫）
  const handleSaveAuthCode = async () => {
    if (!tempAuthCode.trim() || !oauthVerifierRef.current) {
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.errors.emptyCode'),
        variant: 'destructive',
      });
      return;
    }

    // 檢查用戶是否已登入
    if (!userId) {
      toast({
        title: t('pages.settings.notifications.loginRequired.title'),
        description: t('pages.settings.sections.claudeCode.subscription.errors.loginRequired'),
        variant: 'destructive',
      });
      return;
    }

    setIsExchangingCode(true);
    try {
      logger.debug('Starting OAuth authentication', {
        userId,
        authCode: tempAuthCode.substring(0, 20) + '...',
        verifier: oauthVerifierRef.current?.substring(0, 20) + '...',
      });

      toast({
        title: t('pages.settings.sections.claudeCode.subscription.verifying'),
        description: t('pages.settings.sections.claudeCode.subscription.pleaseWait'),
      });

      // 呼叫後端 authenticate API，會自動完成 OAuth exchange 並儲存到資料庫
      logger.debug('Calling authenticate API');
      const result = await OAuthApiService.authenticate(
        tempAuthCode,
        oauthVerifierRef.current
      );
      logger.debug('Authentication successful', { result });

      // 更新本地狀態，包括 oauthAccount 資訊；清空 model 避免帶入舊值
      setClaudeCodeSettings(prev => prev ? {
        ...prev,
        subscriptionAuthCode: tempAuthCode,
        subscriptionAccessToken: result.accessToken,
        subscriptionRefreshToken: result.refreshToken,
        subscriptionExpiresAt: result.expiresAt,
        oauthAccount: result.oauthAccount,  // 更新 OAuth 帳戶資訊
        model: '',
      } : prev);

      // 清除 verifier 和臨時狀態
      oauthVerifierRef.current = null;
      OAuthService.clearVerifier();
      setShowAuthCodeInput(false);
      setTempAuthCode('');

      // 如果後端提示需要同步，設置標記
      if (result.needsSync) {
        setNeedsSync(true);
      }

      toast({
        title: t('pages.settings.sections.claudeCode.subscription.success.title'),
        description: result.needsSync
          ? t('pages.settings.sections.claudeCode.subscription.success.syncDescription')
          : t('pages.settings.sections.claudeCode.subscription.success.description'),
      });
    } catch (error) {
      logger.error('OAuth 認證失敗', { error });

      // 特別處理未認證錯誤
      const errorMessage = error instanceof Error ? error.message : '';
      if (errorMessage.includes('Unauthorized') || errorMessage.includes('User not authenticated')) {
        toast({
          title: t('pages.settings.sections.claudeCode.subscription.errors.sessionExpiredTitle'),
          description: t('pages.settings.sections.claudeCode.subscription.errors.sessionExpiredDescription'),
          variant: 'destructive',
        });
      } else {
        toast({
          title: t('pages.settings.sections.claudeCode.subscription.errors.authFailed'),
          description: errorMessage || t('pages.settings.sections.claudeCode.subscription.errors.unknown'),
          variant: 'destructive',
        });
      }
    } finally {
      setIsExchangingCode(false);
    }
  };

  // 步驟3: 取消認證（清除 access token）
  const handleDisconnectAuth = async () => {
    if (!userId) {
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.disconnect.loginRequiredTitle'),
        description: t('pages.settings.notifications.loginRequired.description'),
        variant: 'destructive',
      });
      return;
    }

    if (!claudeCodeSettings) {
      return;
    }

    try {
      // 立即更新本地狀態
      const updatedSettings = {
        ...claudeCodeSettings,
        subscriptionAuthCode: '',
        subscriptionAccessToken: '',
        subscriptionRefreshToken: '',
        subscriptionExpiresAt: undefined,
        oauthAccount: undefined,
      };
      setClaudeCodeSettings(updatedSettings);

      // 立即儲存到資料庫
      await apiClient.put<UserSettingsResponse>(`/users/${userId}/settings`, {
        general: generalSettings,
        ssh: {
          publicKey: sshKeys?.publicKey,
          privateKey: sshKeys?.privateKey,
          fingerprint: sshKeys?.fingerprint,
          lastRotatedAt: sshKeys?.lastRotatedAt,
        },
        claudeCode: updatedSettings,
        git: gitSettings,
      });

      toast({
        title: t('pages.settings.sections.claudeCode.subscription.disconnect.successTitle'),
        description: t('pages.settings.sections.claudeCode.subscription.disconnect.successDescription'),
      });
    } catch (error) {
      logger.error('取消認證失敗', { error });
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.disconnect.failedTitle'),
        description: error instanceof Error ? error.message : t('pages.settings.sections.claudeCode.subscription.disconnect.failedDescription'),
        variant: 'destructive',
      });
      // 失敗時重新載入設定
      void fetchSettings();
    }
  };

  const handleCodexSignIn = async () => {
    if (!userId) {
      return;
    }
    const authWindow = window.open('about:blank', '_blank');
    setIsCodexAuthLoading(true);
    try {
      const response = await apiClient.post<{ success: boolean; codex: UserSettingsCodex }>(
        `/users/${userId}/settings/codex/login/start`,
        {},
      );
      setCodexSettings(response.codex);
      setNeedsSync(true);

      const verificationUrl = response.codex.authFlow?.verificationUrl;
      if (verificationUrl) {
        if (authWindow) {
          authWindow.opener = null;
          authWindow.location.href = verificationUrl;
          toast({
            title: t('pages.settings.sections.codex.login.window.openedTitle'),
            description: t('pages.settings.sections.codex.login.window.openedDescription'),
          });
        } else {
          const openedWindow = window.open(verificationUrl, '_blank', 'noopener,noreferrer');
          if (!openedWindow) {
            toast({
              title: t('pages.settings.sections.codex.login.window.blockedTitle'),
              description: t('pages.settings.sections.codex.login.window.blockedDescription'),
              variant: 'destructive',
            });
          }
        }
      } else {
        authWindow?.close();
      }
    } catch (err) {
      authWindow?.close();
      logger.error('codex login start failed', { error: err });
      toast({
        title: t('pages.settings.sections.codex.login.errors.startFailedTitle'),
        description: t('pages.settings.sections.codex.login.errors.startFailedDescription'),
        variant: 'destructive',
      });
    } finally {
      setIsCodexAuthLoading(false);
    }
  };

  const handleCodexRefreshStatus = async () => {
    if (!userId) {
      return;
    }
    setIsCodexAuthLoading(true);
    try {
      const response = await apiClient.get<{ success: boolean; codex: UserSettingsCodex }>(
        `/users/${userId}/settings/codex/login/status`,
      );
      setCodexSettings(response.codex);
    } catch (err) {
      logger.error('codex login status failed', { error: err });
    } finally {
      setIsCodexAuthLoading(false);
    }
  };

  const handleCodexLogout = async () => {
    if (!userId) {
      return;
    }
    setIsCodexAuthLoading(true);
    try {
      const response = await apiClient.post<{ success: boolean; codex: UserSettingsCodex }>(
        `/users/${userId}/settings/codex/logout`,
        {},
      );
      setCodexSettings(response.codex);
      setNeedsSync(true);
    } catch (err) {
      logger.error('codex logout failed', { error: err });
      toast({
        title: t('pages.settings.sections.codex.login.errors.logoutFailedTitle'),
        description: t('pages.settings.sections.codex.login.errors.logoutFailedDescription'),
        variant: 'destructive',
      });
    } finally {
      setIsCodexAuthLoading(false);
    }
  };

  const handleCodexCancelLogin = async () => {
    if (!userId) {
      return;
    }
    setIsCodexAuthLoading(true);
    try {
      const response = await apiClient.post<{ success: boolean; codex: UserSettingsCodex }>(
        `/users/${userId}/settings/codex/login/cancel`,
        {},
      );
      setCodexSettings(response.codex);
    } catch (err) {
      logger.error('codex login cancel failed', { error: err });
    } finally {
      setIsCodexAuthLoading(false);
    }
  };

  const hasSettings = Boolean(generalSettings && sshKeys && claudeCodeSettings && codexSettings && gitSettings);

  return (
    <div className="flex h-screen flex-col bg-background">
      <GlobalNavigation />
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="container mx-auto py-8 px-6 max-w-4xl flex flex-col flex-1 space-y-6 overflow-hidden">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground">{t('pages.settings.title')}</h1>
              <p className="text-muted-foreground mt-1">{t('pages.settings.subtitle')}</p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" onClick={handleReset} className="gap-2" disabled={!hasSettings || isSaving}>
                <RefreshCw className="h-4 w-4" />
                {t('pages.settings.actions.resetDefaults')}
              </Button>
              <Button
                variant={needsSync ? "default" : "outline"}
                onClick={handleSync}
                disabled={!hasSettings || isSyncing}
                className="gap-2"
              >
                <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                {isSyncing ? t('pages.settings.actions.syncing') : t('pages.settings.actions.syncWorkspace')}
              </Button>
              <Button onClick={handleSave} disabled={!hasSettings || isSaving} className="gap-2">
                <Save className="h-4 w-4" />
                {isSaving ? t('pages.settings.actions.saving') : t('pages.settings.actions.save')}
              </Button>
            </div>
          </div>

          {error && (
            <div role="alert" className="rounded-md border border-destructive bg-destructive/10 text-destructive px-4 py-3">
              {error}
            </div>
          )}

          {isLoading && (
            <div className="rounded-md border border-border px-4 py-6 text-muted-foreground">
              {t('pages.settings.status.loading')}
            </div>
          )}

          {hasSettings && generalSettings && sshKeys && claudeCodeSettings && codexSettings && gitSettings && (
            <Tabs defaultValue="general" className="w-full flex-1 flex flex-col min-h-0">
              <TabsList className="flex w-full overflow-x-auto flex-shrink-0">
                <TabsTrigger value="general">{t('pages.settings.tabs.general')}</TabsTrigger>
                <TabsTrigger value="ssh">{t('pages.settings.tabs.ssh')}</TabsTrigger>
                <TabsTrigger value="claude-code">{t('pages.settings.tabs.claudeCode')}</TabsTrigger>
                <TabsTrigger value="gemini">{t('pages.settings.tabs.gemini')}</TabsTrigger>
                <TabsTrigger value="opencode">{t('pages.settings.tabs.opencode')}</TabsTrigger>
                <TabsTrigger value="codex">{t('pages.settings.tabs.codex')}</TabsTrigger>
                <TabsTrigger value="git">{t('pages.settings.tabs.git')}</TabsTrigger>
              </TabsList>

              {/* 一般設定：外觀/語言/時區 */}
              <TabsContent value="general" className="flex-1 overflow-auto min-h-0">
                <div className="space-y-6 p-1">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Palette className="h-5 w-5" />{t('pages.settings.sections.appearance.title')}
                      </CardTitle>
                      <CardDescription>{t('pages.settings.sections.appearance.description')}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <Label>{t('pages.settings.sections.appearance.theme.label')}</Label>
                          <p className="text-sm text-muted-foreground">{t('pages.settings.sections.appearance.theme.description')}</p>
                        </div>
                        <Select
                          value={generalSettings.theme}
                          onValueChange={(value: UserSettingsGeneral['theme']) => {
                            setGeneralSettings(prev => (prev ? { ...prev, theme: value } : prev));
                            dispatch({ type: 'SET_THEME', payload: value });
                          }}
                        >
                          <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="light">
                              <div className="flex items-center gap-2"><Sun className="h-4 w-4" />{t('pages.settings.sections.appearance.theme.options.light')}</div>
                            </SelectItem>
                            <SelectItem value="dark">
                              <div className="flex items-center gap-2"><Moon className="h-4 w-4" />{t('pages.settings.sections.appearance.theme.options.dark')}</div>
                            </SelectItem>
                            <SelectItem value="system">
                              <div className="flex items-center gap-2"><Monitor className="h-4 w-4" />{t('pages.settings.sections.appearance.theme.options.system')}</div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <Separator />

                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <Label>{t('pages.settings.sections.appearance.language.label')}</Label>
                          <p className="text-sm text-muted-foreground">{t('pages.settings.sections.appearance.language.description')}</p>
                        </div>
                        <Select
                          value={generalSettings.language}
                          onValueChange={(value: UserSettingsGeneral['language']) => {
                            setGeneralSettings(prev => (prev ? { ...prev, language: value } : prev));
                            dispatch({ type: 'SET_LANGUAGE', payload: value });
                            void changeLanguage(value as SupportedLanguage);
                          }}
                        >
                          <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="zh-TW">
                              <div className="flex items-center gap-2"><Globe className="h-4 w-4" />{t('pages.settings.sections.appearance.language.options.zhTW')}</div>
                            </SelectItem>
                            <SelectItem value="en">
                              <div className="flex items-center gap-2"><Globe className="h-4 w-4" />{t('pages.settings.sections.appearance.language.options.en')}</div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <Separator />

                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <Label>{t('pages.settings.sections.appearance.timezone.label')}</Label>
                          <p className="text-sm text-muted-foreground">{t('pages.settings.sections.appearance.timezone.description')}</p>
                        </div>
                        <Select
                          value={generalSettings.timezone}
                          onValueChange={(value) =>
                            setGeneralSettings(prev => (prev ? { ...prev, timezone: value } : prev))
                          }
                        >
                          <SelectTrigger className="w-60"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="UTC">{t('pages.settings.sections.appearance.timezone.options.utc')}</SelectItem>
                            <SelectItem value="Asia/Taipei">{t('pages.settings.sections.appearance.timezone.options.taipei')}</SelectItem>
                            <SelectItem value="Asia/Tokyo">{t('pages.settings.sections.appearance.timezone.options.tokyo')}</SelectItem>
                            <SelectItem value="Europe/London">{t('pages.settings.sections.appearance.timezone.options.london')}</SelectItem>
                            <SelectItem value="America/Los_Angeles">{t('pages.settings.sections.appearance.timezone.options.losAngeles')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* SSH Keys */}
              <TabsContent value="ssh" className="flex-1 overflow-auto min-h-0">
                <div className="space-y-6 p-1">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><Key className="h-5 w-5" />{t('pages.settings.sections.ssh.title')}</CardTitle>
                      <CardDescription>{t('pages.settings.sections.ssh.description')}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="privateKey">{t('pages.settings.sections.ssh.privateKey.label')}</Label>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm" onClick={() => setShowPrivateKey(!showPrivateKey)}>
                              {showPrivateKey
                                ? t('pages.settings.sections.ssh.privateKey.actions.hide')
                                : t('pages.settings.sections.ssh.privateKey.actions.show')}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => sshKeys?.privateKey && handleCopyToClipboard(sshKeys.privateKey)}
                            >
                              {t('pages.settings.sections.ssh.privateKey.actions.copy')}
                            </Button>
                          </div>
                        </div>
                        <Textarea
                          id="privateKey"
                          placeholder={t('pages.settings.sections.ssh.privateKey.placeholder')}
                          value={showPrivateKey ? (sshKeys.privateKey || '') : '••••••••••••'}
                          onChange={(e) =>
                            setSshKeys(prev => (prev ? { ...prev, privateKey: e.target.value } : prev))
                          }
                          className="font-mono text-sm"
                          disabled={!showPrivateKey}
                          rows={8}
                        />
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="publicKey">{t('pages.settings.sections.ssh.publicKey.label')}</Label>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => sshKeys?.publicKey && handleCopyToClipboard(sshKeys.publicKey)}
                          >
                            {t('pages.settings.sections.ssh.publicKey.copy')}
                          </Button>
                        </div>
                        <Textarea
                          id="publicKey"
                          placeholder={t('pages.settings.sections.ssh.publicKey.placeholder')}
                          value={sshKeys.publicKey || ''}
                          onChange={(e) =>
                            setSshKeys(prev => (prev ? { ...prev, publicKey: e.target.value } : prev))
                          }
                          className="font-mono text-sm"
                          rows={4}
                        />
                      </div>
                      <Button onClick={handleGenerateSSHKey} variant="outline">
                        {t('pages.settings.sections.ssh.generate')}
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* Claude Code */}
              <TabsContent value="claude-code" className="flex-1 overflow-auto min-h-0">
                <div className="space-y-6 p-1">
                  {/* 認證方式選擇 */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Shield className="h-5 w-5" />
                        {t('pages.settings.sections.claudeCode.title')}
                      </CardTitle>
                      <CardDescription>{t('pages.settings.sections.claudeCode.description')}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* 認證方式下拉選單 */}
                      <div className="space-y-2">
                        <Label>{t('pages.settings.sections.claudeCode.authMethod.label')}</Label>
                        <Select
                          value={claudeCodeSettings.authMethod || 'subscription'}
                          onValueChange={(value) =>
                            setClaudeCodeSettings(prev => (prev ? { ...prev, authMethod: value } : prev))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder={t('pages.settings.sections.claudeCode.authMethod.description')} />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="subscription">{t('pages.settings.sections.claudeCode.authMethod.options.subscription')}</SelectItem>
                            <SelectItem value="apikey">{t('pages.settings.sections.claudeCode.authMethod.options.apikey')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <Separator />

                      {/* Subscription 認證 */}
                      {claudeCodeSettings.authMethod === 'subscription' && (
                        <div className="space-y-4">
                          {/* 已連接狀態 - 依照資料庫的 subscriptionAccessToken 決定 */}
                          {claudeCodeSettings.subscriptionAccessToken && !showAuthCodeInput && (
                            <div className="space-y-4">
                              <div className="flex items-center gap-3">
                                <h3 className="text-lg font-semibold">{t('pages.settings.sections.claudeCode.subscription.title')}</h3>
                                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary dark:bg-primary/15 dark:text-primary-foreground">
                                  <span className="h-2 w-2 rounded-full bg-primary"></span>
                                  {t('pages.settings.sections.claudeCode.subscription.status.connected')}
                                </span>
                              </div>

                              <div className="space-y-2">
                                <p className="text-sm text-muted-foreground">
                                  {t('pages.settings.sections.claudeCode.subscription.account')}: <span className="font-mono text-foreground">
                                    {claudeCodeSettings.oauthAccount?.emailAddress || appState.user.email || 'N/A'}
                                    {claudeCodeSettings.oauthAccount?.displayName && (
                                      <span className="ml-2 font-sans text-muted-foreground">({claudeCodeSettings.oauthAccount.displayName})</span>
                                    )}
                                  </span>
                                </p>
                                <p className="text-sm text-muted-foreground">
                                  {t('pages.settings.sections.claudeCode.subscription.description')}
                                </p>
                              </div>

                              {/* 模型選擇 */}
                              <div className="space-y-2">
                                <Label>{t('pages.settings.sections.claudeCode.apikey.modelLabel')}</Label>
                                <Input
                                  placeholder={t('pages.settings.sections.claudeCode.apikey.modelPlaceholder')}
                                  value={claudeCodeSettings.model || ''}
                                  onChange={(e) =>
                                    setClaudeCodeSettings(prev => (prev ? { ...prev, model: e.target.value } : prev))
                                  }
                                  className="font-mono"
                                />
                                <p className="text-xs text-muted-foreground">
                                  {t('pages.settings.sections.claudeCode.apikey.modelHelp')}
                                </p>
                              </div>

                              <Button
                                type="button"
                                variant="outline"
                                onClick={handleDisconnectAuth}
                                className="text-muted-foreground hover:text-foreground"
                              >
                                {t('pages.settings.sections.claudeCode.subscription.disconnectButton')}
                              </Button>
                            </div>
                          )}

                          {/* 未連接狀態 - 步驟1 */}
                          {!claudeCodeSettings.subscriptionAccessToken && !showAuthCodeInput && (
                            <div className="space-y-4">
                              <div className="flex items-center gap-3">
                                <h3 className="text-lg font-semibold">{t('pages.settings.sections.claudeCode.subscription.title')}</h3>
                                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                                  <span className="h-2 w-2 rounded-full bg-red-500"></span>
                                  {t('pages.settings.sections.claudeCode.subscription.status.notConnected')}
                                </span>
                              </div>

                              <Button
                                type="button"
                                onClick={handleClaudeOAuth}
                                className="w-fit"
                              >
                                {t('pages.settings.sections.claudeCode.subscription.connectButton')}
                              </Button>
                            </div>
                          )}

                          {/* 輸入 Authentication Code - 步驟2 */}
                          {showAuthCodeInput && (
                            <div className="space-y-4">
                              <div className="flex items-center gap-3">
                                <h3 className="text-lg font-semibold">{t('pages.settings.sections.claudeCode.subscription.title')}</h3>
                                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                                  <span className="h-2 w-2 rounded-full bg-red-500"></span>
                                  {t('pages.settings.sections.claudeCode.subscription.status.notConnected')}
                                </span>
                              </div>

                              <p className="text-sm text-muted-foreground">
                                {t('pages.settings.sections.claudeCode.subscription.authCodeHint')}
                              </p>

                              <Input
                                placeholder={t('pages.settings.sections.claudeCode.subscription.authCodePlaceholder')}
                                value={tempAuthCode}
                                onChange={(e) => setTempAuthCode(e.target.value)}
                                className="font-mono"
                                disabled={isExchangingCode}
                              />

                              {isExchangingCode && (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                  <RefreshCw className="h-4 w-4 animate-spin" />
                                  <span>{t('pages.settings.sections.claudeCode.subscription.verifying')}</span>
                                </div>
                              )}

                              <div className="flex gap-2">
                                <Button
                                  type="button"
                                  onClick={handleSaveAuthCode}
                                  disabled={isExchangingCode || !tempAuthCode.trim()}
                                  className="bg-primary hover:bg-primary/90 text-primary-foreground"
                                >
                                  {t('pages.settings.sections.claudeCode.subscription.saveButton')}
                                </Button>
                                <Button
                                  type="button"
                                  variant="outline"
                                  onClick={handleCancelAuth}
                                  disabled={isExchangingCode}
                                >
                                  {t('pages.settings.sections.claudeCode.subscription.cancelButton')}
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* API Key 認證 */}
                      {claudeCodeSettings.authMethod === 'apikey' && (
                        <div className="space-y-4">
                          {/* API 廠商選擇 */}
                          <div className="space-y-2">
                            <Label>{t('pages.settings.sections.claudeCode.apikey.providerLabel')}</Label>
                            <Select
                              value={claudeCodeSettings.apiProvider || ''}
                              onValueChange={(value) =>
                                setClaudeCodeSettings(prev => (prev ? { ...prev, apiProvider: value } : prev))
                              }
                            >
                              <SelectTrigger>
                                <SelectValue placeholder={t('pages.settings.sections.claudeCode.apikey.providerPlaceholder')} />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="anthropic">{t('pages.settings.sections.claudeCode.apikey.providerOptions.anthropic')}</SelectItem>
                                <SelectItem value="aws-bedrock">{t('pages.settings.sections.claudeCode.apikey.providerOptions.awsBedrock')}</SelectItem>
                                <SelectItem value="google-vertex-ai">{t('pages.settings.sections.claudeCode.apikey.providerOptions.googleVertexAi')}</SelectItem>
                                <SelectItem value="other">{t('pages.settings.sections.claudeCode.apikey.providerOptions.other')}</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          {/* 模型選擇 */}
                          <div className="space-y-2">
                            <Label>{t('pages.settings.sections.claudeCode.apikey.modelLabel')}</Label>
                            <Input
                              placeholder={t('pages.settings.sections.claudeCode.apikey.modelPlaceholder')}
                              value={claudeCodeSettings.model || ''}
                              onChange={(e) =>
                                setClaudeCodeSettings(prev => (prev ? { ...prev, model: e.target.value } : prev))
                              }
                              className="font-mono"
                            />
                            <p className="text-xs text-muted-foreground">
                              {t('pages.settings.sections.claudeCode.apikey.modelHelp')}
                            </p>
                          </div>

                          {/* 環境變數設定 */}
                          <EnvironmentVariables
                            value={claudeCodeSettings.environmentVariables || []}
                            onChange={(variables) =>
                              setClaudeCodeSettings(prev => (prev ? { ...prev, environmentVariables: variables } : prev))
                            }
                          />
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* Gemini 設定 */}
              <TabsContent value="gemini" className="flex-1 overflow-auto min-h-0">
                <div className="space-y-6 p-1">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5" />
                        {t('pages.settings.tabs.gemini')}
                      </CardTitle>
                      <CardDescription>{t('workspace.agentSettings.common.comingSoon.description', { feature: t('pages.settings.tabs.gemini'), toolName: 'Gemini' })}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-col items-center justify-center gap-4 py-8 text-center">
                        <Construction className="h-12 w-12 text-muted-foreground/50" />
                        <p className="text-sm text-muted-foreground">{t('workspace.agentSettings.common.comingSoon.title')}</p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* OpenCode 設定 */}
              <TabsContent value="opencode" className="flex-1 overflow-auto min-h-0">
                <div className="space-y-6 p-1">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Globe className="h-5 w-5" />
                        {t('pages.settings.tabs.opencode')}
                      </CardTitle>
                      <CardDescription>{t('workspace.agentSettings.common.comingSoon.description', { feature: t('pages.settings.tabs.opencode'), toolName: 'OpenCode' })}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-col items-center justify-center gap-4 py-8 text-center">
                        <Construction className="h-12 w-12 text-muted-foreground/50" />
                        <p className="text-sm text-muted-foreground">{t('workspace.agentSettings.common.comingSoon.title')}</p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* Codex 設定 */}
              <TabsContent value="codex" className="flex-1 overflow-auto min-h-0">
                <div className="space-y-6 p-1">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Bot className="h-5 w-5" />
                        {t('pages.settings.tabs.codex')}
                      </CardTitle>
                      <CardDescription>{t('pages.settings.sections.codex.description')}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-muted/30 p-4">
                        <div className="space-y-2">
                          <div className="flex items-center gap-3">
                            <h3 className="text-lg font-semibold">{t('pages.settings.sections.codex.login.title')}</h3>
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                              <span className="h-2 w-2 rounded-full bg-primary"></span>
                              {t(`pages.settings.sections.codex.login.status.${codexSettings.loginStatus}`)}
                            </span>
                          </div>
                          {codexSettings.account?.email ? (
                            <p className="text-sm text-muted-foreground">
                              {t('pages.settings.sections.codex.login.account')}: <span className="font-mono text-foreground">{codexSettings.account.email}</span>
                            </p>
                          ) : (
                            <p className="text-sm text-muted-foreground">
                              {t('pages.settings.sections.codex.login.notConnectedDescription')}
                            </p>
                          )}
                          {codexSettings.authFlow?.verificationUrl && (
                            <div className="space-y-1 text-sm text-muted-foreground">
                              <p>
                                {t('pages.settings.sections.codex.login.deviceCode', {
                                  code: codexSettings.authFlow.userCode || '',
                                })}
                              </p>
                              <a
                                href={codexSettings.authFlow.verificationUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex font-medium text-primary underline-offset-4 hover:underline"
                              >
                                {t('pages.settings.sections.codex.login.openVerificationLink')}
                              </a>
                            </div>
                          )}
                        </div>
                        <div className="flex shrink-0 gap-2">
                          {codexSettings.loginStatus === 'pending' ? (
                            <>
                              <Button variant="outline" onClick={handleCodexRefreshStatus} disabled={isCodexAuthLoading}>
                                {t('pages.settings.sections.codex.login.refreshButton')}
                              </Button>
                              <Button variant="outline" onClick={handleCodexCancelLogin} disabled={isCodexAuthLoading}>
                                {t('pages.settings.sections.codex.login.cancelButton')}
                              </Button>
                            </>
                          ) : codexSettings.loginStatus === 'connected' ? (
                            <Button variant="outline" onClick={handleCodexLogout} disabled={isCodexAuthLoading}>
                              {t('pages.settings.sections.codex.login.logoutButton')}
                            </Button>
                          ) : (
                            <Button
                              variant="outline"
                              onClick={handleCodexSignIn}
                              disabled={isCodexAuthLoading}
                            >
                              {t('pages.settings.sections.codex.login.signInButton')}
                            </Button>
                          )}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label>{t('pages.settings.sections.codex.model.label')}</Label>
                        <Input
                          placeholder={t('pages.settings.sections.codex.model.placeholder')}
                          value={codexSettings.model || ''}
                          onChange={(e) =>
                            setCodexSettings(prev => (prev ? { ...prev, model: e.target.value } : prev))
                          }
                          className="font-mono"
                        />
                        <p className="text-xs text-muted-foreground">
                          {t('pages.settings.sections.codex.model.help')}
                        </p>
                      </div>

                      <EnvironmentVariables
                        value={codexSettings.environmentVariables || []}
                        onChange={(variables) =>
                          setCodexSettings(prev => (prev ? { ...prev, environmentVariables: variables } : prev))
                        }
                        title={t('pages.settings.sections.codex.environmentVariables.title')}
                        description={t('pages.settings.sections.codex.environmentVariables.description')}
                      />
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* Git 設定 */}
              <TabsContent value="git" className="flex-1 overflow-auto min-h-0">
                <div className="space-y-6 p-1">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2"><GitBranch className="h-5 w-5" />{t('pages.settings.sections.git.title')}</CardTitle>
                      <CardDescription>{t('pages.settings.sections.git.description')}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="gitUserName">{t('pages.settings.sections.git.userName.label')}</Label>
                        <Input
                          id="gitUserName"
                          type="text"
                          placeholder={t('pages.settings.sections.git.userName.placeholder')}
                          value={gitSettings.userName}
                          onChange={(e) =>
                            setGitSettings(prev => (prev ? { ...prev, userName: e.target.value } : prev))
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="gitUserEmail">{t('pages.settings.sections.git.userEmail.label')}</Label>
                        <Input
                          id="gitUserEmail"
                          type="email"
                          placeholder={t('pages.settings.sections.git.userEmail.placeholder')}
                          value={gitSettings.userEmail}
                          onChange={(e) =>
                            setGitSettings(prev => (prev ? { ...prev, userEmail: e.target.value } : prev))
                          }
                        />
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
