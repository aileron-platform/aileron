import { useCallback, useMemo, useRef, useState } from 'react';
import {
  createDocumentTemplate,
  normalizeDocumentMetadata,
  type DocumentContentDetailHandle,
  type DocumentMetadataValue,
} from '@/shared/components/document-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { getDocumentActionPolicy } from './documentActionPolicy';
import type {
  DocumentResourceItem,
  DocumentWorkbenchProps,
} from './model/documentResourceTypes';

const logger = createLogger('DocumentWorkbench');

type UseDocumentWorkbenchControllerOptions = Pick<
  DocumentWorkbenchProps,
  | 'documents'
  | 'selectedId'
  | 'onSelect'
  | 'onCreate'
  | 'onUpdate'
  | 'onDelete'
  | 'onRefresh'
  | 'config'
  | 'i18nNamespace'
  | 'metadataAdapter'
  | 'templateResourceType'
  | 'onDocumentDirtyChange'
  | 'onRename'
>;

const metadataCreateErrorMessage = (
  err: unknown,
  t: ReturnType<typeof useI18n>['t'],
): string => {
  const error = err as Error & { errorCode?: string };
  if (error.errorCode === 'SUBAGENT_CONFLICT') {
    return t('shared.documentWorkflow.metadata.errors.conflict', {
      name: error.message,
    });
  }
  return err instanceof Error
    ? err.message
    : t('shared.documentWorkflow.metadata.createFailed');
};

const metadataRenameErrorMessage = (
  err: unknown,
  t: ReturnType<typeof useI18n>['t'],
): string => (
  err instanceof Error
    ? err.message
    : t('shared.documentWorkflow.metadata.renameFailed')
);

const documentsConflict = (
  candidate: DocumentResourceItem,
  documents: DocumentResourceItem[],
): boolean => {
  const candidatePath = candidate.metadata?.previousFileName
    ? (candidate.metadata?.fileName ?? candidate.path ?? candidate.title)
    : (
      candidate.metadata?.relativePath
      ?? candidate.metadata?.fileName
      ?? candidate.path
      ?? candidate.title
    );
  return documents.some((document) => {
    const documentPath = document.metadata?.relativePath
      ?? document.metadata?.fileName
      ?? document.path
      ?? document.title;
    return document.scope === candidate.scope && documentPath === candidatePath;
  });
};

