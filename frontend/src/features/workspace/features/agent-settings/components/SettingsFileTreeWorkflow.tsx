import React from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  FileManagementDialogs,
  FileManagementSidebarWorkflow,
  type FileConflictWorkflowTransport,
  type FileManagementSidebarInteractionState,
  type UseFileTreeManagerOptions,
  type FileTreeDataAdapter,
  type FileTreeResourceIdentity,
} from '@/shared/components/file-workbench';
import { createLogger } from '@/shared/services/logger';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { AgentSettingsLayerSelector } from './AgentSettingsSourceControls';
import {
  buildChildPath,
  getParentPath,
  SettingsFileTreeSidebarBody,
  uploadFilesWithPicker,
  type SettingsFileConflictPayload,
  type StartSettingsDestinationConflict,
  type DialogState,
} from './settingsFileTreeWorkflowHelpers';
import type { SettingsFileSelection } from './settingsFileTreeWorkflowModel';

const logger = createLogger('SettingsFileTreeWorkflow');

type StartUploadHandler = (targetPath: string, files: File[]) => Promise<void>;

export interface SettingsFileTreeScopeOption<TScope extends string = string> {
  value: TScope;
  label: string;
  icon?: React.ReactNode;
}

export interface SettingsFileTreeWorkflowLabels {
  title: string;
  scopeLabel: string;
  searchPlaceholder: string;
}

export interface SettingsFileTreeWorkflowProps<TScope extends string = string> {
  adapter: FileTreeDataAdapter;
  resourceIdentity: FileTreeResourceIdentity;
  scope: TScope;
  scopeOptions: Array<SettingsFileTreeScopeOption<TScope>>;
  readOnlyScopes?: TScope[];
  labels: SettingsFileTreeWorkflowLabels;
  icon: LucideIcon;
  showHeader?: boolean;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onScopeChange: (scope: TScope) => void;
  onSelect: (file: SettingsFileSelection<TScope>) => void;
  toolbarRightContent?: React.ReactNode;
  loadEnabled?: boolean;
  refreshSignal?: unknown;
  onRefresh?: () => Promise<void>;
  loggerContext?: Record<string, unknown>;
  fileConflictTransport?: FileConflictWorkflowTransport<SettingsFileConflictPayload>;
}

