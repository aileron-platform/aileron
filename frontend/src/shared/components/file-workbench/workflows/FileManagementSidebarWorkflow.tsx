import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw, type LucideIcon } from 'lucide-react';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { SidebarCollapseToggle } from '@/shared/components/layout/CollapsedSidebarControls';
import { ResourceSidebarShell } from '@/shared/components/resource-workflow';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { FileTreeSearchBar } from '../primitives/FileTreeSearchBar';
import { FileTreeToolbar } from '../tree/FileTreeToolbar';
import { useFileTreeManager, type UseFileTreeManagerOptions } from '../hooks/useFileTreeManager';
import type { FileTreeResourceIdentity } from '../model/fileTreeAsyncCoordinator';
import type { FileTreeDataAdapter } from '../types';
import {
  isReadOnlyFileManagementCapabilities,
  resolveFileManagementCapabilities,
  type FileManagementCapabilities,
} from './fileManagementCapabilities';

const logger = createLogger('FileManagementSidebarWorkflow');

export type FileManagementTreeManager = ReturnType<typeof useFileTreeManager>;

export interface FileManagementSidebarController {
  state: Pick<
    FileManagementTreeManager['state'],
    'isLoading' | 'searchQuery' | 'setSearchQuery' | 'clearSearch'
  >;
  loadTree: () => Promise<unknown>;
}

export interface FileManagementSidebarInteractionState<TDialogState = unknown> {
  dialogState: TDialogState | null;
  setDialogState: React.Dispatch<React.SetStateAction<TDialogState | null>>;
  closeDialog: () => void;
  draggingPath: string | null;
  setDraggingPath: React.Dispatch<React.SetStateAction<string | null>>;
  dragOverPath: string | null;
  setDragOverPath: React.Dispatch<React.SetStateAction<string | null>>;
}

const useFileManagementSidebarInteractionState = <TDialogState = unknown>(): FileManagementSidebarInteractionState<TDialogState> => {
  const [dialogState, setDialogState] = useState<TDialogState | null>(null);
  const [draggingPath, setDraggingPath] = useState<string | null>(null);
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);

  const closeDialog = useCallback(() => {
    setDialogState(null);
  }, []);

  return {
    dialogState,
    setDialogState,
    closeDialog,
    draggingPath,
    setDraggingPath,
    dragOverPath,
    setDragOverPath,
  };
};

interface FileManagementSidebarWorkflowBaseProps<
  TManager extends FileManagementSidebarController,
> {
  title: string;
  searchPlaceholder: string;
  headerIcon: LucideIcon;
  showHeader?: boolean;
  showToolbar?: boolean;
  scopeContent?: React.ReactNode | ((manager: TManager) => React.ReactNode);
  toolbarRightContent?: React.ReactNode;
  capabilities?: Partial<FileManagementCapabilities>;
  onCreateFile?: (
    manager: TManager,
    interactionState: FileManagementSidebarInteractionState,
  ) => void;
  onCreateFolder?: (
    manager: TManager,
    interactionState: FileManagementSidebarInteractionState,
  ) => void;
  onUpload?: (
    manager: TManager,
    interactionState: FileManagementSidebarInteractionState,
  ) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  loadEnabled?: boolean;
  refreshSignal?: unknown;
  onRefresh?: () => Promise<void>;
  renderBody?: (args: {
    manager: TManager;
    isReadOnly: boolean;
    interactionState: FileManagementSidebarInteractionState;
  }) => React.ReactNode;
  dialogs?: React.ReactNode | ((args: {
    manager: TManager;
    isReadOnly: boolean;
    interactionState: FileManagementSidebarInteractionState;
  }) => React.ReactNode);
}

type ProvidedFileManagementSidebarWorkflowProps<
  TManager extends FileManagementSidebarController,
> = FileManagementSidebarWorkflowBaseProps<TManager> & {
  manager: TManager;
  adapter?: never;
  resourceIdentity?: never;
  stateOptions?: never;
  onTreeLoaded?: never;
  onError?: never;
};

type ManagedFileManagementSidebarWorkflowProps =
  FileManagementSidebarWorkflowBaseProps<FileManagementTreeManager> & {
    adapter: FileTreeDataAdapter;
    resourceIdentity: FileTreeResourceIdentity;
    stateOptions?: UseFileTreeManagerOptions['stateOptions'];
    onTreeLoaded?: UseFileTreeManagerOptions['onTreeLoaded'];
    onError?: UseFileTreeManagerOptions['onError'];
  };

export type FileManagementSidebarWorkflowProps<
  TManager extends FileManagementSidebarController = FileManagementTreeManager,
> =
  | ProvidedFileManagementSidebarWorkflowProps<TManager>
  | ManagedFileManagementSidebarWorkflowProps;

const hasProvidedManager = <TManager extends FileManagementSidebarController>(
  props: FileManagementSidebarWorkflowProps<TManager>,
): props is ProvidedFileManagementSidebarWorkflowProps<TManager> => (
  'manager' in props
);

type FileManagementSidebarWorkflowContentProps<
  TManager extends FileManagementSidebarController,
> = ProvidedFileManagementSidebarWorkflowProps<TManager>;