export const useDocumentWorkbenchController = ({
  documents,
  selectedId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
  onRefresh,
  config,
  i18nNamespace,
  metadataAdapter,
  templateResourceType,
  onDocumentDirtyChange,
  onRename,
}: UseDocumentWorkbenchControllerOptions) => {
  const { t } = useI18n();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [activeDocument, setActiveDocument] = useState<DocumentResourceItem | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [renameDocument, setRenameDocument] = useState<DocumentResourceItem | null>(null);
  const [metadataValue, setMetadataValue] = useState<DocumentMetadataValue>({
    fileName: '',
    scope: 'project',
  });
  const [detailModeByDocumentId, setDetailModeByDocumentId] = useState<
    Record<string, 'preview' | 'edit'>
  >({});
  const [detailContentMode, setDetailContentMode] = useState<'preview' | 'edit'>(
    'preview',
  );
  const [detailSaving, setDetailSaving] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const detailRef = useRef<DocumentContentDetailHandle | null>(null);

  const documentWorkflowEnabled = Boolean(
    metadataAdapter
    && templateResourceType
    && (
      config.contentFormat === 'markdown'
      || config.contentFormat === 'toml'
      || config.contentFormat === 'plain'
    ),
  );
  const scopeHidden = config.scopeMode === 'hidden';
  const metadataCapabilities = metadataAdapter
    ? {
        ...metadataAdapter.capabilities,
        scope: scopeHidden ? false : metadataAdapter.capabilities.scope,
      }
    : null;
  const metadataScopeOptions = scopeHidden
    ? []
    : [
        {
          value: 'project',
          labelKey: `${i18nNamespace}.documents.scope.values.project`,
        },
        {
          value: 'user',
          labelKey: `${i18nNamespace}.documents.scope.values.user`,
        },
      ];

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedId) ?? null,
    [documents, selectedId],
  );
  const currentIndex = selectedDocument
    ? documents.findIndex((document) => document.id === selectedDocument.id)
    : -1;
  const canNavigatePrevious = currentIndex > 0;
  const canNavigateNext = currentIndex >= 0 && currentIndex < documents.length - 1;
  const selectedDocumentActions = getDocumentActionPolicy(selectedDocument);

  const handleCreateRequest = () => {
    if (documentWorkflowEnabled && metadataAdapter) {
      setMetadataValue(metadataAdapter.read(null));
      setInlineError(null);
      setCreateDialogOpen(true);
      return;
    }
    setDialogMode('create');
    setActiveDocument(null);
    setDialogOpen(true);
  };

  const handleEditRequest = () => {
    if (!getDocumentActionPolicy(selectedDocument).canEdit) {
      return;
    }
    if (documentWorkflowEnabled && selectedDocument) {
      detailRef.current?.edit();
      setDetailModeByDocumentId({ [selectedDocument.id]: 'edit' });
      setDetailContentMode('edit');
      return;
    }
    setDialogMode('edit');
    setActiveDocument(selectedDocument);
    setDialogOpen(true);
  };

  const handleDetailModeChange = useCallback((
    mode: 'preview' | 'edit',
    saving: boolean,
  ) => {
    setDetailContentMode(mode);
    setDetailSaving(saving);
  }, []);

  const handleMetadataCreate = async (value: DocumentMetadataValue) => {
    if (!metadataAdapter || !templateResourceType || !onCreate) {
      return;
    }
    try {
      setIsProcessing(true);
      setInlineError(null);
      const contentFormat = config.contentFormat ?? 'markdown';
      const normalizedValue = normalizeDocumentMetadata(
        value,
        templateResourceType,
        contentFormat,
      );
      if (!normalizedValue.fileName) {
        setInlineError(
          t('shared.documentWorkflow.metadata.errors.fileNameRequired'),
        );
        return;
      }
      const templateContent = createDocumentTemplate(
        templateResourceType,
        normalizedValue,
        t,
        contentFormat,
      );
      const document = metadataAdapter.buildCreate(
        normalizedValue,
        templateContent,
      );
      if (documentsConflict(document, documents)) {
        setInlineError(t('shared.documentWorkflow.metadata.errors.conflict', {
          name: document.title,
        }));
        return;
      }
      const created = await onCreate(document);
      const selectedDocumentId = created?.id ?? document.id;
      onSelect(selectedDocumentId);
      setDetailModeByDocumentId({ [selectedDocumentId]: 'edit' });
      onDocumentDirtyChange?.(false);
      setCreateDialogOpen(false);
    } catch (err) {
      const message = metadataCreateErrorMessage(err, t);
      setInlineError(message);
      logger.error('documentMetadataCreateFailed', { error: err });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRenameRequest = () => {
    if (!selectedDocument || !metadataAdapter) {
      return;
    }
    setRenameDocument(selectedDocument);
    setMetadataValue(metadataAdapter.read(selectedDocument));
    setInlineError(null);
  };

  const handleMetadataRename = async (value: DocumentMetadataValue) => {
    if (!renameDocument || !metadataAdapter || !templateResourceType) {
      return;
    }
    try {
      setIsProcessing(true);
      setInlineError(null);
      const contentFormat = config.contentFormat ?? 'markdown';
      const normalizedValue = normalizeDocumentMetadata({
        fileName: value.fileName,
        namespace: value.namespace,
        scope: value.scope,
      }, templateResourceType, contentFormat);
      if (!normalizedValue.fileName) {
        setInlineError(
          t('shared.documentWorkflow.metadata.errors.fileNameRequired'),
        );
        return;
      }
      const renameTarget = normalizedValue.path ?? normalizedValue.fileName;
      const nextDocument = metadataAdapter.applyRename(
        renameDocument,
        renameTarget,
      );
      const otherDocuments = documents.filter(
        (document) => document.id !== renameDocument.id,
      );
      if (documentsConflict(nextDocument, otherDocuments)) {
        setInlineError(t('shared.documentWorkflow.metadata.errors.conflict', {
          name: normalizedValue.fileName,
        }));
        return;
      }
      if (!onRename) {
        setInlineError(t('shared.documentWorkflow.metadata.renameUnsupported'));
        return;
      }
      const renamed = await onRename(nextDocument, renameTarget);
      onSelect(renamed?.id ?? nextDocument.id);
      setRenameDocument(null);
    } catch (err) {
      const message = metadataRenameErrorMessage(err, t);
      setInlineError(message);
      logger.error('documentMetadataRenameFailed', { error: err });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRefresh = async () => {
    if (!onRefresh) {
      return;
    }
    try {
      setIsProcessing(true);
      await onRefresh();
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDialogSubmit = async (document: DocumentResourceItem) => {
    try {
      setIsProcessing(true);
      if (dialogMode === 'create') {
        if (!onCreate) {
          return;
        }
        const created = await onCreate(document);
        onSelect(created?.id ?? document.id);
      } else {
        const updated = await onUpdate(document);
        onSelect(updated?.id ?? document.id);
      }
      setDialogOpen(false);
      setActiveDocument(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDelete = async () => {
    if (!getDocumentActionPolicy(selectedDocument).canDelete) {
      return;
    }
    const confirmed = window.confirm(
      t(`${i18nNamespace}.documents.confirmDelete`, {
        title: selectedDocument.title,
      }),
    );
    if (!confirmed) {
      return;
    }
    try {
      setIsProcessing(true);
      await onDelete(selectedDocument.id);
      const nextDocuments = documents.filter(
        (document) => document.id !== selectedDocument.id,
      );
      onSelect(nextDocuments[0]?.id ?? null);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleNavigatePrevious = () => {
    if (canNavigatePrevious) {
      onSelect(documents[currentIndex - 1].id);
    }
  };

  const handleNavigateNext = () => {
    if (canNavigateNext) {
      onSelect(documents[currentIndex + 1].id);
    }
  };

  const handleDetailCancel = () => {
    detailRef.current?.cancel();
    setDetailModeByDocumentId({});
    setDetailContentMode('preview');
  };

  const handleDetailSave = () => {
    void detailRef.current?.save();
  };

  const handleContentSave = async (
    document: DocumentResourceItem,
    content: string,
  ) => {
    const updated = await onUpdate({ ...document, content });
    onSelect(updated?.id ?? document.id);
    setDetailModeByDocumentId({});
    setDetailContentMode('preview');
    onDocumentDirtyChange?.(false);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setActiveDocument(null);
  };

  const closeCreateDialog = () => {
    setCreateDialogOpen(false);
    setInlineError(null);
  };

  const closeRenameDialog = () => {
    setRenameDocument(null);
    setInlineError(null);
  };

  return {
    dialogOpen,
    dialogMode,
    activeDocument,
    createDialogOpen,
    renameDocument,
    metadataValue,
    setMetadataValue,
    detailModeByDocumentId,
    detailContentMode,
    detailSaving,
    inlineError,
    isProcessing,
    detailRef,
    documentWorkflowEnabled,
    scopeHidden,
    metadataCapabilities,
    metadataScopeOptions,
    selectedDocument,
    canNavigatePrevious,
    canNavigateNext,
    selectedDocumentActions,
    handleCreateRequest,
    handleEditRequest,
    handleDetailModeChange,
    handleMetadataCreate,
    handleRenameRequest,
    handleMetadataRename,
    handleRefresh,
    handleDialogSubmit,
    handleDelete,
    handleNavigatePrevious,
    handleNavigateNext,
    handleDetailCancel,
    handleDetailSave,
    handleContentSave,
    closeDialog,
    closeCreateDialog,
    closeRenameDialog,
  };
};
