import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useToast } from '@/shared/components/ui/use-toast';
import { MarkdownDocumentShell } from '@/shared/components/document-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { ApiError } from '@/shared/api/apiClient';
import type { SingleDocumentLoadResult, SingleDocumentSource } from '../../model/singleDocumentSource';
import type { AgentScope } from '../../model/documents';
import type { AgentToolScopeOption } from '../../model/capabilities';
import { sortAgentSettingsSourceOptions } from '../AgentSettingsSourceControls';
import { useAgentSettingsAuthorization } from '../../AgentSettingsAuthorizationContext';

export interface SingleDocumentWorkflowLabelKeys {
  refresh?: string;
  save?: string;
  runtimeLoading?: string;
  loading?: string;
  runtimeMissing?: string;
  runtimeUnavailable?: string;
  scope?: string;
  confirmDiscard?: string;
  fallbackNotice?: string;
  loadFailedTitle?: string;
  loadFailedDescription?: string;
  runtimeUnavailableToastTitle?: string;
  runtimeUnavailableToastDescription?: string;
  saveSuccessTitle?: string;
  saveSuccessDescription?: string;
  saveFailedTitle?: string;
  saveFailedDescription?: string;
}

export interface SingleDocumentWorkflowProps {
  queryKey: ReadonlyArray<string>;
  source: SingleDocumentSource;
  scopes: AgentScope[];
  titleKey: string;
  fileName: string;
  i18nNamespace: string;
  scopeOptions?: AgentToolScopeOption[];
  labelKeys?: SingleDocumentWorkflowLabelKeys;
  runtimeLoading?: boolean;
  runtimeBaseUrl?: string | null;
  workspaceId?: string | null;
  runtimeError?: string | null;
  renderHeader?: (scope: AgentScope, document: SingleDocumentLoadResult | null) => React.ReactNode;
  renderFooter?: (scope: AgentScope, document: SingleDocumentLoadResult | null) => React.ReactNode;
  readOnly?: boolean;
}

const is404Error = (err: unknown): boolean => {
  if (err instanceof ApiError) {
    return err.status === 404;
  }
  if (err instanceof Error) {
    return err.message.includes('404');
  }
  return false;
};

