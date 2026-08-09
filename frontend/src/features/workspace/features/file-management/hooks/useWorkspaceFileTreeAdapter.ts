import { useCallback, useEffect, useMemo, useRef } from 'react';
import {
  createFileTreeResourceIdentity,
  serializeFileTreeResourceIdentity,
  useFileTreeManager,
} from '@/shared/components/file-workbench';
import { useI18n } from '@/shared/hooks/useI18n';
import { createWorkspaceFileTreeDataAdapter } from '../adapters/workspaceFileTreeDataAdapter';
import type { FileTreeActions, FileTreeState } from '../model/fileManagementTypes';
import { ensureLeadingSlash } from '../model/filePathModel';
import { mapManagerNodes } from '../model/workspaceFileTreeModel';
import { useWorkspaceFileMutations } from './useWorkspaceFileMutations';
import { useWorkspaceFileTreeInteractions } from './useWorkspaceFileTreeInteractions';

interface UseWorkspaceFileTreeAdapterOptions {
  workspaceId?: string;
  runtimeBaseUrl?: string | null;
  contextId?: string | null;
  showHiddenEntries: boolean;
  onShowHiddenEntriesChange?: (showHiddenEntries: boolean) => void;
}

interface WorkspaceFileTreeAdapterResult {
  state: FileTreeState;
  actions: FileTreeActions;
}

