import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { createLogger } from '@/shared/services/logger';
import { Button } from '@/shared/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { useToast } from '@/shared/components/ui/use-toast';
import GlobalNavigation from '@/app/components/navigation/GlobalNavigation';
import {
  Save,
  RefreshCw,
} from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useApp } from '@/app/providers/AppProvider';
import type { SupportedLanguage } from '@/shared/types/i18n';
import { ApiError, apiClient } from '@/shared/api/apiClient';
import { authenticateOAuth } from './settings/oauthApi';
import { clearOAuthVerifier, openOAuthWindow } from './settings/oauthFlow';
import type {
  UserSettings,
  UserSettingsGeneral,
  UserSettingsSSH,
  UserSettingsClaudeCode,
  UserSettingsCodex,
  UserSettingsOpenCode,
  UserSettingsGit,
  UserSettingsResponse,
} from '@/shared/types/user';
import {
  cloneDeep,
  getPartialSyncWorkspaceCount,
  normalizeCodexSettings,
  normalizeModelSelection,
  normalizeOpenCodeSettings,
} from './settingsPageModel';
import { SettingsGeneralTab } from './settings/SettingsGeneralTab';
import { SettingsSshTab } from './settings/SettingsSshTab';
import { SettingsCodexTab } from './settings/SettingsCodexTab';
import { SettingsGitTab } from './settings/SettingsGitTab';
import { SettingsClaudeCodeTab } from './settings/SettingsClaudeCodeTab';
import { SettingsOpenCodeTab } from './settings/SettingsOpenCodeTab';

const logger = createLogger('SettingsPage');

