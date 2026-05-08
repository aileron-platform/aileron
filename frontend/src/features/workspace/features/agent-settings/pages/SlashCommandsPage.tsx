import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DocumentPage } from '../components/DocumentPage';
import { AgentCommandDialog } from '../components/dialogs/AgentCommandDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import { sortAgentSettingsScopeValues } from '../components/SettingsSourcePrimitives';
import type { AgentDocument, AgentScope } from '../types';

export interface SlashCommandsPageProps {
  apiPrefix?: string;
  availableScopes?: AgentScope[];
  format?: 'markdown' | 'toml';
  i18nNamespace?: string;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
}

const SlashCommandsPage: React.FC<SlashCommandsPageProps> = ({
  apiPrefix = 'claude-code',
  availableScopes = ['project', 'user'],
  format = 'markdown',
  i18nNamespace = 'workspace.agentSettings.common',
  selectedId,
  onSelect,
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();

  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const [documents, setDocuments] = useState<AgentDocument[]>([]);
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(null);
  const isControlled = selectedId !== undefined;
  const selectedIdValue = isControlled ? selectedId : internalSelectedId;
  const setSelectedId = onSelect ?? setInternalSelectedId;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const docs = await api.listSlashCommands(runtimeBaseUrl, workspaceId);
      setDocuments(docs);
      if (docs.length > 0 && !selectedIdValue) {
        setSelectedId(docs[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [api, runtimeBaseUrl, workspaceId, selectedIdValue, setSelectedId]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleCreate = useCallback(async (doc: AgentDocument): Promise<AgentDocument> => {
    const created = await api.createSlashCommand(runtimeBaseUrl, workspaceId, doc);
    await loadDocuments();
    return created;
  }, [api, runtimeBaseUrl, workspaceId, loadDocuments]);

  const handleUpdate = useCallback(async (doc: AgentDocument): Promise<AgentDocument> => {
    const updated = await api.updateSlashCommand(runtimeBaseUrl, workspaceId, doc);
    await loadDocuments();
    return updated;
  }, [api, runtimeBaseUrl, workspaceId, loadDocuments]);

  const handleDelete = useCallback(async (id: string) => {
    const doc = documents.find((d) => d.id === id);
    if (!doc) return;
    await api.deleteSlashCommand(runtimeBaseUrl, workspaceId, doc);
    await loadDocuments();
  }, [api, runtimeBaseUrl, workspaceId, documents, loadDocuments]);

  const handleRefresh = useCallback(async () => {
    await loadDocuments();
  }, [loadDocuments]);

  const effectiveScopes = useMemo(() => sortAgentSettingsScopeValues(availableScopes), [availableScopes]);

  const DialogWrapper = useMemo(() => {
    const Wrapper: React.FC<{
      open: boolean;
      mode: 'create' | 'edit';
      initialValue?: AgentDocument | null;
      onClose: () => void;
      onSubmit: (document: AgentDocument) => Promise<void> | void;
    }> = (props) => (
        <AgentCommandDialog
        {...props}
        format={format}
        availableScopes={effectiveScopes.filter((scope) => scope !== 'extension' && scope !== 'plugin')}
        i18nNamespace={i18nNamespace}
      />
    );
    Wrapper.displayName = 'CommandDialogWrapper';
    return Wrapper;
  }, [format, effectiveScopes, i18nNamespace]);

  return (
    <DocumentPage
      documents={documents}
      selectedId={selectedIdValue}
      onSelect={setSelectedId}
      onCreate={handleCreate}
      onUpdate={handleUpdate}
      onDelete={handleDelete}
      isLoading={loading}
      error={error}
      onRefresh={handleRefresh}
      dialogComponent={DialogWrapper}
      i18nNamespace={i18nNamespace}
      config={{
        metaKey: 'slash-commands',
        contentFormat: format,
        showRawToml: false,
        createButtonLabel: t(`${i18nNamespace}.slashCommands.actions.create`),
        emptyStateTitle: t(`${i18nNamespace}.slashCommands.empty.title`),
        emptyStateDescription: t(`${i18nNamespace}.slashCommands.empty.description`),
        dialogTitle: t(`${i18nNamespace}.slashCommands.pageTitle`),
      }}
    />
  );
};

export default SlashCommandsPage;