export function useWorkspaceFileTreeAdapter(
  options: UseWorkspaceFileTreeAdapterOptions,
): WorkspaceFileTreeAdapterResult {
  const { t } = useI18n();
  const {
    workspaceId,
    runtimeBaseUrl,
    contextId,
    showHiddenEntries,
    onShowHiddenEntriesChange,
  } = options;

  const fileTreeAdapter = useMemo(
    () => createWorkspaceFileTreeDataAdapter({
      workspaceId: workspaceId ?? 'pending-workspace',
      contextId,
      runtimeBaseUrl: runtimeBaseUrl ?? undefined,
      includeHidden: showHiddenEntries,
    }),
    [contextId, runtimeBaseUrl, showHiddenEntries, workspaceId],
  );
  const resourceIdentity = useMemo(
    () => createFileTreeResourceIdentity('workspace', {
      workspaceId: workspaceId ?? 'pending-workspace',
      contextId: contextId ?? null,
      runtimeBaseUrl: runtimeBaseUrl ?? null,
      includeHidden: showHiddenEntries,
    }),
    [contextId, runtimeBaseUrl, showHiddenEntries, workspaceId],
  );

  const manager = useFileTreeManager({
    adapter: fileTreeAdapter,
    resourceIdentity,
    stateOptions: { enableMultiSelect: true },
    autoLoad: false,
  });
  const runtimeReady = Boolean(runtimeBaseUrl && runtimeBaseUrl.length > 0);

  const ensureRuntimeReady = useCallback(() => {
    if (!runtimeReady) {
      manager.state.setError(t('workspace.fileManagement.runtime.unavailableTitle'));
      return false;
    }
    manager.state.setError(null);
    return true;
  }, [manager.state, runtimeReady, t]);

  const loadFileTree = useCallback(async () => {
    if (!ensureRuntimeReady()) {
      return;
    }
    await manager.loadTree();
  }, [ensureRuntimeReady, manager]);

  const refreshFileTree = useCallback(async () => {
    await loadFileTree();
  }, [loadFileTree]);

  const setShowHiddenEntries = useCallback(async (nextShowHiddenEntries: boolean) => {
    onShowHiddenEntriesChange?.(nextShowHiddenEntries);
  }, [onShowHiddenEntriesChange]);

  const toggleShowHiddenEntries = useCallback(async () => {
    onShowHiddenEntriesChange?.(!showHiddenEntries);
  }, [onShowHiddenEntriesChange, showHiddenEntries]);

  const interactions = useWorkspaceFileTreeInteractions({ manager });
  const mutations = useWorkspaceFileMutations({
    workspaceId,
    runtimeBaseUrl,
    contextId,
    ensureRuntimeReady,
    refreshFileTree,
  });
  const resetInteractionState = interactions.resetInteractionState;
  const clearPendingAction = mutations.clearPendingAction;

  const workspaceIdentity = serializeFileTreeResourceIdentity(resourceIdentity);
  const previousWorkspaceIdentityRef = useRef<string | null>(null);
  const previousHiddenVisibilityRef = useRef(showHiddenEntries);

  const resetWorkspaceInteractionState = useCallback(() => {
    clearPendingAction();
    resetInteractionState();
  }, [clearPendingAction, resetInteractionState]);

  useEffect(() => {
    const previousWorkspaceIdentity = previousWorkspaceIdentityRef.current;
    previousWorkspaceIdentityRef.current = workspaceIdentity;

    if (previousWorkspaceIdentity === null || previousWorkspaceIdentity === workspaceIdentity) {
      return;
    }

    resetWorkspaceInteractionState();
  }, [resetWorkspaceInteractionState, workspaceIdentity]);

  useEffect(() => {
    if (previousHiddenVisibilityRef.current === showHiddenEntries) {
      return;
    }

    previousHiddenVisibilityRef.current = showHiddenEntries;

    if (!runtimeReady) {
      return;
    }

    void manager.loadTree();
  }, [manager, runtimeReady, showHiddenEntries]);

  const state = useMemo<FileTreeState>(() => {
    const expandedIds = manager.state.expandedIds;
    return {
      nodes: mapManagerNodes(manager.state.nodes, expandedIds),
      selectedFile: manager.state.selectedId
        ? ensureLeadingSlash(manager.state.selectedId)
        : null,
      selectedFiles: new Set(Array.from(manager.state.selectedIds).map(ensureLeadingSlash)),
      lastSelectedFile: manager.state.lastSelectedId
        ? ensureLeadingSlash(manager.state.lastSelectedId)
        : null,
      isLoading: manager.state.isLoading,
      error: manager.state.error,
      expandedNodes: new Set(Array.from(expandedIds).map(ensureLeadingSlash)),
      pendingAction: mutations.pendingAction,
      draggedNode: interactions.draggedNode,
      dropTarget: interactions.dropTarget,
      showHiddenEntries,
    };
  }, [
    interactions.draggedNode,
    interactions.dropTarget,
    manager.state.error,
    manager.state.expandedIds,
    manager.state.isLoading,
    manager.state.lastSelectedId,
    manager.state.nodes,
    manager.state.selectedId,
    manager.state.selectedIds,
    mutations.pendingAction,
    showHiddenEntries,
  ]);

  const actions = useMemo<FileTreeActions>(() => ({
    loadFileTree,
    refreshFileTree,
    setShowHiddenEntries,
    toggleShowHiddenEntries,
    selectFile: interactions.selectFile,
    selectFileWithModifier: interactions.selectFileWithModifier,
    selectRange: interactions.selectRange,
    toggleMultiSelect: interactions.toggleMultiSelect,
    clearSelection: interactions.clearSelection,
    selectAllFiles: interactions.selectAllFiles,
    expandNode: interactions.expandNode,
    collapseNode: interactions.collapseNode,
    createFile: mutations.createFile,
    createFolder: mutations.createFolder,
    renameFile: mutations.renameFile,
    deleteFile: mutations.deleteFile,
    deleteFiles: mutations.deleteFiles,
    moveNode: mutations.moveNode,
    uploadFiles: mutations.uploadFiles,
    downloadFile: mutations.downloadFile,
    downloadFiles: mutations.downloadFiles,
    readFileContent: mutations.readFileContent,
    saveFileContent: mutations.saveFileContent,
    setDraggedNode: interactions.setDraggedNode,
    setDropTarget: interactions.setDropTarget,
  }), [
    interactions.clearSelection,
    interactions.collapseNode,
    interactions.expandNode,
    interactions.selectAllFiles,
    interactions.selectFile,
    interactions.selectFileWithModifier,
    interactions.selectRange,
    interactions.setDraggedNode,
    interactions.setDropTarget,
    interactions.toggleMultiSelect,
    loadFileTree,
    mutations.createFile,
    mutations.createFolder,
    mutations.deleteFile,
    mutations.deleteFiles,
    mutations.downloadFile,
    mutations.downloadFiles,
    mutations.moveNode,
    mutations.readFileContent,
    mutations.renameFile,
    mutations.saveFileContent,
    mutations.uploadFiles,
    refreshFileTree,
    setShowHiddenEntries,
    toggleShowHiddenEntries,
  ]);

  return { state, actions };
}

export type { WorkspaceFileTreeAdapterResult };