export const SettingsPage: React.FC = () => {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { t, changeLanguage } = useI18n();
  const { state: appState, dispatch } = useApp();
  const canSyncSettingsToWorkspaces = true;
  const userId = appState.user.id;

  const [generalSettings, setGeneralSettings] = useState<UserSettingsGeneral | null>(null);
  const [sshKeys, setSshKeys] = useState<UserSettingsSSH | null>(null);
  const [claudeCodeSettings, setClaudeCodeSettings] = useState<UserSettingsClaudeCode | null>(null);
  const [codexSettings, setCodexSettings] = useState<UserSettingsCodex | null>(null);
  const [opencodeSettings, setOpenCodeSettings] = useState<UserSettingsOpenCode | null>(null);
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
  const fetchSettingsRef = useRef<(() => Promise<void>) | null>(null);

  const syncFromSnapshot = useCallback(
    (snapshot: UserSettings) => {
      initialSettingsRef.current = cloneDeep(snapshot);
      setGeneralSettings(cloneDeep(snapshot.general));
      setSshKeys(cloneDeep(snapshot.ssh));

      const claudeCodeWithDefaults = {
        authMethod: 'subscription',
        environmentVariables: [],
        ...cloneDeep(snapshot.claudeCode),
        modelSelection: normalizeModelSelection(
          snapshot.claudeCode?.modelSelection,
        ),
      };
      setClaudeCodeSettings(claudeCodeWithDefaults);

      setCodexSettings(normalizeCodexSettings(cloneDeep(snapshot.codex)));
      setOpenCodeSettings(normalizeOpenCodeSettings(cloneDeep(snapshot.opencode)));

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
    fetchSettingsRef.current = fetchSettings;
  }, [fetchSettings]);

  useEffect(() => {
    void fetchSettingsRef.current?.();
  }, [userId]);

  const handleSave = async () => {
    if (!userId) {
      toast({
        title: t('pages.settings.notifications.saveLoginRequired.title'),
        description: t('pages.settings.notifications.saveLoginRequired.description'),
        variant: 'destructive',
      });
      return;
    }
    if (!generalSettings || !sshKeys || !claudeCodeSettings || !codexSettings || !opencodeSettings || !gitSettings) {
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
          modelSelection: claudeCodeSettings.modelSelection,
        },
        codex: {
          authMethod: codexSettings.authMethod || 'subscription',
          loginStatus: codexSettings.loginStatus,
          account: codexSettings.account,
          model: codexSettings.model || '',
          environmentVariables: codexSettings.authMethod === 'apikey' ? codexSettings.environmentVariables : [],
          authFlow: codexSettings.authFlow,
          lastSyncedAt: codexSettings.lastSyncedAt,
          lastSyncError: codexSettings.lastSyncError,
          modelSelection: codexSettings.modelSelection,
        },
        opencode: {
          model: opencodeSettings.model || opencodeSettings.modelSelection.defaultModel,
          environmentVariables: opencodeSettings.environmentVariables || [],
          modelSelection: opencodeSettings.modelSelection,
        },
        git: {
          userName: gitSettings.userName,
          userEmail: gitSettings.userEmail,
          signingKey: gitSettings.signingKey,
        },
      });

      syncFromSnapshot(response.data);
      void queryClient.invalidateQueries({ queryKey: ['ai-chat', 'capabilities'] });

      toast({
        title: t('pages.settings.notifications.saved.title'),
        description: t('pages.settings.notifications.saved.description'),
      });

      if (canSyncSettingsToWorkspaces) {
        handleSync().catch(err => {
          logger.error('auto-sync failed after save', { error: err });
        });
      }
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
    if (!canSyncSettingsToWorkspaces) {
      return;
    }

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
      const { syncSettingsToWorkspaces } = await import('./settings/settingsSyncApi');
      const result = await syncSettingsToWorkspaces(userId);
      const partialWorkspaceCount = getPartialSyncWorkspaceCount(result.workspaces);
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
      logger.error('Failed to copy content to clipboard', { error: err });
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
      logger.error('Failed to generate SSH key', { error });
      toast({
        title: t('pages.settings.notifications.generateKey.failedTitle'),
        description: error instanceof Error ? error.message : t('pages.settings.notifications.generateKey.failedDescription'),
        variant: 'destructive',
      });
    }
  };

  const handleClaudeOAuth = async () => {
    try {
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.oauthWindow.openingTitle'),
        description: t('pages.settings.sections.claudeCode.subscription.oauthWindow.openingDescription'),
      });

      const { verifier } = await openOAuthWindow();
      oauthVerifierRef.current = verifier;

      setShowAuthCodeInput(true);
      setTempAuthCode('');

      toast({
        title: t('pages.settings.sections.claudeCode.subscription.oauthWindow.openedTitle'),
        description: t('pages.settings.sections.claudeCode.subscription.oauthWindow.openedDescription'),
      });
    } catch (error) {
      logger.error('Failed to open OAuth window', { error });
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.oauthWindow.failedTitle'),
        description: error instanceof Error
          ? error.message
          : t('pages.settings.sections.claudeCode.subscription.oauthWindow.failedDescription'),
        variant: 'destructive',
      });
    }
  };

  const handleCancelAuth = () => {
    setShowAuthCodeInput(false);
    setTempAuthCode('');
    oauthVerifierRef.current = null;
    clearOAuthVerifier();
  };

  const handleSaveAuthCode = async () => {
    if (!tempAuthCode.trim() || !oauthVerifierRef.current) {
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.errors.emptyCode'),
        variant: 'destructive',
      });
      return;
    }

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
      logger.debug('Starting OAuth authentication', { userId });

      toast({
        title: t('pages.settings.sections.claudeCode.subscription.verifying'),
        description: t('pages.settings.sections.claudeCode.subscription.pleaseWait'),
      });

      logger.debug('Calling authenticate API');
      const result = await authenticateOAuth(
        tempAuthCode,
        oauthVerifierRef.current
      );
      logger.debug('Authentication successful');

      setClaudeCodeSettings(prev => prev ? {
        ...prev,
        subscriptionAuthCode: tempAuthCode,
        subscriptionAccessToken: result.accessToken,
        subscriptionRefreshToken: result.refreshToken,
        subscriptionExpiresAt: result.expiresAt,
        oauthAccount: result.oauthAccount,
        model: '',
      } : prev);

      oauthVerifierRef.current = null;
      clearOAuthVerifier();
      setShowAuthCodeInput(false);
      setTempAuthCode('');

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
      logger.error('OAuth authentication failed', { error });

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
      const updatedSettings = {
        ...claudeCodeSettings,
        subscriptionAuthCode: '',
        subscriptionAccessToken: '',
        subscriptionRefreshToken: '',
        subscriptionExpiresAt: undefined,
        oauthAccount: undefined,
      };
      setClaudeCodeSettings(updatedSettings);

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
      logger.error('Failed to disconnect authentication', { error });
      toast({
        title: t('pages.settings.sections.claudeCode.subscription.disconnect.failedTitle'),
        description: error instanceof Error ? error.message : t('pages.settings.sections.claudeCode.subscription.disconnect.failedDescription'),
        variant: 'destructive',
      });
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
      setCodexSettings(prev => normalizeCodexSettings(response.codex, prev));
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
      const errorCode = err instanceof ApiError ? err.errorCode : undefined;
      const descriptionKey = errorCode === 'codex_login_service_unavailable'
        ? 'pages.settings.sections.codex.login.errors.serviceUnavailableDescription'
        : errorCode === 'codex_login_provider_error'
          ? 'pages.settings.sections.codex.login.errors.providerFailedDescription'
          : 'pages.settings.sections.codex.login.errors.startFailedDescription';
      toast({
        title: t('pages.settings.sections.codex.login.errors.startFailedTitle'),
        description: t(descriptionKey),
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
      setCodexSettings(prev => normalizeCodexSettings(response.codex, prev));
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
      setCodexSettings(prev => normalizeCodexSettings(response.codex, prev));
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
      setCodexSettings(prev => normalizeCodexSettings(response.codex, prev));
    } catch (err) {
      logger.error('codex login cancel failed', { error: err });
    } finally {
      setIsCodexAuthLoading(false);
    }
  };

  const hasSettings = Boolean(generalSettings && sshKeys && claudeCodeSettings && codexSettings && opencodeSettings && gitSettings);

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
              {canSyncSettingsToWorkspaces ? (
                <Button
                  variant={needsSync ? "default" : "outline"}
                  onClick={handleSync}
                  disabled={!hasSettings || isSyncing}
                  className="gap-2"
                >
                  <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                  {isSyncing ? t('pages.settings.actions.syncing') : t('pages.settings.actions.syncWorkspace')}
                </Button>
              ) : null}
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

          {hasSettings && generalSettings && sshKeys && claudeCodeSettings && codexSettings && opencodeSettings && gitSettings && (
            <Tabs defaultValue="general" className="w-full flex-1 flex flex-col min-h-0">
              <TabsList className="flex w-full overflow-x-auto flex-shrink-0">
                <TabsTrigger value="general">{t('pages.settings.tabs.general')}</TabsTrigger>
                <TabsTrigger value="claude-code">{t('pages.settings.tabs.claudeCode')}</TabsTrigger>
                <TabsTrigger value="codex">{t('pages.settings.tabs.codex')}</TabsTrigger>
                <TabsTrigger value="opencode">{t('pages.settings.tabs.opencode')}</TabsTrigger>
                <TabsTrigger value="ssh">{t('pages.settings.tabs.ssh')}</TabsTrigger>
                <TabsTrigger value="git">{t('pages.settings.tabs.git')}</TabsTrigger>
              </TabsList>

              <TabsContent value="general" className="flex-1 overflow-auto min-h-0">
                <SettingsGeneralTab
                  generalSettings={generalSettings}
                  onGeneralSettingsChange={setGeneralSettings}
                  onThemeChange={(theme) => {
                    setGeneralSettings(prev => (prev ? { ...prev, theme } : prev));
                    dispatch({ type: 'SET_THEME', payload: theme });
                  }}
                  onLanguageChange={(language) => {
                    setGeneralSettings(prev => (prev ? { ...prev, language } : prev));
                    dispatch({ type: 'SET_LANGUAGE', payload: language });
                    void changeLanguage(language as SupportedLanguage);
                  }}
                />
              </TabsContent>

              {/* SSH Keys */}
              <TabsContent value="ssh" className="flex-1 overflow-auto min-h-0">
                <SettingsSshTab
                  sshKeys={sshKeys}
                  showPrivateKey={showPrivateKey}
                  onSshKeysChange={setSshKeys}
                  onShowPrivateKeyChange={setShowPrivateKey}
                  onCopyPrivateKey={() => sshKeys.privateKey && handleCopyToClipboard(sshKeys.privateKey)}
                  onCopyPublicKey={() => sshKeys.publicKey && handleCopyToClipboard(sshKeys.publicKey)}
                  onGenerateSSHKey={handleGenerateSSHKey}
                />
              </TabsContent>

              <TabsContent value="claude-code" className="flex-1 overflow-auto min-h-0">
                <SettingsClaudeCodeTab
                  claudeCodeSettings={claudeCodeSettings}
                  fallbackAccountEmail={appState.user.email}
                  showAuthCodeInput={showAuthCodeInput}
                  isExchangingCode={isExchangingCode}
                  tempAuthCode={tempAuthCode}
                  onClaudeCodeSettingsChange={setClaudeCodeSettings}
                  onTempAuthCodeChange={setTempAuthCode}
                  onConnect={handleClaudeOAuth}
                  onSaveAuthCode={handleSaveAuthCode}
                  onCancelAuth={handleCancelAuth}
                  onDisconnect={handleDisconnectAuth}
                />
              </TabsContent>

              <TabsContent value="opencode" className="flex-1 overflow-auto min-h-0">
                <SettingsOpenCodeTab
                  opencodeSettings={opencodeSettings}
                  onOpenCodeSettingsChange={setOpenCodeSettings}
                />
              </TabsContent>

              <TabsContent value="codex" className="flex-1 overflow-auto min-h-0">
                <SettingsCodexTab
                  codexSettings={codexSettings}
                  isCodexAuthLoading={isCodexAuthLoading}
                  onCodexSettingsChange={setCodexSettings}
                  onSignIn={handleCodexSignIn}
                  onRefreshStatus={handleCodexRefreshStatus}
                  onLogout={handleCodexLogout}
                  onCancelLogin={handleCodexCancelLogin}
                />
              </TabsContent>

              <TabsContent value="git" className="flex-1 overflow-auto min-h-0">
                <SettingsGitTab
                  gitSettings={gitSettings}
                  onGitSettingsChange={setGitSettings}
                />
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