const SingleDocumentWorkflow: React.FC<SingleDocumentWorkflowProps> = ({
  queryKey,
  source,
  scopes,
  titleKey,
  fileName,
  i18nNamespace,
  scopeOptions = [],
  labelKeys = {},
  runtimeLoading = false,
  runtimeBaseUrl = 'ready',
  workspaceId = 'ready',
  runtimeError = null,
  renderHeader,
  renderFooter,
  readOnly: readOnlyProp,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { readOnly: contextReadOnly } = useAgentSettingsAuthorization();
  const readOnly = readOnlyProp ?? contextReadOnly;
  const defaultScope = scopes[0] ?? 'project';
  const [scope, setScope] = useState<AgentScope>(defaultScope);
  const [content, setContent] = useState('');
  const [initialContent, setInitialContent] = useState('');
  const [showFallbackNotice, setShowFallbackNotice] = useState(false);
  const fileNameInterp = useMemo(() => ({ fileName }), [fileName]);
  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !runtimeError);
  const hasChanges = content !== initialContent;
  const activeScopeOptions = useMemo(() => (
    sortAgentSettingsSourceOptions(scopeOptions.filter((option) => scopes.includes(option.value as AgentScope)))
  ), [scopeOptions, scopes]);

  const keyOf = useCallback((key: keyof SingleDocumentWorkflowLabelKeys, fallback: string): string => (
    labelKeys[key] ?? fallback
  ), [labelKeys]);

  const runtimeStatusMessage = useMemo(() => {
    if (runtimeError) {
      return t(keyOf('runtimeUnavailable', `${i18nNamespace}.agentsMd.status.runtimeUnavailable`), {
        message: runtimeError,
        ...fileNameInterp,
      });
    }
    if (!runtimeBaseUrl || !workspaceId) {
      return t(keyOf('runtimeMissing', `${i18nNamespace}.agentsMd.status.runtimeMissing`), fileNameInterp);
    }
    return null;
  }, [fileNameInterp, i18nNamespace, keyOf, runtimeBaseUrl, runtimeError, t, workspaceId]);

  const documentQuery = useQuery({
    queryKey: ['single-document', ...queryKey, scope],
    enabled: isRuntimeReady,
    staleTime: 30_000,
    queryFn: async () => {
      setShowFallbackNotice(false);
      try {
        return await source.load(scope);
      } catch (err) {
        if (is404Error(err)) {
          return { content: '' };
        }
        setShowFallbackNotice(true);
        toast({
          variant: 'destructive',
          title: t(keyOf('loadFailedTitle', `${i18nNamespace}.agentsMd.notifications.loadFailed.title`), fileNameInterp),
          description: err instanceof Error
            ? err.message
            : t(keyOf('loadFailedDescription', `${i18nNamespace}.agentsMd.notifications.loadFailed.description`), fileNameInterp),
        });
        return { content: '' };
      }
    },
  });

  useEffect(() => {
    if (!documentQuery.data) return;
    const nextContent = documentQuery.data.content ?? '';
    setContent(nextContent);
    setInitialContent(nextContent);
  }, [documentQuery.data]);

  const confirmDiscard = useCallback(() => {
    if (!hasChanges) return true;
    return window.confirm(t(keyOf('confirmDiscard', `${i18nNamespace}.agentsMd.confirmDiscard`)));
  }, [hasChanges, i18nNamespace, keyOf, t]);

  const handleScopeChange = useCallback((value: string) => {
    if (readOnly || value === scope) return;
    if (!confirmDiscard()) return;
    setScope(value as AgentScope);
  }, [confirmDiscard, readOnly, scope]);

  const handleRefresh = useCallback(() => {
    if (!isRuntimeReady) {
      toast({
        variant: 'destructive',
        title: t(keyOf('runtimeUnavailableToastTitle', `${i18nNamespace}.agentsMd.notifications.runtimeUnavailable.title`)),
        description: t(keyOf('runtimeUnavailableToastDescription', `${i18nNamespace}.agentsMd.notifications.runtimeUnavailable.description`)),
      });
      return;
    }
    if (!confirmDiscard()) return;
    void documentQuery.refetch();
  }, [confirmDiscard, documentQuery, i18nNamespace, isRuntimeReady, keyOf, t, toast]);

  const saveMutation = useMutation({
    mutationFn: () => {
      if (readOnly) {
        throw new Error(t('common.authorization.readOnlyDescription'));
      }
      return source.save(scope, content);
    },
    onSuccess: () => {
      setInitialContent(content);
      setShowFallbackNotice(false);
      void queryClient.invalidateQueries({ queryKey: ['single-document', ...queryKey, scope] });
      toast({
        title: t(keyOf('saveSuccessTitle', `${i18nNamespace}.agentsMd.notifications.saveSuccess.title`), fileNameInterp),
        description: labelKeys.saveSuccessDescription
          ? t(labelKeys.saveSuccessDescription, fileNameInterp)
          : undefined,
      });
    },
    onError: (err) => {
      toast({
        variant: 'destructive',
        title: t(keyOf('saveFailedTitle', `${i18nNamespace}.agentsMd.notifications.saveFailed.title`), fileNameInterp),
        description: err instanceof Error
          ? err.message
          : t(keyOf('saveFailedDescription', `${i18nNamespace}.agentsMd.notifications.saveFailed.description`), fileNameInterp),
      });
    },
  });

  const selectedScopeOption = activeScopeOptions.find((option) => option.value === scope);
  const footer = renderFooter
    ? renderFooter(scope, documentQuery.data ?? null)
    : (
      <span>
        {t(`${i18nNamespace}.agentsMd.footer.scope`, {
          scope: t(selectedScopeOption?.labelKey ?? '', { defaultValue: scope }),
        })}
      </span>
    );
  const isLoading = documentQuery.isLoading || (documentQuery.isFetching && !documentQuery.data);

  return (
    <div className="flex h-full flex-col">
      {renderHeader && documentQuery.isSuccess ? renderHeader(scope, documentQuery.data ?? null) : null}
      <MarkdownDocumentShell
        title={t(titleKey, { defaultValue: fileName })}
        refreshLabel={t(keyOf('refresh', `${i18nNamespace}.agentsMd.actions.refresh`))}
        saveLabel={t(keyOf('save', `${i18nNamespace}.agentsMd.actions.save`))}
        runtimeLoadingLabel={t(keyOf('runtimeLoading', `${i18nNamespace}.agentsMd.status.runtimeLoading`), fileNameInterp)}
        loadingLabel={t(keyOf('loading', `${i18nNamespace}.agentsMd.status.loading`), fileNameInterp)}
        runtimeStatusMessage={runtimeStatusMessage}
        runtimeLoading={runtimeLoading}
        isRuntimeReady={isRuntimeReady}
        isLoading={isLoading}
        isSaving={saveMutation.isPending}
        statusMessage={showFallbackNotice ? t(keyOf('fallbackNotice', `${i18nNamespace}.agentsMd.status.fallbackNotice`), fileNameInterp) : null}
        value={content}
        onChange={setContent}
        onRefresh={handleRefresh}
        onSave={() => {
          if (!readOnly) {
            saveMutation.mutate();
          }
        }}
        refreshDisabled={!isRuntimeReady || documentQuery.isFetching || saveMutation.isPending || runtimeLoading}
        saveDisabled={!isRuntimeReady || documentQuery.isFetching || saveMutation.isPending || !hasChanges || runtimeLoading}
        headerExtras={(
          <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
            <span className="text-xs text-muted-foreground">
              {t(keyOf('scope', `${i18nNamespace}.agentsMd.scope.label`))}
            </span>
            <Select
              value={scope}
              onValueChange={handleScopeChange}
              disabled={readOnly || documentQuery.isFetching || saveMutation.isPending || runtimeLoading}
            >
              <SelectTrigger className="h-7 w-32 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {activeScopeOptions.map((scopeOption) => (
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
        footerExtras={footer}
        readOnly={readOnly}
      />
    </div>
  );
};

export default SingleDocumentWorkflow;