export const SettingsFileTreeWorkflow = <TScope extends string = string>({
  adapter,
  resourceIdentity,
  scope,
  scopeOptions,
  readOnlyScopes = [],
  labels,
  icon: HeaderIcon,
  showHeader = true,
  isCollapsed,
  onToggleCollapse,
  onScopeChange,
  onSelect,
  toolbarRightContent,
  loadEnabled = true,
  refreshSignal,
  onRefresh,
  loggerContext = {},
  fileConflictTransport,
}: SettingsFileTreeWorkflowProps<TScope>) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const isReadOnly = readOnlyScopes.includes(scope);
  const stateOptions: UseFileTreeManagerOptions['stateOptions'] = { enableMultiSelect: !isReadOnly };
  const startUploadRef = React.useRef<StartUploadHandler | null>(null);
  const startDestinationConflictRef = React.useRef<StartSettingsDestinationConflict | null>(null);

  return (
    <FileManagementSidebarWorkflow
      adapter={adapter}
      resourceIdentity={resourceIdentity}
      title={labels.title}
      searchPlaceholder={labels.searchPlaceholder}
      headerIcon={HeaderIcon}
      showHeader={showHeader}
      scopeContent={(manager) => (
        <AgentSettingsLayerSelector
          value={scope}
          onChange={(value) => {
            onScopeChange(value as TScope);
            manager.state.clearSelection();
          }}
          options={scopeOptions}
          label={labels.scopeLabel}
        />
      )}
      toolbarRightContent={toolbarRightContent}
      capabilities={{
        canCreateFile: !isReadOnly,
        canCreateFolder: !isReadOnly,
        canUpload: !isReadOnly,
      }}
      onCreateFile={isReadOnly ? undefined : (manager, interactionState) => {
        interactionState.setDialogState({ type: 'create-file', parentPath: getParentPath(manager.state.contextMenu?.node) });
      }}
      onCreateFolder={isReadOnly ? undefined : (manager, interactionState) => {
        interactionState.setDialogState({ type: 'create-folder', parentPath: getParentPath(manager.state.contextMenu?.node) });
      }}
      onUpload={isReadOnly ? undefined : (manager) => {
        const targetPath = manager.state.contextMenu?.node?.type === 'directory' ? manager.state.contextMenu.node.path : '';
        uploadFilesWithPicker(
          manager,
          loggerContext,
          targetPath,
          async (path, files) => {
            await startUploadRef.current?.(path, files);
          },
        );
      }}
      isCollapsed={isCollapsed}
      onToggleCollapse={onToggleCollapse}
      loadEnabled={loadEnabled}
      refreshSignal={refreshSignal}
      onRefresh={isReadOnly ? undefined : onRefresh}
      stateOptions={stateOptions}
      renderBody={({ manager, isReadOnly: sidebarReadOnly, interactionState }) => {
        return (
          <SettingsFileTreeSidebarBody
            manager={manager}
            isReadOnly={sidebarReadOnly}
            scope={scope}
            onSelect={onSelect}
            interactionState={interactionState as FileManagementSidebarInteractionState<DialogState>}
            loggerContext={loggerContext}
            fileConflictTransport={fileConflictTransport}
            registerStartUpload={(handler) => {
              startUploadRef.current = handler;
            }}
            registerStartDestinationConflict={(handler) => {
              startDestinationConflictRef.current = handler;
            }}
          />
        );
      }}
      dialogs={isReadOnly ? undefined : ({ manager, interactionState }) => (
        <FileManagementDialogs
          dialogState={interactionState.dialogState as DialogState}
          onClose={interactionState.closeDialog}
          onCreateFile={async (name) => {
            const dialogState = interactionState.dialogState as DialogState;
            if (dialogState?.type !== 'create-file') return;
            try {
              const targetPath = buildChildPath(dialogState.parentPath, name);
              if (startDestinationConflictRef.current) {
                return await startDestinationConflictRef.current({
                  operation: 'create',
                  targetPath,
                  sourcePath: targetPath,
                  entryType: 'file',
                  content: '',
                });
              }
              const response = await manager.createFileAndOpen(targetPath, '');
              if (!response.success) {
                throw new Error(response.error || t('common.fileOperations.error.fileOperationFailed'));
              }
            } catch (error) {
              logger.error('createFileFailed', { ...loggerContext, error });
              throw error;
            }
          }}
          onCreateFolder={async (name) => {
            const dialogState = interactionState.dialogState as DialogState;
            if (dialogState?.type !== 'create-folder') return;
            try {
              const targetPath = buildChildPath(dialogState.parentPath, name);
              if (startDestinationConflictRef.current) {
                return await startDestinationConflictRef.current({
                  operation: 'create',
                  targetPath,
                  sourcePath: targetPath,
                  entryType: 'directory',
                });
              }
              const response = await manager.operations.createDirectory(targetPath);
              if (!response.success) {
                throw new Error(response.error || t('common.fileOperations.error.fileOperationFailed'));
              }
              await manager.loadTree();
            } catch (error) {
              logger.error('createFolderFailed', { ...loggerContext, error });
              throw error;
            }
          }}
          onRename={async (newName) => {
            const dialogState = interactionState.dialogState as DialogState;
            if (dialogState?.type !== 'rename') return;
            try {
              const newPath = buildChildPath(getParentPath(dialogState.node), newName);
              if (startDestinationConflictRef.current) {
                return await startDestinationConflictRef.current({
                  operation: 'move',
                  targetPath: newPath,
                  sourcePath: dialogState.node.path,
                  entryType: dialogState.node.type,
                });
              }
              const response = await manager.renameFileAndUpdateTab(dialogState.node.path, newPath);
              if (!response.success) {
                throw new Error(response.error || t('common.fileOperations.error.fileOperationFailed'));
              }
            } catch (error) {
              logger.error('renameFailed', { ...loggerContext, error });
              throw error;
            }
          }}
          onDelete={async () => {
            const dialogState = interactionState.dialogState as DialogState;
            if (dialogState?.type !== 'delete') return;
            try {
              const response = await manager.deleteFileAndCloseTab(
                dialogState.node.path,
                dialogState.node.type === 'directory',
              );
              if (!response.success) {
                throw new Error(response.error || t('common.fileOperations.error.fileOperationFailed'));
              }
            } catch (error) {
              logger.error('deleteFailed', { ...loggerContext, error });
              throw error;
            }
          }}
          onBatchDelete={async () => {
            const dialogState = interactionState.dialogState as DialogState;
            if (dialogState?.type !== 'batch-delete') return;
            const paths = dialogState.nodes.map((node) => node.path);
            try {
              const response = await manager.batchDeleteAndCloseTabs(
                paths,
                dialogState.nodes.some((node) => node.type === 'directory'),
              );
              response.failed.forEach((failure) => {
                toast({
                  title: t('common.fileOperations.error.fileOperationFailed'),
                  description: failure.error || failure.path,
                  variant: 'destructive',
                });
              });
              if (response.successCount === paths.length) {
                manager.state.clearSelection();
              }
              if (response.failedCount > 0) {
                return { suppressSuccessToast: true };
              }
            } catch (error) {
              logger.error('batchDeleteFailed', { ...loggerContext, error });
              throw error;
            }
          }}
          getAffectedUnsavedTabsCount={(paths) => manager.editor.tabs.filter((tab) => (
            tab.isModified
            && paths.some((path) => tab.path === path || tab.path.startsWith(`${path}/`))
          )).length}
        />
      )}
    />
  );
};

SettingsFileTreeWorkflow.displayName = 'SettingsFileTreeWorkflow';
