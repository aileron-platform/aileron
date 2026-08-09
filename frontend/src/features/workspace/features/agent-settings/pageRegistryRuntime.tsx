import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { AgentScope, AgentSelectedFile } from './model/documents';
import type {
  AgentToolCapabilities,
  AgentToolConfig,
  AgentSettingsToolId,
} from './model/capabilities';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import MemoryDialog from './capabilities/memory/MemoryDialog';
import { createAgentsMdSource } from './capabilities/agents-md/agentsMdSource';
import { createCodexAgentsMdSource } from './capabilities/agents-md/codexAgentsMdSource';
import { createSlashCommandSource } from './capabilities/slash-commands/slashCommandSource';
import { createCodexDocumentSource } from './capabilities/slash-commands/codexDocumentSource';
import { createOutputStyleSource } from './capabilities/output-styles/outputStyleSource';
import { createMemorySource } from './capabilities/memory/memorySource';
import { createSubagentSource } from './capabilities/subagents/subagentSource';
import { createCodexSubagentSource } from './capabilities/subagents/codexSubagentSource';
import { createCodexRulesSource } from './capabilities/rules/codexRulesSource';
import { RulesDocumentDialog } from './capabilities/rules/RulesDocumentDialog';
import { createCodexSettingsSource } from './capabilities/codex-settings/codexSettingsSource';
import { createClaudeSettingsSource } from './capabilities/claude-settings/claudeSettingsSource';
import { createClaudeHookSource } from './capabilities/hooks/claudeHookSource';
import { createCodexHookSource } from './capabilities/hooks/codexHookSource';
import { createAgentSettingsApi } from './api/agentSettingsApi';
import { agentSettingsQueryKeys } from './api/agentSettingsQueryKeys';
import { createDocumentMetadataAdapter } from '@/shared/components/document-resource';
import {
  buildPluginResourceQueryKey,
  getCodexPluginControlErrorKey,
  invalidateProviderResourceQueries,
  resolvePluginResourceFilter,
} from './model/pluginResources';
import { PluginResourceMetadata } from './capabilities/plugin-resources/PluginResourceMetadata';
import { useProviderPluginListQuery } from './capabilities/plugin-resources/useProviderPluginListQuery';
import type { DocumentResourceWorkbenchProps } from '@/shared/components/document-resource';
import { useAgentSettingsAuthorization } from './AgentSettingsAuthorizationContext';

const MCPSettingsPage = React.lazy(() => import('./capabilities/mcp/MCPSettingsPage'));
const HooksPage = React.lazy(() => import('./capabilities/hooks/HooksPage'));
const SkillsPage = React.lazy(() => import('./capabilities/skills/SkillsPage'));
const CodexPluginsPage = React.lazy(() => import('./capabilities/plugins/CodexPluginsPage'));
const ClaudePluginsPage = React.lazy(() => import('./capabilities/plugins/ClaudePluginsPage'));
const SingleDocumentWorkflow = React.lazy(() => import('./components/workflows/SingleDocumentWorkflow'));
const BaseDocumentResourceWorkbench = React.lazy(() =>
  import('@/shared/components/document-resource').then(({ DocumentResourceWorkbench }) => ({
    default: DocumentResourceWorkbench,
  })),
);
const RawSettingsWorkflow = React.lazy(() => import('./components/workflows/RawSettingsWorkflow'));

export type SubViewId = string;

export interface PageRenderContext {
  toolId: AgentSettingsToolId;
  config: AgentToolConfig;
  subView: string;
  loadingFallback: React.ReactNode;
  selectedSkillFile: AgentSelectedFile | null;
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
  onDocumentDirtyChange?: (dirty: boolean) => void;
  documentSelectionBlocked?: boolean;
}

export interface PageEntry {
  render: (context: PageRenderContext) => React.ReactNode;
  requiresCapability?: keyof AgentToolCapabilities;
  isSupported?: (config: AgentToolConfig) => boolean;
}

const renderWithSuspense = (
  fallback: React.ReactNode,
  page: React.ReactNode,
): React.ReactNode => <React.Suspense fallback={fallback}>{page}</React.Suspense>;

const DocumentResourceWorkbench: React.FC<DocumentResourceWorkbenchProps> = (props) => {
  const { readOnly } = useAgentSettingsAuthorization();
  return <BaseDocumentResourceWorkbench {...props} readOnly={readOnly} />;
};

