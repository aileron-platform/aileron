/**
 * AgentsMdPage - 通用指令檔案編輯器
 *
 * 泛化自 ClaudeMdPage，根據 AgentToolConfig 動態設定
 * scope 選項、標題、API prefix 等。
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FileText, Loader2, RefreshCw, Save } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Button } from '@/shared/components/ui/button';
import { MarkdownEditor } from '@/shared/components/composite/MarkdownEditor';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useToast } from '@/shared/components/ui/use-toast';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { AgentToolConfig } from '../types';

export interface AgentsMdPageProps {
  config: AgentToolConfig;
}

const AgentsMdPage: React.FC<AgentsMdPageProps> = ({ config }) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();

  const i18nNs = config.i18nNamespace;
  const fileNameInterp = { fileName: config.agentsMd.fileName };

  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const runtimeLoading = workspaceRuntime.isLoading;
  const runtimeError = workspaceRuntime.error;

  const agentsMdEndpoint = config.agentsMd.apiEndpoint ?? config.agentsMd.subViewId;
  const api = useMemo(() => createAgentSettingsApi(config.apiPathPrefix, agentsMdEndpoint), [config.apiPathPrefix, agentsMdEndpoint]);

  const defaultScope = config.agentsMd.scopes[0]?.value ?? 'project';
  const [scope, setScope] = useState(defaultScope);
  const [content, setContent] = useState('');
  const [initialContent, setInitialContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [showFallbackNotice, setShowFallbackNotice] = useState(false);

  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !runtimeError);

  const runtimeStatusMessage = useMemo(() => {
    if (runtimeError) {
      return t(`${i18nNs}.agentsMd.status.runtimeUnavailable`, {
        message: runtimeError,
        ...fileNameInterp,
      });
    }
    if (!runtimeBaseUrl || !workspaceId) {
      return t(`${i18nNs}.agentsMd.status.runtimeMissing`, fileNameInterp);
    }
    return null;
  }, [runtimeError, runtimeBaseUrl, workspaceId, t, i18nNs, fileNameInterp]);

  const is404Error = useCallback((err: unknown): boolean => {
    if (err instanceof Error) {
      return err.message.includes('404');
    }
    return false;
  }, []);

  const hasChanges = content !== initialContent;

  const confirmDiscard = useCallback(() => {
    if (!hasChanges) return true;
    return window.confirm(t(`${i18nNs}.agentsMd.confirmDiscard`));
  }, [hasChanges, t, i18nNs]);

  useEffect(() => {
    if (!runtimeBaseUrl || !workspaceId || runtimeError) {
      setLoading(false);
      return;
    }

    let isMounted = true;
    const targetScope = scope;

    const loadDocument = async () => {
      setLoading(true);
      setShowFallbackNotice(false);

      try {
        const document = await api.getAgentsMd(runtimeBaseUrl, workspaceId, targetScope);
        if (!isMounted) return;
        const nextContent = document.content ?? '';
        setContent(nextContent);
        setInitialContent(nextContent);
      } catch (err) {
        if (!isMounted) return;

        if (is404Error(err)) {
          setContent('');
          setInitialContent('');
          setShowFallbackNotice(false);
        } else {
          setContent('');
          setInitialContent('');
          setShowFallbackNotice(true);
          toast({
            variant: 'destructive',
            title: t(`${i18nNs}.agentsMd.notifications.loadFailed.title`, fileNameInterp),
            description: err instanceof Error ? err.message : t(`${i18nNs}.agentsMd.notifications.loadFailed.description`, fileNameInterp),
          });
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    void loadDocument();
    return () => { isMounted = false; };
  }, [runtimeBaseUrl, workspaceId, runtimeError, scope, refreshToken, is404Error, toast, t, api, i18nNs]);

  const handleScopeChange = useCallback(
    (value: string) => {
      if (value === scope) return;
      if (!confirmDiscard()) return;
      setScope(value);
    },
    [confirmDiscard, scope],
  );

  const handleRefresh = useCallback(() => {
    if (!isRuntimeReady) {
      toast({
        variant: 'destructive',
        title: t(`${i18nNs}.agentsMd.notifications.runtimeUnavailable.title`),
        description: t(`${i18nNs}.agentsMd.notifications.runtimeUnavailable.description`),
      });
      return;
    }
    if (!confirmDiscard()) return;
    setRefreshToken((token) => token + 1);
  }, [confirmDiscard, isRuntimeReady, toast, t, i18nNs]);

  const handleSave = useCallback(async () => {
    if (!isRuntimeReady) {
      toast({
        variant: 'destructive',
        title: t(`${i18nNs}.agentsMd.notifications.runtimeUnavailable.title`),
        description: t(`${i18nNs}.agentsMd.notifications.runtimeUnavailable.description`),
      });
      return;
    }

    setSaving(true);
    try {
      await api.updateAgentsMd(runtimeBaseUrl!, workspaceId!, {
        scope,
        content,
      });
      setInitialContent(content);
      setShowFallbackNotice(false);
      toast({
        title: t(`${i18nNs}.agentsMd.notifications.saveSuccess.title`, fileNameInterp),
        description: t(`${i18nNs}.agentsMd.notifications.saveSuccess.description`, fileNameInterp),
      });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t(`${i18nNs}.agentsMd.notifications.saveFailed.title`, fileNameInterp),
        description: err instanceof Error ? err.message : t(`${i18nNs}.agentsMd.notifications.saveFailed.description`, fileNameInterp),
      });
    } finally {
      setSaving(false);
    }
  }, [content, isRuntimeReady, scope, runtimeBaseUrl, t, toast, workspaceId, api, i18nNs]);

  const saveDisabled = !isRuntimeReady || loading || saving || !hasChanges;
  const refreshDisabled = !isRuntimeReady || loading || saving || runtimeLoading;

  const headerTitle = t(config.agentsMd.labelKey, { defaultValue: config.agentsMd.fileName });

  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={headerTitle}
        icon={FileText}
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
              <span className="text-xs text-muted-foreground">
                {t(`${i18nNs}.agentsMd.scope.label`)}
              </span>
              <Select value={scope} onValueChange={handleScopeChange} disabled={loading || saving || runtimeLoading}>
                <SelectTrigger className="h-7 w-32 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {config.agentsMd.scopes.map((scopeOption) => (
                    <SelectItem key={scopeOption.value} value={scopeOption.value}>
                      <div className="flex items-center gap-2">
                        <scopeOption.icon className="h-3 w-3" />
                        {t(scopeOption.labelKey, { defaultValue: scopeOption.value })}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={handleRefresh}
              disabled={refreshDisabled}
            >
              <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
              {t(`${i18nNs}.agentsMd.actions.refresh`)}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-xs"
              onClick={handleSave}
              disabled={saveDisabled}
            >
              {saving ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5 mr-1.5" />
              )}
              {t(`${i18nNs}.agentsMd.actions.save`)}
            </Button>
          </div>
        }
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        {runtimeLoading ? (
          <LoadingSpinner
            size="md"
            className="flex-1"
            text={t(`${i18nNs}.agentsMd.status.runtimeLoading`, fileNameInterp)}
          />
        ) : !isRuntimeReady ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground">
            <p>{runtimeStatusMessage}</p>
          </div>
        ) : loading ? (
          <LoadingSpinner
            size="md"
            className="flex-1"
            text={t(`${i18nNs}.agentsMd.status.loading`, fileNameInterp)}
          />
        ) : (
          <div className="flex flex-1 flex-col overflow-hidden">
            <MarkdownEditor
              value={content}
              onChange={setContent}
              className="flex-1"
              statusMessage={showFallbackNotice ? t(`${i18nNs}.agentsMd.status.fallbackNotice`, fileNameInterp) : null}
              footerExtras={
                <span>
                  {t(`${i18nNs}.agentsMd.footer.scope`, {
                    scope: t(config.agentsMd.scopes.find(s => s.value === scope)?.labelKey ?? '', { defaultValue: scope }),
                  })}
                </span>
              }
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentsMdPage;
