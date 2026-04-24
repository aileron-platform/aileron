import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DocumentPage } from '../components/DocumentPage';
import { CommandDialog } from '@/shared/components/dialogs';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { ClaudeDocument, ClaudeScope } from '../../claude-code/types';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';

export interface SlashCommandsPageProps {
  apiPrefix?: string;
  availableScopes?: ClaudeScope[];
  format?: 'markdown' | 'toml';
  i18nNamespace?: string;
}

const SlashCommandsPage: React.FC<SlashCommandsPageProps> = ({
  apiPrefix = 'claude-code',
  availableScopes = ['project', 'user'],
  format = 'markdown',
  i18nNamespace = 'workspace.claudeCode',
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();

  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const [documents, setDocuments] = useState<ClaudeDocument[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const docs = await api.listSlashCommands(runtimeBaseUrl, workspaceId);
      setDocuments(docs);
      if (docs.length > 0 && !selectedId) {
        setSelectedId(docs[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [api, runtimeBaseUrl, workspaceId, selectedId]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: ['slashCommands'],
    onRefresh: loadDocuments,
  });

  const handleCreate = useCallback(async (doc: ClaudeDocument): Promise<ClaudeDocument> => {
    const created = await api.createSlashCommand(runtimeBaseUrl, workspaceId, doc);
    await loadDocuments();
    return created;
  }, [api, runtimeBaseUrl, workspaceId, loadDocuments]);

  const handleUpdate = useCallback(async (doc: ClaudeDocument): Promise<ClaudeDocument> => {
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

  // 包裝 CommandDialog 以注入 format 和 availableScopes
  const DialogWrapper = useMemo(() => {
    const Wrapper: React.FC<{
      open: boolean;
      mode: 'create' | 'edit';
      initialValue?: ClaudeDocument | null;
      onClose: () => void;
      onSubmit: (document: ClaudeDocument) => Promise<void> | void;
    }> = (props) => (
      <CommandDialog
        {...props}
        format={format}
        availableScopes={availableScopes}
        i18nNamespace={i18nNamespace}
      />
    );
    Wrapper.displayName = 'CommandDialogWrapper';
    return Wrapper;
  }, [format, availableScopes, i18nNamespace]);

  return (
    <DocumentPage
      documents={documents}
      selectedId={selectedId}
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
        createButtonLabel: t(`${i18nNamespace}.slashCommands.actions.create`),
        emptyStateTitle: t(`${i18nNamespace}.slashCommands.empty.title`),
        emptyStateDescription: t(`${i18nNamespace}.slashCommands.empty.description`),
        dialogTitle: t(`${i18nNamespace}.slashCommands.pageTitle`),
      }}
    />
  );
};

export default SlashCommandsPage;
