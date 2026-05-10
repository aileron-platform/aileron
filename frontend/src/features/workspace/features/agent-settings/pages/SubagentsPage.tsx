import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DocumentPage } from '../components/DocumentPage';
import { AgentDefinitionDialog } from '../components/dialogs/AgentDefinitionDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import { sortAgentSettingsScopeValues } from '../components/SettingsSourcePrimitives';
import type { AgentDocument, AgentScope } from '../types';

export interface SubagentsPageProps {
  apiPrefix?: string;
  availableScopes?: AgentScope[];
  i18nNamespace?: string;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
}

const SubagentsPage: React.FC<SubagentsPageProps> = ({
  apiPrefix = 'claude-code',
  availableScopes = ['project', 'user', 'plugin'],
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
      const docs = await api.listSubagents(runtimeBaseUrl, workspaceId);
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
    const created = await api.createSubagent(runtimeBaseUrl, workspaceId, doc);
    await loadDocuments();
    return created;
  }, [api, runtimeBaseUrl, workspaceId, loadDocuments]);

  const handleUpdate = useCallback(async (doc: AgentDocument): Promise<AgentDocument> => {
    const updated = await api.updateSubagent(runtimeBaseUrl, workspaceId, doc);
    await loadDocuments();
    return updated;
  }, [api, runtimeBaseUrl, workspaceId, loadDocuments]);

  const handleDelete = useCallback(async (id: string) => {
    const doc = documents.find((item) => item.id === id);
    if (!doc) return;
    await api.deleteSubagent(runtimeBaseUrl, workspaceId, doc);
    await loadDocuments();
  }, [api, runtimeBaseUrl, workspaceId, documents, loadDocuments]);

  const effectiveScopes = useMemo(() => sortAgentSettingsScopeValues(availableScopes), [availableScopes]);

  const DialogWrapper = useMemo(() => {
    const Wrapper: React.FC<{
      open: boolean;
      mode: 'create' | 'edit';
      initialValue?: AgentDocument | null;
      onClose: () => void;
      onSubmit: (document: AgentDocument) => Promise<void> | void;
    }> = (props) => (
      <AgentDefinitionDialog
        {...props}
        i18nNamespace={i18nNamespace}
      />
    );
    Wrapper.displayName = 'SubagentDialogWrapper';
    return Wrapper;
  }, [i18nNamespace]);

  const visibleDocuments = useMemo(
    () => documents.filter((doc) => effectiveScopes.includes(doc.scope)),
    [effectiveScopes, documents],
  );

  return (
    <DocumentPage
      documents={visibleDocuments}
      selectedId={selectedIdValue}
      onSelect={setSelectedId}
      onCreate={handleCreate}
      onUpdate={handleUpdate}
      onDelete={handleDelete}
      isLoading={loading}
      error={error}
      onRefresh={loadDocuments}
      dialogComponent={DialogWrapper}
      i18nNamespace={i18nNamespace}
      showSidebar={false}
      config={{
        metaKey: 'subagents',
        contentFormat: 'markdown',
        createButtonLabel: t(`${i18nNamespace}.subagents.actions.create`),
        emptyStateTitle: t(`${i18nNamespace}.subagents.empty.title`),
        emptyStateDescription: t(`${i18nNamespace}.subagents.empty.description`),
        dialogTitle: t(`${i18nNamespace}.subagents.pageTitle`),
      }}
    />
  );
};

export default SubagentsPage;