const FileManagementSidebarWorkflowContent = <TManager extends FileManagementSidebarController>({
  manager,
  title,
  searchPlaceholder,
  headerIcon: HeaderIcon,
  showHeader = true,
  showToolbar = true,
  scopeContent,
  toolbarRightContent,
  capabilities,
  onCreateFile,
  onCreateFolder,
  onUpload,
  isCollapsed,
  onToggleCollapse,
  loadEnabled = true,
  refreshSignal,
  onRefresh,
  renderBody,
  dialogs,
}: FileManagementSidebarWorkflowContentProps<TManager>) => {
  const { t } = useI18n();
  const resolvedCapabilities = resolveFileManagementCapabilities(capabilities);
  const isReadOnly = isReadOnlyFileManagementCapabilities(resolvedCapabilities);
  const loadTree = manager.loadTree;
  const interactionState = useFileManagementSidebarInteractionState();

  useEffect(() => {
    if (loadEnabled) {
      void loadTree();
    }
  }, [loadEnabled, loadTree, refreshSignal]);

  const handleRefresh = useCallback(async () => {
    try {
      await onRefresh?.();
      await loadTree();
    } catch (error) {
      logger.error('refreshFailed', { error });
    }
  }, [loadTree, onRefresh]);

  const resolvedScopeContent = typeof scopeContent === 'function'
    ? scopeContent(manager)
    : scopeContent;

  const toolbar = (
    <FileTreeToolbar
      leftContent={resolvedScopeContent}
      rightContent={toolbarRightContent}
      onCreateFile={resolvedCapabilities.canCreateFile && onCreateFile
        ? () => onCreateFile(manager, interactionState)
        : undefined}
      onCreateFolder={resolvedCapabilities.canCreateFolder && onCreateFolder
        ? () => onCreateFolder(manager, interactionState)
        : undefined}
      onUpload={resolvedCapabilities.canUpload && onUpload
        ? () => onUpload(manager, interactionState)
        : undefined}
      isLoading={manager.state.isLoading}
      isReadOnly={isReadOnly}
    />
  );

  const header = showHeader ? (
    <div className={`h-10 px-3 border-b border-sidebar-border bg-card flex items-center ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
      {!isCollapsed ? (
        <div className="flex items-center gap-2">
          <div className="flex-shrink-0">
            <HeaderIcon className="h-5 w-5 text-sidebar-primary" />
          </div>
          <h2 className="text-sm font-medium text-sidebar-foreground">{title}</h2>
        </div>
      ) : null}
      <div className="flex flex-shrink-0 items-center gap-1">
        {!isCollapsed ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => {
              void handleRefresh();
            }}
            disabled={manager.state.isLoading}
            aria-label={t('common.fileTree.contextMenu.refresh')}
            title={t('common.fileTree.contextMenu.refresh')}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${manager.state.isLoading ? 'animate-spin' : ''}`} />
          </Button>
        ) : null}
        <SidebarCollapseToggle
          collapsed={isCollapsed}
          label={isCollapsed ? t('common.fileTree.sidebar.expand') : t('common.fileTree.sidebar.collapse')}
          onClick={onToggleCollapse}
        />
      </div>
    </div>
  ) : undefined;

  const search = !isCollapsed ? (
    <FileTreeSearchBar
      value={manager.state.searchQuery}
      onChange={manager.state.setSearchQuery}
      onClear={manager.state.clearSearch}
      placeholder={searchPlaceholder}
      containerClassName="border-b border-sidebar-border bg-sidebar-accent/20"
    />
  ) : undefined;

  const body = isCollapsed
    ? (
      <CollapsedSidebarPlaceholder
        icon={HeaderIcon}
        testId="file-management-sidebar-collapsed-icon"
      />
    )
    : renderBody?.({ manager, isReadOnly, interactionState }) ?? null;

  const resolvedDialogs = typeof dialogs === 'function'
    ? dialogs({ manager, isReadOnly, interactionState })
    : dialogs;

  return (
    <>
      <ResourceSidebarShell
        className="border-r border-sidebar-border bg-background"
        header={header}
        search={search}
        scopeFilter={!isCollapsed && showToolbar ? toolbar : undefined}
        body={body}
        bodyClassName="flex flex-1 min-h-0 flex-col overflow-hidden bg-background"
      />
      {resolvedDialogs}
    </>
  );
};

export const FileManagementSidebarWorkflow = <
  TManager extends FileManagementSidebarController = FileManagementTreeManager,
>(props: FileManagementSidebarWorkflowProps<TManager>) => {
  if (hasProvidedManager(props)) {
    return <FileManagementSidebarWorkflowContent {...props} />;
  }

  return <ManagedFileManagementSidebarWorkflow {...props} />;
};

const ManagedFileManagementSidebarWorkflow = (
  props: ManagedFileManagementSidebarWorkflowProps,
) => {
  const {
    adapter,
    resourceIdentity,
    stateOptions,
    onTreeLoaded,
    onError,
    ...contentProps
  } = props;

  const managedTree = useFileTreeManager({
    adapter,
    resourceIdentity,
    stateOptions,
    autoLoad: false,
    onTreeLoaded,
    onError,
  });

  return <FileManagementSidebarWorkflowContent {...contentProps} manager={managedTree} />;
};
