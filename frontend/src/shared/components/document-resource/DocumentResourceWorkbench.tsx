import React, { useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  DocumentMetadataAdapter,
  DocumentTemplateResourceType,
  DocumentWorkbenchRenderSurface,
} from '@/shared/components/document-workflow';
import { DocumentWorkbench } from './DocumentWorkbench';
import type {
  DocumentResourceItem,
  DocumentResourceScope,
  DocumentDialogProps,
  DocumentWorkbenchConfig,
  DocumentSource,
  ResourceListResult,
} from './model/documentResourceTypes';

export interface DocumentResourceWorkbenchProps {
  queryKey: ReadonlyArray<string>;
  source: DocumentSource;
  dialog?: React.ComponentType<DocumentDialogProps>;
  config: DocumentWorkbenchConfig;
  i18nNamespace: string;
  availableScopes?: DocumentResourceScope[];
  renderHeader?: (documents: DocumentResourceItem[]) => React.ReactNode;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  metadataAdapter?: DocumentMetadataAdapter<DocumentResourceItem>;
  templateResourceType?: DocumentTemplateResourceType;
  onDocumentDirtyChange?: (dirty: boolean) => void;
  documentSelectionBlocked?: boolean;
  showSidebar?: boolean;
  showSidebarSearch?: boolean;
  useShellSidebarHeader?: boolean;
  isEnabled?: boolean;
  disabledMessage?: string | null;
  renderDocumentMeta?: (
    document: DocumentResourceItem,
  ) => React.ReactNode;
  readOnly?: boolean;
  renderSurface?: (surface: DocumentWorkbenchRenderSurface) => React.ReactNode;
}

type EnrichedDialogProps = DocumentDialogProps & {
  format?: DocumentWorkbenchConfig['contentFormat'];
  i18nNamespace?: string;
  dialogKey?: 'slashCommands' | 'prompts';
  availableScopes?: DocumentResourceScope[];
};

const dialogKeyOf = (
  metaKey: DocumentWorkbenchConfig['metaKey'],
): EnrichedDialogProps['dialogKey'] =>
  metaKey === 'prompts' ? 'prompts' : 'slashCommands';

