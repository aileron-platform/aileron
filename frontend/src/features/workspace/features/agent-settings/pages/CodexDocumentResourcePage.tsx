import React, { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { DocumentWorkflowDialogProps } from '@/shared/components/document-workflow';
import { formatDocumentContentSize } from '@/shared/components/document-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { AgentDocumentPage } from '../components/DocumentPage';
import { CodexSubagentDialog } from '../components/dialogs/CodexSubagentDialog';
import { AgentCommandDialog } from '../components/dialogs/AgentCommandDialog';
import { AgentDefinitionDialog } from '../components/dialogs/AgentDefinitionDialog';
import {
  createAgentSettingsApi,
  type CodexFileSummary,
  type CodexSubagentDefinition,
  type CodexSubagentItem,
  type CodexSubagentsResponse,
} from '../services/agentSettingsApi';
import type { AgentDocument, AgentScope } from '../types';

const logger = createLogger('CodexDocumentResourcePage');

type CodexDocumentResource = 'subagents' | 'prompts';
type CodexEditableLayer = 'project' | 'user';

const EDITABLE_LAYERS: CodexEditableLayer[] = ['project', 'user'];
const CODEX_DOCUMENT_SCOPES: AgentScope[] = ['project', 'user'];

const resourceDefaults: Record<CodexDocumentResource, { fileName: string; metaKey: 'subagents' | 'prompts'; format: 'markdown' | 'toml' }> = {
  subagents: { fileName: 'worker.toml', metaKey: 'subagents', format: 'toml' },
  prompts: { fileName: 'prompt.md', metaKey: 'prompts', format: 'markdown' },
};

const fileNameFromPath = (path: string) => path.split('/').filter(Boolean).pop() || path;

const buildDocumentId = (source: string, path: string) => `${source}:${path}`;

const buildDocumentPath = (document: AgentDocument, fallback: string) => {
  const fileName = (document.metadata?.fileName as string | undefined) || document.title || fallback;
  const namespace = (document.metadata?.namespace as string | undefined)?.trim();
  if (!namespace) return fileName;
  return `${namespace.replace(/^\/+|\/+$/g, '')}/${fileName}`.replace(/^\/+/, '');
};

const mapSourceToScope = (source: CodexFileSummary['source']): AgentScope => (
  source === 'user' || source === 'project' || source === 'plugin' ? source : 'plugin'
);

const mapSubagentSourceToScope = (source: CodexSubagentItem['source']): AgentScope => (
  source === 'user' || source === 'project' || source === 'plugin' ? source : 'plugin'
);

const escapeTomlString = (value: string) => value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

const subagentDefinitionToToml = (definition?: CodexSubagentDefinition | null): string => {
  if (!definition) return '';
  const lines = [
    `name = "${escapeTomlString(definition.name)}"`,
    `description = "${escapeTomlString(definition.description)}"`,
    `developer_instructions = "${escapeTomlString(definition.developer_instructions)}"`,
  ];
  if (definition.nickname_candidates?.length) {
    lines.push(`nickname_candidates = [${definition.nickname_candidates.map((item) => `"${escapeTomlString(item)}"`).join(', ')}]`);
  }
  if (definition.model) lines.push(`model = "${escapeTomlString(definition.model)}"`);
  if (definition.model_reasoning_effort) lines.push(`model_reasoning_effort = "${escapeTomlString(definition.model_reasoning_effort)}"`);
  if (definition.sandbox_mode) lines.push(`sandbox_mode = "${escapeTomlString(definition.sandbox_mode)}"`);
  return `${lines.join('\n')}\n`;
};

const mapSummaryToDocument = (summary: CodexFileSummary, content = ''): AgentDocument => ({
  id: buildDocumentId(summary.source, summary.path),
  title: fileNameFromPath(summary.path),
  description: '',
  content,
  scope: mapSourceToScope(summary.source),
  size: formatDocumentContentSize(content || ' '),
  metadata: {
    fileName: summary.path,
    source: summary.source,
    readOnly: summary.readOnly,
    sizeBytes: summary.sizeBytes,
    ...summary.metadata,
  },
  pluginName: typeof summary.metadata?.pluginName === 'string' ? summary.metadata.pluginName : undefined,
  marketplaceName: typeof summary.metadata?.marketplaceName === 'string' ? summary.metadata.marketplaceName : undefined,
});

const mapSubagentToDocument = (item: CodexSubagentItem): AgentDocument => {
  const content = item.content || subagentDefinitionToToml(item.definition);
  return {
    id: item.id,
    title: item.name,
    description: item.definition?.description ?? '',
    content,
    scope: mapSubagentSourceToScope(item.source),
    size: formatDocumentContentSize(content || ' '),
    metadata: {
      ...item.metadata,
      definition: item.definition,
      fileName: item.relativePath,
      relativePath: item.relativePath,
      source: item.source,
      readOnly: item.readOnly,
      editable: item.editable,
      effective: item.effective,
      overridden: item.overridden,
      format: 'toml',
    },
    pluginName: item.pluginName ?? undefined,
    marketplaceName: item.marketplaceName ?? undefined,
  };
};

export interface CodexDocumentResourcePageProps {
  resource: CodexDocumentResource;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
}

const CodexDocumentResourcePage: React.FC<CodexDocumentResourcePageProps> = ({
  resource,
  selectedId: selectedIdProp,
  onSelect: onSelectProp,
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const queryClient = useQueryClient();
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(null);
  const [subagentsResponse, setSubagentsResponse] = useState<CodexSubagentsResponse | null>(null);
  const defaults = resourceDefaults[resource];
  const selectedId = selectedIdProp !== undefined ? selectedIdProp : internalSelectedId;
  const setSelectedId = onSelectProp ?? setInternalSelectedId;

  const documentsQuery = useQuery({
    queryKey: ['codex-document-resource', runtimeBaseUrl, workspaceId, resource],
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    queryFn: async () => {
      if (resource === 'subagents') {
        const response = await api.listCodexSubagents(runtimeBaseUrl || '', workspaceId || '');
        setSubagentsResponse(response);
        return response.items.map(mapSubagentToDocument);
      }

      const summariesById = new Map<string, CodexFileSummary>();
      for (const layer of EDITABLE_LAYERS) {
        const response = await api.listCodexFiles(runtimeBaseUrl || '', workspaceId || '', resource, layer);
        for (const summary of response.files) {
          const id = buildDocumentId(summary.source, summary.path);
          if (!summariesById.has(id)) {
            summariesById.set(id, summary);
          }
        }
      }

      const documents = await Promise.all(
        Array.from(summariesById.values()).map(async (summary) => {
          if (summary.readOnly || (summary.source !== 'project' && summary.source !== 'user')) {
            return mapSummaryToDocument(summary, '');
          }
          try {
            const file = await api.getCodexFile(
              runtimeBaseUrl || '',
              workspaceId || '',
              resource,
              summary.source,
              summary.path,
            );
            return mapSummaryToDocument(summary, file.content);
          } catch (error) {
            logger.error('loadCodexDocumentFailed', { resource, path: summary.path, error });
            return mapSummaryToDocument(summary, '');
          }
        }),
      );

      return documents.sort((a, b) => a.title.localeCompare(b.title));
    },
  });

  const baseDocuments = documentsQuery.data ?? [];
  const selectedDocumentSummary = useMemo(() => {
    const document = baseDocuments.find((item) => item.id === selectedId);
    const source = document?.metadata?.source;
    const path = document?.metadata?.fileName;
    if ((source !== 'project' && source !== 'user') || typeof path !== 'string') {
      return null;
    }
    return { source, path };
  }, [baseDocuments, selectedId]);

  const selectedDocumentQuery = useQuery({
    queryKey: [
      'codex-document-resource-selected-content',
      runtimeBaseUrl,
      workspaceId,
      resource,
      selectedDocumentSummary?.source,
      selectedDocumentSummary?.path,
    ],
    enabled: Boolean(
      runtimeBaseUrl
      && workspaceId
      && selectedDocumentSummary?.source
      && selectedDocumentSummary?.path,
    ),
    queryFn: async () => api.getCodexFile(
      runtimeBaseUrl || '',
      workspaceId || '',
      resource,
      selectedDocumentSummary?.source ?? 'project',
      selectedDocumentSummary?.path ?? '',
    ),
  });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['codex-document-resource', runtimeBaseUrl, workspaceId, resource] });
  };

  const createDocument = async (document: AgentDocument) => {
    const scope = document.scope === 'user' ? 'user' : 'project';
    if (resource === 'subagents') {
      const response = await api.saveCodexSubagent(runtimeBaseUrl || '', workspaceId || '', {
        layer: scope,
        path: (document.metadata?.relativePath as string | undefined) ?? null,
        content: document.metadata?.rawMode ? document.content : null,
        definition: document.metadata?.rawMode ? null : document.metadata?.definition as CodexSubagentDefinition | null,
      });
      await refresh();
      return mapSubagentToDocument(response);
    }

    const path = buildDocumentPath(document, defaults.fileName);
    const response = await api.updateCodexFile(runtimeBaseUrl || '', workspaceId || '', resource, scope, path, document.content);
    const created = mapSummaryToDocument({
      name: fileNameFromPath(path),
      path,
      sizeBytes: document.content.length,
      source: scope,
      readOnly: false,
      metadata: {},
    }, response.content);
    await refresh();
    return created;
  };

  const updateDocument = async (document: AgentDocument) => {
    const scope = document.scope === 'user' ? 'user' : 'project';
    if (resource === 'subagents') {
      const response = await api.saveCodexSubagent(runtimeBaseUrl || '', workspaceId || '', {
        layer: scope,
        path: (document.metadata?.relativePath as string | undefined) ?? null,
        content: document.metadata?.rawMode ? document.content : null,
        definition: document.metadata?.rawMode ? null : document.metadata?.definition as CodexSubagentDefinition | null,
      });
      await refresh();
      return mapSubagentToDocument(response);
    }

    const path = buildDocumentPath(document, defaults.fileName);
    const response = await api.updateCodexFile(runtimeBaseUrl || '', workspaceId || '', resource, scope, path, document.content);
    const updated = mapSummaryToDocument({
      name: fileNameFromPath(path),
      path,
      sizeBytes: document.content.length,
      source: scope,
      readOnly: false,
      metadata: {},
    }, response.content);
    await refresh();
    return updated;
  };

  const deleteDocument = async (id: string) => {
    const document = baseDocuments.find((item) => item.id === id);
    if (!document) return;
    const source = document.metadata?.source;
    if (source !== 'project' && source !== 'user') return;
    const path = (document.metadata?.relativePath as string | undefined)
      || (document.metadata?.fileName as string | undefined)
      || document.title;
    if (resource === 'subagents') {
      await api.deleteCodexSubagent(runtimeBaseUrl || '', workspaceId || '', source, path);
    } else {
      await api.deleteCodexFile(runtimeBaseUrl || '', workspaceId || '', resource, source, path);
    }
    await refresh();
  };

  const DialogWrapper = useMemo(() => {
    const Wrapper: React.FC<DocumentWorkflowDialogProps<AgentDocument>> = (props) => {
      if (resource === 'prompts') {
        return (
          <AgentCommandDialog
            {...props}
            format="markdown"
            availableScopes={CODEX_DOCUMENT_SCOPES}
            i18nNamespace="workspace.agentSettings.codex"
            dialogKey="prompts"
          />
        );
      }
      if (resource === 'subagents') {
        return <CodexSubagentDialog {...props} />;
      }
      return <AgentDefinitionDialog {...props} i18nNamespace="workspace.agentSettings.codex" />;
    };
    Wrapper.displayName = 'CodexDocumentResourceDialog';
    return Wrapper;
  }, [resource]);

  const documents = useMemo(() => {
    if (!selectedId || !selectedDocumentQuery.data) {
      return baseDocuments;
    }
    return baseDocuments.map((document) => {
      if (document.id !== selectedId) {
        return document;
      }
      const content = selectedDocumentQuery.data.content;
      return {
        ...document,
        content,
        size: formatDocumentContentSize(content || ' '),
        metadata: {
          ...document.metadata,
          sizeBytes: content.length,
        },
      };
    });
  }, [baseDocuments, selectedDocumentQuery.data, selectedId]);

  React.useEffect(() => {
    const selectedExists = selectedId ? documents.some((document) => document.id === selectedId) : false;
    if (documents.length > 0 && (!selectedId || !selectedExists)) {
      setSelectedId(documents[0].id);
    }
  }, [documents, selectedId, setSelectedId]);

  const registry = resource === 'subagents' ? subagentsResponse?.registry ?? [] : [];

  return (
    <div className="flex h-full flex-col">
      {registry.length > 0 ? (
        <div className="border-b border-border bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
          {registry.map((source) => (
            <span key={`${source.layer}:${source.path}`} className="mr-4">
              {t('workspace.agentSettings.codex.subagents.registry.summary', {
                layer: t(`workspace.agentSettings.codex.documents.scope.values.${source.layer}`),
                maxThreads: source.settings.max_threads ?? '-',
                maxDepth: source.settings.max_depth ?? '-',
                jobMaxRuntime: source.settings.job_max_runtime_seconds ?? '-',
              })}
            </span>
          ))}
        </div>
      ) : null}
      <AgentDocumentPage
      documents={documents}
      selectedId={selectedId}
      onSelect={setSelectedId}
      onCreate={createDocument}
      onUpdate={updateDocument}
      onDelete={deleteDocument}
      isLoading={documentsQuery.isFetching && documents.length === 0}
      error={documentsQuery.error instanceof Error ? documentsQuery.error.message : null}
      onRefresh={refresh}
      dialogComponent={DialogWrapper}
      i18nNamespace="workspace.agentSettings.codex"
      config={{
        metaKey: defaults.metaKey,
        contentFormat: defaults.format,
        createButtonLabel: t(`workspace.agentSettings.codex.${resource}.actions.create`),
        emptyStateTitle: t(`workspace.agentSettings.codex.${resource}.empty.title`),
        emptyStateDescription: t(`workspace.agentSettings.codex.${resource}.empty.description`),
        dialogTitle: t(`workspace.agentSettings.codex.${resource}.pageTitle`),
      }}
      />
    </div>
  );
};

export default CodexDocumentResourcePage;