const documentContentFormat = (format: string | undefined): 'markdown' | 'toml' =>
  format === 'toml' ? 'toml' : 'markdown';

const agentsMdScopes = (config: AgentToolConfig): AgentScope[] =>
  config.agentsMd.scopes.map((scope) => scope.value as AgentScope);

const i18nPrimitive = (value: unknown): string | number =>
  typeof value === 'number' || typeof value === 'string' ? value : '';

const useRuntimeBackedPageGate = () => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl ?? '';
  const workspaceId = workspaceRuntime.workspaceId ?? '';
  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !workspaceRuntime.error);
  return {
    workspaceRuntime,
    runtimeBaseUrl,
    workspaceId,
    isRuntimeReady,
    disabledMessage: !isRuntimeReady ? t('workspace.agentSettings.common.mcp.messages.runtimeNotReady') : null,
  };
};

const AgentAgentsMdPage: React.FC<{ config: AgentToolConfig }> = ({ config }) => {
  const { workspaceRuntime } = useWorkspace();
  const agentsMdEndpoint = config.agentsMd.apiEndpoint ?? config.agentsMd.subViewId;
  const api = React.useMemo(
    () => createAgentSettingsApi(config.apiPathPrefix, agentsMdEndpoint),
    [agentsMdEndpoint, config.apiPathPrefix],
  );
  const source = React.useMemo(
    () => createAgentsMdSource(api, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId),
    [api, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId],
  );
  return (
    <SingleDocumentWorkflow
      queryKey={['agents-md', config.id]}
      source={source}
      scopes={agentsMdScopes(config)}
      scopeOptions={config.agentsMd.scopes}
      titleKey={config.agentsMd.labelKey}
      fileName={config.agentsMd.fileName}
      i18nNamespace={config.i18nNamespace}
      runtimeBaseUrl={workspaceRuntime.runtimeBaseUrl}
      workspaceId={workspaceRuntime.workspaceId}
      runtimeError={workspaceRuntime.error}
      runtimeLoading={workspaceRuntime.isLoading}
    />
  );
};