export const DocumentResourceWorkbench: React.FC<DocumentResourceWorkbenchProps> = ({
  queryKey,
  source,
  dialog,
  config,
  i18nNamespace,
  availableScopes,
  renderHeader,
  selectedId: selectedIdProp,
  onSelect: onSelectProp,
  metadataAdapter,
  templateResourceType,
  onDocumentDirtyChange,
  documentSelectionBlocked,
  showSidebar = false,
  showSidebarSearch = false,
  useShellSidebarHeader = false,
  isEnabled = true,
  disabledMessage = null,
  renderDocumentMeta,
  readOnly = false,
  renderSurface,
}) => {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [internalSelectedId, setInternalSelectedId] = React.useState<string | null>(null);
  const selectedId = selectedIdProp !== undefined ? selectedIdProp : internalSelectedId;
  const setSelectedId = onSelectProp ?? setInternalSelectedId;

  const listQuery = useQuery({
    queryKey: ['document-resource', ...queryKey],
    queryFn: () => source.list(),
    enabled: isEnabled,
    staleTime: 30_000,
  });

  const listResult = listQuery.data;
  const baseDocuments = useMemo(() => listResult?.items ?? [], [listResult]);
  const derivedScopes = useMemo(
    () => listResult?.availableScopes?.map((scope) => scope.scope) ?? availableScopes,
    [availableScopes, listResult],
  );
  const selectedDoc = useMemo(
    () => baseDocuments.find((document) => document.id === selectedId) ?? null,
    [baseDocuments, selectedId],
  );

  const contentQuery = useQuery({
    queryKey: ['document-resource-content', ...queryKey, selectedDoc?.id],
    enabled: Boolean(isEnabled && source.loadContent && selectedDoc),
    queryFn: () => source.loadContent!(selectedDoc as DocumentResourceItem),
    staleTime: 30_000,
  });

  const documents = useMemo<DocumentResourceItem[]>(() => {
    const loaded = contentQuery.data;
    if (!loaded) {
      return baseDocuments;
    }
    return baseDocuments.map((document) => (document.id === loaded.id ? loaded : document));
  }, [baseDocuments, contentQuery.data]);

  useEffect(() => {
    const exists = selectedId ? documents.some((document) => document.id === selectedId) : false;
    if (documents.length > 0 && (!selectedId || !exists)) {
      setSelectedId(documents[0].id);
    }
  }, [documents, selectedId, setSelectedId]);

  const refresh = async () => {
    if (!isEnabled) {
      return;
    }
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['document-resource', ...queryKey] }),
      queryClient.invalidateQueries({ queryKey: ['document-resource-content', ...queryKey] }),
    ]);
  };

  const handleCreate = async (document: DocumentResourceItem) => {
    if (readOnly) {
      throw new Error(t('common.authorization.readOnlyDescription'));
    }
    const created = await source.create(document);
    await refresh();
    queryClient.setQueryData<ResourceListResult>(['document-resource', ...queryKey], (current) => {
      const base = current ?? { items: [], availableScopes: [] };
      const nextDocument = created ?? document;
      const exists = base.items.some((item) => item.id === nextDocument.id);
      return {
        ...base,
        items: exists
          ? base.items.map((item) => (item.id === nextDocument.id ? nextDocument : item))
          : [...base.items, nextDocument],
      };
    });
    return created;
  };

  const handleUpdate = async (document: DocumentResourceItem) => {
    if (readOnly) {
      throw new Error(t('common.authorization.readOnlyDescription'));
    }
    const updated = await source.update(document);
    await refresh();
    return updated;
  };

  const handleMove = async (document: DocumentResourceItem, nextPath: string) => {
    if (readOnly) {
      throw new Error(t('common.authorization.readOnlyDescription'));
    }
    if (!source.move) {
      throw new Error(t('shared.documentWorkflow.metadata.renameUnsupported'));
    }
    const moved = await source.move(document, nextPath);
    await refresh();
    return moved;
  };

  const handleDelete = async (id: string) => {
    if (readOnly) {
      throw new Error(t('common.authorization.readOnlyDescription'));
    }
    const document = documents.find((item) => item.id === id);
    if (!document) {
      return;
    }
    await source.remove(document);
    await refresh();
  };

  const DialogComponent = useMemo(() => {
    if (!dialog) {
      return undefined;
    }
    const SourceDialog = dialog as React.ComponentType<EnrichedDialogProps>;
    const WrappedDialog: React.FC<DocumentDialogProps> = (props) => (
      <SourceDialog
        {...props}
        format={config.contentFormat}
        i18nNamespace={i18nNamespace}
        dialogKey={dialogKeyOf(config.metaKey)}
        availableScopes={derivedScopes}
      />
    );
    WrappedDialog.displayName = 'DocumentResourceDialog';
    return WrappedDialog;
  }, [config.contentFormat, config.metaKey, derivedScopes, dialog, i18nNamespace]);

  const translatedConfig = useMemo<DocumentWorkbenchConfig>(() => ({
    ...config,
    createButtonLabel: config.createButtonLabel ? t(config.createButtonLabel) : undefined,
    emptyStateTitle: t(config.emptyStateTitle),
    emptyStateDescription: t(config.emptyStateDescription),
    dialogTitle: t(config.dialogTitle),
  }), [config, t]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {renderHeader && listQuery.isSuccess ? renderHeader(documents) : null}
      <DocumentWorkbench
        documents={documents}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
        onDelete={handleDelete}
        isLoading={listQuery.isFetching && documents.length === 0}
        error={disabledMessage ?? (listQuery.error instanceof Error ? listQuery.error.message : null)}
        onRefresh={isEnabled ? refresh : undefined}
        dialogComponent={DialogComponent}
        i18nNamespace={i18nNamespace}
        showSidebar={showSidebar}
        config={translatedConfig}
        metadataAdapter={metadataAdapter}
        templateResourceType={templateResourceType}
        onDocumentDirtyChange={onDocumentDirtyChange}
        documentSelectionBlocked={documentSelectionBlocked}
        onRename={source.move ? handleMove : undefined}
        showSidebarSearch={showSidebarSearch}
        useShellSidebarHeader={useShellSidebarHeader}
        renderDocumentMeta={renderDocumentMeta}
        readOnly={readOnly}
        renderSurface={renderSurface}
      />
    </div>
  );
};
