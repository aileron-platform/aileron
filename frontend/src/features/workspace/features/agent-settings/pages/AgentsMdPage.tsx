/**
 * AgentsMdPage - generic instruction file editor.
 *
 * Generalizes ClaudeMdPage through AgentToolConfig for scopes, titles,
 * API prefixes, and instruction file metadata.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useToast } from '@/shared/components/ui/use-toast';
import { ApiError } from '@/shared/api/apiClient';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { AgentToolConfig } from '../types';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';
import { MarkdownDocumentShell } from '@/shared/components/document-workflow';

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
  const api = useMemo(
    () => createAgentSettingsApi(config.apiPathPrefix, agentsMdEndpoint),
    [config.apiPathPrefix, agentsMdEndpoint],
  );

  const defaultScope = config.agentsMd.scopes[0]?.value ?? 'project';
  const [scope, setScope] = useState(defaultScope);
  const [content, setContent] = useState('');
  const [initialContent, setInitialContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [showFallbackNotice, setShowFallbackNotice] = useState(false);
  const [isStale, setIsStale] = useState(false);

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
    if (err instanceof ApiError) {
      return err.status === 404;
    }
    if (err instanceof Error) {
      return err.message.includes('404');
    }
    return false;
  }, []);

  const hasChanges = content !== initialContent;
  const headerTitle = t(config.agentsMd.labelKey, { defaultValue: config.agentsMd.fileName });

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
        setIsStale(false);
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
            description: err instanceof Error
              ? err.message
              : t(`${i18nNs}.agentsMd.notifications.loadFailed.description`, fileNameInterp),
          });
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    void loadDocument();
    return () => {
      isMounted = false;
    };
  }, [runtimeBaseUrl, workspaceId, runtimeError, scope, refreshToken, is404Error, toast, t, api, i18nNs]);

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: ['claudeMd'],
    onRefresh: () => {
      setRefreshToken((token) => token + 1);
    },
    shouldDeferRefresh: () => hasChanges,
    onDeferredRefresh: () => {
      setIsStale(true);
      toast({
        title: headerTitle,
        description: t(`${i18nNs}.agentsMd.notifications.templateUpdated.description`, fileNameInterp),
      });
    },
  });

  const handleScopeChange = useCallback((value: string) => {
    if (value === scope) return;
    if (!confirmDiscard()) return;
    setScope(value);
  }, [confirmDiscard, scope]);

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
      await api.updateAgentsMd(runtimeBaseUrl!, workspaceId!, { scope, content });
      setInitialContent(content);
      setShowFallbackNotice(false);
      setIsStale(false);
      toast({
        title: t(`${i18nNs}.agentsMd.notifications.saveSuccess.title`, fileNameInterp),
        description: t(`${i18nNs}.agentsMd.notifications.saveSuccess.description`, fileNameInterp),
      });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t(`${i18nNs}.agentsMd.notifications.saveFailed.title`, fileNameInterp),
        description: err instanceof Error
          ? err.message
          : t(`${i18nNs}.agentsMd.notifications.saveFailed.description`, fileNameInterp),
      });
    } finally {
      setSaving(false);
    }
  }, [content, isRuntimeReady, scope, runtimeBaseUrl, t, toast, workspaceId, api, i18nNs]);

  return (
    <MarkdownDocumentShell
      title={headerTitle}
      refreshLabel={t(`${i18nNs}.agentsMd.actions.refresh`)}
      saveLabel={t(`${i18nNs}.agentsMd.actions.save`)}
      runtimeLoadingLabel={t(`${i18nNs}.agentsMd.status.runtimeLoading`, fileNameInterp)}
      loadingLabel={t(`${i18nNs}.agentsMd.status.loading`, fileNameInterp)}
      runtimeStatusMessage={runtimeStatusMessage}
      runtimeLoading={runtimeLoading}
      isRuntimeReady={isRuntimeReady}
      isLoading={loading}
      isSaving={saving}
      isStale={isStale}
      statusMessage={showFallbackNotice ? t(`${i18nNs}.agentsMd.status.fallbackNotice`, fileNameInterp) : null}
      staleMessage={t(`${i18nNs}.agentsMd.status.staleTemplate`, fileNameInterp)}
      value={content}
      onChange={setContent}
      onRefresh={handleRefresh}
      onSave={handleSave}
      refreshDisabled={!isRuntimeReady || loading || saving || runtimeLoading}
      saveDisabled={!isRuntimeReady || loading || saving || !hasChanges}
      headerExtras={(
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
      )}
      footerExtras={(
        <span>
          {t(`${i18nNs}.agentsMd.footer.scope`, {
            scope: t(config.agentsMd.scopes.find((item) => item.value === scope)?.labelKey ?? '', {
              defaultValue: scope,
            }),
          })}
        </span>
      )}
    />
  );
};

export default AgentsMdPage;