const ClaudeHooksPage: React.FC<{ config: AgentToolConfig }> = ({ config }) => {
  const { workspaceRuntime, runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const { t } = useI18n();
  const api = React.useMemo(() => createAgentSettingsApi(config.apiPathPrefix), [config.apiPathPrefix]);
  const source = React.useMemo(
    () => createClaudeHookSource(api, runtimeBaseUrl, workspaceId),
    [api, runtimeBaseUrl, workspaceId],
  );
  const eventOptions = React.useMemo(
    () => config.hookEvents?.map((event) => ({
      value: event.value,
      label: t(event.optionKey),
      description: t(event.labelKey),
    })),
    [config.hookEvents, t],
  );
  return (
    <HooksPage
      queryKey={['hooks', config.id, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]}
      source={source}
      provider="claude-code"
      availableScopes={config.availableScopes}
      eventOptions={eventOptions}
      i18nNamespace={config.i18nNamespace}
      isEnabled={isRuntimeReady}
      disabledMessage={disabledMessage}
    />
  );
};

const AgentSlashCommandsPage: React.FC<{
  config: AgentToolConfig;
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
  onDocumentDirtyChange?: (dirty: boolean) => void;
  documentSelectionBlocked?: boolean;
}> = ({ config, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) => {
  const { runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const api = React.useMemo(() => createAgentSettingsApi(config.apiPathPrefix), [config.apiPathPrefix]);
  const source = React.useMemo(
    () => createSlashCommandSource(api, runtimeBaseUrl, workspaceId),
    [api, runtimeBaseUrl, workspaceId],
  );
  return (
    <DocumentResourceWorkbench
      queryKey={agentSettingsQueryKeys.documentCollectionIdentity(
        runtimeBaseUrl,
        workspaceId,
        'slash-commands',
        config.apiPathPrefix,
      )}
      source={source}
      config={{
        metaKey: 'slash-commands',
        contentFormat: documentContentFormat(
          config.slashCommandFormat ?? config.capabilities.slashCommands?.format,
        ),
        createButtonLabel: `${config.i18nNamespace}.slashCommands.actions.create`,
        emptyStateTitle: `${config.i18nNamespace}.slashCommands.empty.title`,
        emptyStateDescription: `${config.i18nNamespace}.slashCommands.empty.description`,
        dialogTitle: `${config.i18nNamespace}.slashCommands.pageTitle`,
      }}
      i18nNamespace={config.i18nNamespace}
      availableScopes={config.capabilities.slashCommands?.scopes}
      selectedId={documentSelectedId}
      onSelect={onDocumentSelect}
      metadataAdapter={createDocumentMetadataAdapter('slashCommand')}
      templateResourceType="slashCommand"
      onDocumentDirtyChange={onDocumentDirtyChange}
      documentSelectionBlocked={documentSelectionBlocked}
      isEnabled={isRuntimeReady}
      disabledMessage={disabledMessage}
    />
  );
};

const ClaudeOutputStylesPage: React.FC<{
  config: AgentToolConfig;
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
  onDocumentDirtyChange?: (dirty: boolean) => void;
  documentSelectionBlocked?: boolean;
}> = ({ config, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) => {
  const { runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const [searchParams] = useSearchParams();
  const filter = React.useMemo(
    () => resolvePluginResourceFilter(searchParams),
    [searchParams],
  );
  const api = React.useMemo(() => createAgentSettingsApi(config.apiPathPrefix), [config.apiPathPrefix]);
  const source = React.useMemo(
    () => createOutputStyleSource(
      api,
      runtimeBaseUrl,
      workspaceId,
      filter.scope === 'plugin'
        ? { scope: 'plugin', pluginId: filter.pluginId }
        : undefined,
    ),
    [api, filter.pluginId, filter.scope, runtimeBaseUrl, workspaceId],
  );
  const queryKey = React.useMemo(
    () => agentSettingsQueryKeys.documentCollectionIdentity(
      runtimeBaseUrl,
      workspaceId,
      'output-styles',
      'claude-code',
      ...(filter.scope === 'plugin'
        ? ['plugin', filter.pluginId ?? 'all']
        : []),
    ),
    [
      filter.pluginId,
      filter.scope,
      runtimeBaseUrl,
      workspaceId,
    ],
  );
  return (
    <DocumentResourceWorkbench
      queryKey={queryKey}
      source={source}
      config={{
        metaKey: 'output-styles',
        contentFormat: 'markdown',
        hideCreate: filter.scope === 'plugin',
        createButtonLabel: 'workspace.claudeCode.outputStyles.actions.create',
        emptyStateTitle: 'workspace.claudeCode.outputStyles.empty.title',
        emptyStateDescription: 'workspace.claudeCode.outputStyles.empty.description',
        dialogTitle: 'workspace.claudeCode.outputStyles.pageTitle',
      }}
      i18nNamespace="workspace.claudeCode"
      availableScopes={config.capabilities.outputStyles?.scopes}
      selectedId={documentSelectedId}
      onSelect={onDocumentSelect}
      metadataAdapter={createDocumentMetadataAdapter('outputStyle')}
      templateResourceType="outputStyle"
      onDocumentDirtyChange={onDocumentDirtyChange}
      documentSelectionBlocked={documentSelectionBlocked}
      isEnabled={isRuntimeReady}
      disabledMessage={disabledMessage}
      renderDocumentMeta={document => (
        <PluginResourceMetadata
          provider="claude-code"
          resource="output-styles"
          workspaceId={workspaceId}
          pluginId={
            typeof document.metadata?.pluginId === 'string'
              ? document.metadata.pluginId
              : null
          }
          pluginName={document.pluginName}
          marketplaceId={document.marketplaceName}
          enabled={
            typeof document.metadata?.enabled === 'boolean'
              ? document.metadata.enabled
              : undefined
          }
          readOnly={
            typeof document.metadata?.readOnly === 'boolean'
              ? document.metadata.readOnly
              : document.scope === 'plugin'
          }
          relativeSourcePath={
            typeof document.metadata?.relativeSourcePath === 'string'
              ? document.metadata.relativeSourcePath
              : null
          }
          compact
        />
      )}
    />
  );
};

const ClaudeMemoryPage: React.FC<{
  config: AgentToolConfig;
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
}> = ({ config, documentSelectedId, onDocumentSelect }) => {
  const { runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const api = React.useMemo(() => createAgentSettingsApi(config.apiPathPrefix), [config.apiPathPrefix]);
  const source = React.useMemo(
    () => createMemorySource(api, runtimeBaseUrl, workspaceId),
    [api, runtimeBaseUrl, workspaceId],
  );
  return (
    <DocumentResourceWorkbench
      queryKey={agentSettingsQueryKeys.documentCollectionIdentity(
        runtimeBaseUrl,
        workspaceId,
        'memory',
        config.apiPathPrefix,
      )}
      source={source}
      dialog={MemoryDialog}
      config={{
        metaKey: 'memory',
        contentFormat: 'markdown',
        hideCreate: true,
        emptyStateTitle: 'workspace.claudeCode.memory.empty.title',
        emptyStateDescription: 'workspace.claudeCode.memory.empty.description',
        dialogTitle: 'workspace.claudeCode.memory.pageTitle',
        scopeMode: 'hidden',
      }}
      i18nNamespace="workspace.claudeCode"
      selectedId={documentSelectedId}
      onSelect={onDocumentSelect}
      isEnabled={isRuntimeReady}
      disabledMessage={disabledMessage}
    />
  );
};

const AgentSubagentsPage: React.FC<{
  config: AgentToolConfig;
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
  onDocumentDirtyChange?: (dirty: boolean) => void;
  documentSelectionBlocked?: boolean;
}> = ({ config, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) => {
  const { runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const api = React.useMemo(() => createAgentSettingsApi(config.apiPathPrefix), [config.apiPathPrefix]);
  const source = React.useMemo(
    () => createSubagentSource(api, runtimeBaseUrl, workspaceId),
    [api, runtimeBaseUrl, workspaceId],
  );
  return (
    <DocumentResourceWorkbench
      queryKey={agentSettingsQueryKeys.documentCollectionIdentity(
        runtimeBaseUrl,
        workspaceId,
        'subagents',
        config.apiPathPrefix,
      )}
      source={source}
      availableScopes={config.capabilities.agentDefinitions?.scopes}
      config={{
        metaKey: 'subagents',
        contentFormat: documentContentFormat(config.capabilities.agentDefinitions?.format),
        createButtonLabel: `${config.i18nNamespace}.subagents.actions.create`,
        emptyStateTitle: `${config.i18nNamespace}.subagents.empty.title`,
        emptyStateDescription: `${config.i18nNamespace}.subagents.empty.description`,
        dialogTitle: `${config.i18nNamespace}.subagents.pageTitle`,
      }}
      i18nNamespace={config.i18nNamespace}
      selectedId={documentSelectedId}
      onSelect={onDocumentSelect}
      metadataAdapter={createDocumentMetadataAdapter('subagent')}
      templateResourceType="subagent"
      onDocumentDirtyChange={onDocumentDirtyChange}
      documentSelectionBlocked={documentSelectionBlocked}
      isEnabled={isRuntimeReady}
      disabledMessage={disabledMessage}
    />
  );
};

const ClaudeSettingsPage: React.FC = () => {
  const { workspaceRuntime } = useWorkspace();
  const source = React.useMemo(
    () => createClaudeSettingsSource(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId),
    [workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId],
  );
  return (
    <RawSettingsWorkflow
      queryKey={['raw-settings', 'claude']}
      source={source}
      titleKey="workspace.claudeCode.settings.header.title"
      scopeLabelKey="workspace.claudeCode.permissions.scope.label"
      dirtyLabelKey="workspace.claudeCode.settings.dirty"
      refreshLabelKey="workspace.claudeCode.permissions.actions.refresh"
      saveLabelKey="workspace.claudeCode.permissions.actions.save"
      savingLabelKey="workspace.claudeCode.permissions.actions.saving"
      saveSuccessKey="workspace.claudeCode.settings.saveSuccess"
      saveFailedKey="workspace.claudeCode.settings.saveFailed"
      loadFailedKey="workspace.claudeCode.permissions.status.loadFailed"
      unsavedChangesConfirmKey="workspace.claudeCode.settings.unsavedChangesConfirm"
      runtimeUnavailableKey="workspace.claudeCode.permissions.status.runtimeUnavailable"
      runtimeLoadingKey="workspace.claudeCode.permissions.status.runtimeLoading"
      runtimeMissingKey="workspace.claudeCode.permissions.status.runtimeMissing"
    />
  );
};

const CodexAgentsMdPage: React.FC<{ config: AgentToolConfig }> = ({ config }) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const api = React.useMemo(() => createAgentSettingsApi('codex'), []);
  const source = React.useMemo(
    () => createCodexAgentsMdSource(api, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId),
    [api, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId],
  );
  return (
    <SingleDocumentWorkflow
      queryKey={['agents-md', 'codex']}
      source={source}
      scopes={agentsMdScopes(config)}
      scopeOptions={config.agentsMd.scopes}
      titleKey={config.agentsMd.labelKey}
      fileName={config.agentsMd.fileName}
      i18nNamespace="workspace.agentSettings.codex"
      runtimeBaseUrl={workspaceRuntime.runtimeBaseUrl}
      workspaceId={workspaceRuntime.workspaceId}
      runtimeError={workspaceRuntime.error}
      runtimeLoading={workspaceRuntime.isLoading}
      labelKeys={{
        refresh: 'workspace.agentSettings.codex.common.actions.refresh',
        save: 'workspace.agentSettings.codex.common.actions.save',
        runtimeLoading: 'workspace.agentSettings.common.loading',
        loading: 'workspace.agentSettings.common.loading',
        runtimeMissing: 'workspace.agentSettings.common.agentsMd.status.runtimeMissing',
        runtimeUnavailable: 'workspace.agentSettings.common.agentsMd.status.runtimeUnavailable',
        scope: 'workspace.agentSettings.codex.common.layer',
        confirmDiscard: 'workspace.agentSettings.codex.agentsMd.confirmDiscard',
        saveSuccessTitle: 'workspace.agentSettings.codex.agentsMd.notifications.saveSuccess',
        saveFailedTitle: 'workspace.agentSettings.codex.agentsMd.notifications.saveFailed',
      }}
      renderHeader={() => {
        const caveats = source.getCaveats();
        if (caveats.length === 0) {
          return null;
        }
        return (
          <div className="space-y-2 px-4 pt-4">
            {caveats.map((caveat) => (
              <Alert key={`${caveat.type}:${caveat.path ?? ''}`}>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>{t(`workspace.agentSettings.codex.agentsMd.caveatTitles.${caveat.type}`)}</AlertTitle>
                <AlertDescription>
                  {t(caveat.messageKey, {
                    path: caveat.path ?? '',
                    sizeBytes: i18nPrimitive(caveat.metadata?.sizeBytes),
                    maxBytes: i18nPrimitive(caveat.metadata?.maxBytes),
                  })}
                </AlertDescription>
              </Alert>
            ))}
          </div>
        );
      }}
      renderFooter={(_scope, document) => document ? (
        <span>
          {t('workspace.agentSettings.codex.agentsMd.footer', {
            path: i18nPrimitive(document.metadata?.path),
            sizeBytes: i18nPrimitive(document.metadata?.sizeBytes),
            maxBytes: i18nPrimitive(document.metadata?.maxBytes),
          })}
        </span>
      ) : null}
    />
  );
};

const CodexHooksPage: React.FC<{ config: AgentToolConfig }> = ({ config }) => {
  const { runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const api = React.useMemo(() => createAgentSettingsApi('codex'), []);
  const source = React.useMemo(
    () => createCodexHookSource(api, runtimeBaseUrl, workspaceId),
    [api, runtimeBaseUrl, workspaceId],
  );
  const pluginListQuery = useProviderPluginListQuery({
    provider: 'codex',
    runtimeBaseUrl,
    workspaceId,
    enabled: isRuntimeReady,
  });
  const providerResourceGeneration =
    pluginListQuery.data?.providerResourceGeneration ?? 0;
  const queryKey = React.useMemo(
    () => buildPluginResourceQueryKey({
      provider: 'codex',
      resource: 'hooks',
      runtimeBaseUrl,
      workspaceId,
      providerResourceGeneration,
      scope: null,
      pluginId: null,
    }),
    [
      providerResourceGeneration,
      runtimeBaseUrl,
      workspaceId,
    ],
  );
  const invalidateProviderRoot = React.useCallback(
    () => invalidateProviderResourceQueries(
      queryClient,
      'codex',
      workspaceId,
    ),
    [queryClient, workspaceId],
  );
  const pluginListError = pluginListQuery.error
    ? t(getCodexPluginControlErrorKey('hook-trust', pluginListQuery.error))
    : null;
  return (
    <HooksPage
      queryKey={queryKey}
      source={source}
      provider="codex"
      availableScopes={['project', 'user', 'plugin']}
      i18nNamespace={config.i18nNamespace}
      isEnabled={isRuntimeReady && pluginListQuery.isSuccess}
      disabledMessage={disabledMessage ?? pluginListError}
      onProviderResourceMutation={invalidateProviderRoot}
    />
  );
};

const CodexPromptsPage: React.FC<{
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
}> = ({ documentSelectedId, onDocumentSelect }) => {
  const { runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const api = React.useMemo(() => createAgentSettingsApi('codex'), []);
  const source = React.useMemo(
    () => createCodexDocumentSource(api, runtimeBaseUrl, workspaceId, 'prompts'),
    [api, runtimeBaseUrl, workspaceId],
  );
  return (
    <DocumentResourceWorkbench
      queryKey={[runtimeBaseUrl, workspaceId, 'prompts', 'codex']}
      source={source}
      config={{
        metaKey: 'prompts',
        contentFormat: 'markdown',
        createButtonLabel: 'workspace.agentSettings.codex.prompts.actions.create',
        emptyStateTitle: 'workspace.agentSettings.codex.prompts.empty.title',
        emptyStateDescription: 'workspace.agentSettings.codex.prompts.empty.description',
        dialogTitle: 'workspace.agentSettings.codex.prompts.pageTitle',
      }}
      i18nNamespace="workspace.agentSettings.codex"
      selectedId={documentSelectedId}
      onSelect={onDocumentSelect}
      metadataAdapter={createDocumentMetadataAdapter('slashCommand')}
      templateResourceType="slashCommand"
      isEnabled={isRuntimeReady}
      disabledMessage={disabledMessage}
    />
  );
};

const CodexSubagentsPage: React.FC<{
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
  onDocumentDirtyChange?: (dirty: boolean) => void;
  documentSelectionBlocked?: boolean;
}> = ({ documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) => {
  const { t } = useI18n();
  const { runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const api = React.useMemo(() => createAgentSettingsApi('codex'), []);
  const source = React.useMemo(
    () => createCodexSubagentSource(api, runtimeBaseUrl, workspaceId),
    [api, runtimeBaseUrl, workspaceId],
  );
  return (
    <DocumentResourceWorkbench
      queryKey={[runtimeBaseUrl, workspaceId, 'subagents', 'codex']}
      source={source}
      config={{
        metaKey: 'subagents',
        contentFormat: 'toml',
        createButtonLabel: 'workspace.agentSettings.codex.subagents.actions.create',
        emptyStateTitle: 'workspace.agentSettings.codex.subagents.empty.title',
        emptyStateDescription: 'workspace.agentSettings.codex.subagents.empty.description',
        dialogTitle: 'workspace.agentSettings.codex.subagents.pageTitle',
      }}
      i18nNamespace="workspace.agentSettings.codex"
      renderHeader={() => {
        const registry = source.getRegistry();
        if (registry.length === 0) {
          return null;
        }
        return (
          <div className="border-b border-border bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
            {registry.map((entry) => (
              <span key={`${entry.scope}:${entry.path}`} className="mr-4">
                {t('workspace.agentSettings.codex.subagents.registry.summary', {
                  layer: t(`workspace.agentSettings.codex.documents.scope.values.${entry.scope}`),
                  maxThreads: entry.settings.max_threads ?? '-',
                  maxDepth: entry.settings.max_depth ?? '-',
                  jobMaxRuntime: entry.settings.job_max_runtime_seconds ?? '-',
                })}
              </span>
            ))}
          </div>
        );
      }}
      selectedId={documentSelectedId}
      onSelect={onDocumentSelect}
      metadataAdapter={createDocumentMetadataAdapter('subagent')}
      templateResourceType="subagent"
      onDocumentDirtyChange={onDocumentDirtyChange}
      documentSelectionBlocked={documentSelectionBlocked}
      isEnabled={isRuntimeReady}
      disabledMessage={disabledMessage}
    />
  );
};

const CodexRulesPage: React.FC<{
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
}> = ({ documentSelectedId, onDocumentSelect }) => {
  const { runtimeBaseUrl, workspaceId, isRuntimeReady, disabledMessage } = useRuntimeBackedPageGate();
  const api = React.useMemo(() => createAgentSettingsApi('codex'), []);
  const source = React.useMemo(
    () => createCodexRulesSource(api, runtimeBaseUrl, workspaceId),
    [api, runtimeBaseUrl, workspaceId],
  );
  return (
    <DocumentResourceWorkbench
      queryKey={[runtimeBaseUrl, workspaceId, 'rules', 'codex']}
      source={source}
      dialog={RulesDocumentDialog}
      config={{
        metaKey: 'rules',
        contentFormat: 'plain',
        createButtonLabel: 'workspace.agentSettings.codex.rules.actions.create',
        emptyStateTitle: 'workspace.agentSettings.codex.rules.empty.title',
        emptyStateDescription: 'workspace.agentSettings.codex.rules.empty.description',
        dialogTitle: 'workspace.agentSettings.codex.rules.pageTitle',
      }}
      i18nNamespace="workspace.agentSettings.codex"
      selectedId={documentSelectedId}
      onSelect={onDocumentSelect}
      isEnabled={isRuntimeReady}
      disabledMessage={disabledMessage}
    />
  );
};

const CodexSettingsPage: React.FC = () => {
  const { workspaceRuntime } = useWorkspace();
  const source = React.useMemo(
    () => createCodexSettingsSource(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId),
    [workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId],
  );
  return (
    <RawSettingsWorkflow
      queryKey={['raw-settings', 'codex']}
      source={source}
      titleKey="workspace.agentSettings.codex.settings.header.title"
      scopeLabelKey="workspace.agentSettings.codex.settings.layers.label"
      dirtyLabelKey="workspace.agentSettings.codex.settings.dirty"
      refreshLabelKey="workspace.agentSettings.codex.settings.actions.refresh"
      saveLabelKey="workspace.agentSettings.codex.settings.actions.save"
      savingLabelKey="workspace.agentSettings.codex.settings.actions.saving"
      saveSuccessKey="workspace.agentSettings.codex.settings.notifications.saveSuccess"
      saveFailedKey="workspace.agentSettings.codex.settings.notifications.saveFailed"
      loadFailedKey="workspace.agentSettings.codex.settings.notifications.loadFailed"
      unsavedChangesConfirmKey="workspace.agentSettings.codex.settings.unsavedChangesConfirm"
    />
  );
};

export const PAGE_REGISTRY: Record<AgentSettingsToolId, Partial<Record<SubViewId, PageEntry>>> = {
  claude: {
    'claude-md': {
      render: ({ loadingFallback, config }) => renderWithSuspense(loadingFallback, <AgentAgentsMdPage config={config} />),
    },
    mcp: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <MCPSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            supportsToggle={config.supportsToggle}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'mcp',
    },
    hooks: {
      render: ({ loadingFallback, config }) => renderWithSuspense(loadingFallback, <ClaudeHooksPage config={config} />),
      requiresCapability: 'hooks',
    },
    'slash-commands': {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) =>
        renderWithSuspense(
          loadingFallback,
          <AgentSlashCommandsPage
            config={config}
            documentSelectedId={documentSelectedId}
            onDocumentSelect={onDocumentSelect}
            onDocumentDirtyChange={onDocumentDirtyChange}
            documentSelectionBlocked={documentSelectionBlocked}
          />,
        ),
      requiresCapability: 'slashCommands',
    },
    'output-styles': {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) =>
        renderWithSuspense(
          loadingFallback,
          <ClaudeOutputStylesPage
            config={config}
            documentSelectedId={documentSelectedId}
            onDocumentSelect={onDocumentSelect}
            onDocumentDirtyChange={onDocumentDirtyChange}
            documentSelectionBlocked={documentSelectionBlocked}
          />,
        ),
      requiresCapability: 'outputStyles',
    },
    memory: {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <ClaudeMemoryPage config={config} documentSelectedId={documentSelectedId} onDocumentSelect={onDocumentSelect} />,
        ),
    },
    skills: {
      render: ({ loadingFallback, config, selectedSkillFile }) =>
        renderWithSuspense(
          loadingFallback,
          <SkillsPage
            selectedFile={selectedSkillFile}
            apiPrefix={config.apiPathPrefix}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'skills',
    },
    subagents: {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) =>
        renderWithSuspense(
          loadingFallback,
          <AgentSubagentsPage
            config={config}
            documentSelectedId={documentSelectedId}
            onDocumentSelect={onDocumentSelect}
            onDocumentDirtyChange={onDocumentDirtyChange}
            documentSelectionBlocked={documentSelectionBlocked}
          />,
        ),
      requiresCapability: 'agentDefinitions',
    },
    plugins: {
      render: ({ loadingFallback }) => renderWithSuspense(loadingFallback, <ClaudePluginsPage />),
      requiresCapability: 'plugins',
    },
    settings: {
      render: ({ loadingFallback }) => renderWithSuspense(loadingFallback, <ClaudeSettingsPage />),
    },
  },
  opencode: {
    'agents-md': {
      render: ({ loadingFallback, config }) => renderWithSuspense(loadingFallback, <AgentAgentsMdPage config={config} />),
    },
    mcp: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <MCPSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            supportsToggle={config.supportsToggle}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'mcp',
    },
    'slash-commands': {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) =>
        renderWithSuspense(
          loadingFallback,
          <AgentSlashCommandsPage
            config={config}
            documentSelectedId={documentSelectedId}
            onDocumentSelect={onDocumentSelect}
            onDocumentDirtyChange={onDocumentDirtyChange}
            documentSelectionBlocked={documentSelectionBlocked}
          />,
        ),
      requiresCapability: 'slashCommands',
    },
    skills: {
      render: ({ loadingFallback, config, selectedSkillFile }) =>
        renderWithSuspense(
          loadingFallback,
          <SkillsPage
            selectedFile={selectedSkillFile}
            apiPrefix={config.apiPathPrefix}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'skills',
    },
    subagents: {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) =>
        renderWithSuspense(
          loadingFallback,
          <AgentSubagentsPage
            config={config}
            documentSelectedId={documentSelectedId}
            onDocumentSelect={onDocumentSelect}
            onDocumentDirtyChange={onDocumentDirtyChange}
            documentSelectionBlocked={documentSelectionBlocked}
          />,
        ),
      requiresCapability: 'agentDefinitions',
    },
  },
  codex: {
    'agents-md': {
      render: ({ loadingFallback, config }) => renderWithSuspense(loadingFallback, <CodexAgentsMdPage config={config} />),
    },
    mcp: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <MCPSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            supportsToggle={config.supportsToggle}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'mcp',
    },
    hooks: {
      render: ({ loadingFallback, config }) => renderWithSuspense(loadingFallback, <CodexHooksPage config={config} />),
      requiresCapability: 'hooks',
    },
    skills: {
      render: ({ loadingFallback, config, selectedSkillFile }) =>
        renderWithSuspense(
          loadingFallback,
          <SkillsPage
            selectedFile={selectedSkillFile}
            apiPrefix={config.apiPathPrefix}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'skills',
    },
    prompts: {
      render: ({ loadingFallback, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <CodexPromptsPage documentSelectedId={documentSelectedId} onDocumentSelect={onDocumentSelect} />,
        ),
      isSupported: (config) => config.id === 'codex',
    },
    subagents: {
      render: ({ loadingFallback, documentSelectedId, onDocumentSelect, onDocumentDirtyChange, documentSelectionBlocked }) =>
        renderWithSuspense(
          loadingFallback,
          <CodexSubagentsPage
            documentSelectedId={documentSelectedId}
            onDocumentSelect={onDocumentSelect}
            onDocumentDirtyChange={onDocumentDirtyChange}
            documentSelectionBlocked={documentSelectionBlocked}
          />,
        ),
      isSupported: (config) => config.id === 'codex',
    },
    rules: {
      render: ({ loadingFallback, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <CodexRulesPage documentSelectedId={documentSelectedId} onDocumentSelect={onDocumentSelect} />,
        ),
      isSupported: (config) => config.id === 'codex',
    },
    plugins: {
      render: ({ loadingFallback }) => renderWithSuspense(loadingFallback, <CodexPluginsPage />),
      isSupported: (config) => config.id === 'codex',
    },
    settings: {
      render: ({ loadingFallback }) => renderWithSuspense(loadingFallback, <CodexSettingsPage />),
      isSupported: (config) => config.id === 'codex',
    },
  },
};
