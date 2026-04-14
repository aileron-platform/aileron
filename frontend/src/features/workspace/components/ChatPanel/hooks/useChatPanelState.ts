import { useCallback, useMemo, useState } from 'react';
import type { ChatUploadItem, ChatCodeReference } from '../types';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useChatPanelState');

export interface ChatPanelUIState {
  draftMessage: string;
  isFileDialogOpen: boolean;
  isUploadDialogOpen: boolean;
  isSlashDialogOpen: boolean;
  isOpenSpecDialogOpen: boolean;
  isWorkspaceWizardOpen: boolean;
  pendingUploads: ChatUploadItem[];
  codeReferences: ChatCodeReference[];
}

export interface ChatPanelUIActions {
  setDraftMessage: (value: string) => void;
  resetDraftMessage: () => void;
  openFileDialog: () => void;
  closeFileDialog: () => void;
  openUploadDialog: () => void;
  closeUploadDialog: () => void;
  queueUploads: (files: File[] | FileList) => void;
  setUploads: (updater: (uploads: ChatUploadItem[]) => ChatUploadItem[]) => void;
  updateUploadStatus: (uploadId: string, status: ChatUploadItem['status']) => void;
  removeUpload: (uploadId: string) => void;
  clearUploads: () => void;
  addCodeReference: (reference: Omit<ChatCodeReference, 'id'>) => void;
  removeCodeReference: (referenceId: string) => void;
  clearCodeReferences: () => void;
  openSlashDialog: () => void;
  closeSlashDialog: () => void;
  openOpenSpecDialog: () => void;
  closeOpenSpecDialog: () => void;
  openWorkspaceWizard: () => void;
  closeWorkspaceWizard: () => void;
}

export const useChatPanelState = (): [ChatPanelUIState, ChatPanelUIActions] => {
  const [draftMessage, setDraftMessage] = useState('');

  // Add debug logging for setDraftMessage
  const debugSetDraftMessage = useCallback((value: string) => {
    if (import.meta.env.DEV) {
      logger.debug('setDraftMessage called', { value });
    }
    setDraftMessage(value);
  }, []);
  const [isFileDialogOpen, setIsFileDialogOpen] = useState(false);
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false);
  const [isSlashDialogOpen, setIsSlashDialogOpen] = useState(false);
  const [isOpenSpecDialogOpen, setIsOpenSpecDialogOpen] = useState(false);
  const [isWorkspaceWizardOpen, setIsWorkspaceWizardOpen] = useState(false);
  const [pendingUploads, setPendingUploads] = useState<ChatUploadItem[]>([]);
  const [codeReferences, setCodeReferences] = useState<ChatCodeReference[]>([]);

  const createUniqueId = useCallback(() => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }, []);

  const resetDraftMessage = useCallback(() => {
    setDraftMessage('');
  }, []);

  const openFileDialog = useCallback(() => setIsFileDialogOpen(true), []);
  const closeFileDialog = useCallback(() => setIsFileDialogOpen(false), []);

  const openUploadDialog = useCallback(() => setIsUploadDialogOpen(true), []);
  const closeUploadDialog = useCallback(() => setIsUploadDialogOpen(false), []);

  const queueUploads = useCallback(
    (input: File[] | FileList) => {
      const files = Array.isArray(input) ? input : Array.from(input ?? []);
      if (files.length === 0) return;

      setPendingUploads(prev => {
        const existingSignatures = new Set(
          prev.map(item => `${item.file.name}-${item.file.size}-${item.file.lastModified}`)
        );

        const additions = files
          .filter(file => file && !existingSignatures.has(`${file.name}-${file.size}-${file.lastModified}`))
          .map<ChatUploadItem>(file => ({
            id: createUniqueId(),
            file,
            status: 'ready',
          }));

        if (additions.length === 0) {
          return prev;
        }

        return [...prev, ...additions];
      });
    },
    [createUniqueId]
  );

  const setUploads = useCallback(
    (updater: (uploads: ChatUploadItem[]) => ChatUploadItem[]) => {
      setPendingUploads(prev => updater([...prev]));
    },
    []
  );

  const updateUploadStatus = useCallback((uploadId: string, status: ChatUploadItem['status']) => {
    setPendingUploads(prev => prev.map(item => (item.id === uploadId ? { ...item, status } : item)));
  }, []);

  const removeUpload = useCallback((uploadId: string) => {
    setPendingUploads(prev => prev.filter(item => item.id !== uploadId));
  }, []);

  const clearUploads = useCallback(() => {
    setPendingUploads([]);
  }, []);

  const addCodeReference = useCallback((reference: Omit<ChatCodeReference, 'id'>) => {
    setCodeReferences(prev => {
      const existing = prev[0];
      if (
        existing &&
        existing.filePath === reference.filePath &&
        existing.startLine === reference.startLine &&
        existing.endLine === reference.endLine
      ) {
        return prev;
      }

      const id = createUniqueId();
      return [{ ...reference, id }];
    });
  }, [createUniqueId]);

  const removeCodeReference = useCallback((referenceId: string) => {
    setCodeReferences(prev => prev.filter(item => item.id !== referenceId));
  }, []);

  const clearCodeReferences = useCallback(() => {
    setCodeReferences([]);
  }, []);

  const openSlashDialog = useCallback(() => setIsSlashDialogOpen(true), []);
  const closeSlashDialog = useCallback(() => setIsSlashDialogOpen(false), []);
  const openOpenSpecDialog = useCallback(() => setIsOpenSpecDialogOpen(true), []);
  const closeOpenSpecDialog = useCallback(() => setIsOpenSpecDialogOpen(false), []);

  const openWorkspaceWizard = useCallback(() => setIsWorkspaceWizardOpen(true), []);
  const closeWorkspaceWizard = useCallback(() => setIsWorkspaceWizardOpen(false), []);

  const state: ChatPanelUIState = useMemo(() => ({
    draftMessage,
    isFileDialogOpen,
    isUploadDialogOpen,
    isSlashDialogOpen,
    isOpenSpecDialogOpen,
    isWorkspaceWizardOpen,
    pendingUploads,
    codeReferences,
  }), [
    draftMessage,
    isFileDialogOpen,
    isUploadDialogOpen,
    isSlashDialogOpen,
    isOpenSpecDialogOpen,
    isWorkspaceWizardOpen,
    pendingUploads,
    codeReferences,
  ]);

  const actions: ChatPanelUIActions = useMemo(() => ({
    setDraftMessage: debugSetDraftMessage,
    resetDraftMessage,
    openFileDialog,
    closeFileDialog,
    openUploadDialog,
    closeUploadDialog,
    queueUploads,
    setUploads,
    updateUploadStatus,
    removeUpload,
    clearUploads,
    addCodeReference,
    removeCodeReference,
    clearCodeReferences,
    openSlashDialog,
    closeSlashDialog,
    openOpenSpecDialog,
    closeOpenSpecDialog,
    openWorkspaceWizard,
    closeWorkspaceWizard,
  }), [
    debugSetDraftMessage,
    resetDraftMessage,
    openFileDialog,
    closeFileDialog,
    openUploadDialog,
    closeUploadDialog,
    queueUploads,
    setUploads,
    updateUploadStatus,
    removeUpload,
    clearUploads,
    addCodeReference,
    removeCodeReference,
    clearCodeReferences,
    openSlashDialog,
    closeSlashDialog,
    openOpenSpecDialog,
    closeOpenSpecDialog,
    openWorkspaceWizard,
    closeWorkspaceWizard,
  ]);

  return [state, actions];
};
