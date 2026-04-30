import React, { useCallback, useLayoutEffect, useMemo } from 'react';
import { AlertCircle, File as FileIcon, Folder as FolderIcon, Loader2, RefreshCw } from 'lucide-react';
import {
  FileTreeContextMenu,
  FileTreePanel,
  StandardFileTreeLayout,
  useFileTreeContextMenu,
  useFileTreeManager,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { findNodeByPath, getAllFileNodes } from '@/shared/components/file-workbench';
import {
  createTemplateFileWorkbenchAdapter,
  FileViewerWorkbench,
  toFileWorkbenchTab,
  type FileViewerWorkbenchTab,
} from '@/shared/components/file-workbench';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { flattenFileTree } from '@/features/template-management/utils/templateFiles';

const logger = createLogger('TemplateDetailFileViewer');

interface TemplateDetailFileViewerProps {
  templateId: string;
  basePath: string;
  title: string;
  onTreeUpdate?: (nodes: FileTreeNode[], flattenedCount: number) => void;
}

export const TemplateDetailFileViewer: React.FC<TemplateDetailFileViewerProps> = ({
  templateId,
  basePath,
  title,
  onTreeUpdate,
}) => {
  const { t } = useI18n();

  const apiConfig = useMemo(
    () => ({
      type: 'template' as const,
      templateId,
      scope: basePath,
    }),
    [templateId, basePath],
  );

  const manager = useFileTreeManager({
    apiConfig,
    autoLoad: true,
    stateOptions: {
      enableMultiSelect: false,
    },
  });

  const { state: treeState, editor, handleFileSelect, handleFileDoubleClick, loadTree } = manager;
  const { expandNode, nodes, openContextMenu, selectNodeWithModifier } = treeState;

  useLayoutEffect(() => {
    const flattened = flattenFileTree(nodes as Parameters<typeof flattenFileTree>[0]);
    onTreeUpdate?.(nodes, flattened.length);

    nodes
      .filter(node => node.type === 'directory')
      .forEach(node => expandNode(node.path));

    const activePath = editor.activeTab?.path;
    const activeNode = activePath ? findNodeByPath(nodes, activePath) : null;

    if (activeNode?.type === 'file') {
      return;
    }

    const firstFile = getAllFileNodes(nodes)[0];
    if (firstFile) {
      void handleFileSelect(firstFile);
    }
  }, [editor.activeTab?.path, expandNode, handleFileSelect, nodes, onTreeUpdate]);

  const handleNodeClick = useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    selectNodeWithModifier(node.path, modifier);

    if (node.type === 'file' && modifier === 'none') {
      void handleFileSelect(node);
    }
  }, [handleFileSelect, selectNodeWithModifier]);

  const handleNodeDoubleClick = useCallback((node: FileTreeNode) => {
    void handleFileDoubleClick(node);
  }, [handleFileDoubleClick]);

  const handleContextMenu = useCallback((node: FileTreeNode, event: React.MouseEvent) => {
    openContextMenu(event.clientX, event.clientY, node);
  }, [openContextMenu]);

  const handleCopyPath = useCallback((path: string) => {
    void navigator.clipboard?.writeText(path).catch((error) => {
      logger.error('Failed to copy template file path', { error, path });
    });
  }, []);

  const workbenchTabs = useMemo(
    () => editor.tabs.map((tab): FileViewerWorkbenchTab => toFileWorkbenchTab(tab)),
    [editor.tabs],
  );

  const workbenchAdapter = useMemo(() => createTemplateFileWorkbenchAdapter({
    templateId,
    scope: basePath,
    readFile: manager.operations.readFile,
    copyPath: async (path) => {
      handleCopyPath(path);
    },
    revealInTree: (path) => {
      treeState.selectNode(path);
    },
  }), [basePath, handleCopyPath, manager.operations.readFile, templateId, treeState]);

  const handleWorkbenchTabsChange = useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    const nextPaths = new Set(nextTabs.map((tab) => tab.path));

    editor.tabs.forEach((tab) => {
      if (!nextPaths.has(tab.path)) {
        editor.closeTab(tab.path);
      }
    });
  }, [editor]);

  const handleWorkbenchActiveTabChange = useCallback((tabId: string | null) => {
    if (tabId) {
      editor.setActiveTab(tabId);
    }
  }, [editor]);

  const contextMenuItems = useFileTreeContextMenu({
    node: treeState.contextMenu?.node ?? null,
    readOnly: true,
    features: {
      view: true,
      copyPath: treeState.contextMenu?.node?.type === 'file',
    },
    callbacks: {
      onView: (node) => {
        void handleFileSelect(node);
      },
      onCopyPath: handleCopyPath,
      onClose: treeState.closeContextMenu,
    },
    t,
  });

  const flattenedFilesCount = useMemo(
    () => flattenFileTree(treeState.nodes as Parameters<typeof flattenFileTree>[0]).length,
    [treeState.nodes],
  );

  return (
    <div className="flex h-full overflow-hidden rounded-lg border border-border bg-background">
      <div className="w-80 border-r border-border">
        <StandardFileTreeLayout
          searchValue={treeState.searchQuery}
          onSearchChange={treeState.setSearchQuery}
          onSearchClear={treeState.clearSearch}
          searchPlaceholder={t('template.detail.fileViewer.searchPlaceholder')}
          toolbarContent={(
            <div className="flex h-10 items-center justify-between border-b border-sidebar-border bg-sidebar-accent/20 px-3">
              <div className="flex min-w-0 items-center gap-2">
                <FolderIcon className="h-4 w-4 shrink-0 text-primary" />
                <span className="truncate text-sm font-medium text-sidebar-foreground">{title}</span>
                <Badge variant="secondary" className="px-2 text-[11px]">
                  {flattenedFilesCount}
                </Badge>
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={() => {
                  void loadTree();
                }}
                disabled={treeState.isLoading}
                title={t('template.detail.fileViewer.actions.refresh')}
                aria-label={t('template.detail.fileViewer.actions.refresh')}
              >
                {treeState.isLoading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" />
                )}
              </Button>
            </div>
          )}
        >
          <FileTreePanel
            state={treeState}
            onNodeClick={handleNodeClick}
            onNodeDoubleClick={handleNodeDoubleClick}
            onContextMenu={handleContextMenu}
            onRefresh={() => {
              void loadTree();
            }}
            enableSearch={false}
            enableToolbar={false}
            enableMultiSelectBar={false}
            enableDragDrop={false}
            className="flex-1"
          />
          <FileTreeContextMenu
            contextMenu={treeState.contextMenu}
            items={contextMenuItems}
            onClose={treeState.closeContextMenu}
          />
        </StandardFileTreeLayout>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        {treeState.error && (
          <Alert variant="destructive" className="m-4 mb-0">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t('template.detail.fileViewer.errors.loadTree')}</AlertTitle>
            <AlertDescription>{treeState.error}</AlertDescription>
          </Alert>
        )}

        <div className="min-h-0 flex-1">
          {!editor.activeTab && !treeState.isLoading ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <div className="flex items-center gap-2">
                <FileIcon className="h-4 w-4" />
                <span>{t('template.detail.fileViewer.noSelection')}</span>
              </div>
            </div>
          ) : (
            <FileViewerWorkbench
              tabs={workbenchTabs}
              activeTabId={editor.activeTabPath}
              adapter={workbenchAdapter}
              capabilities={{
                canEdit: false,
                canSave: false,
                canReadBlob: true,
                canCopyPath: true,
                canRevealInTree: true,
                canCloseTabs: true,
              }}
              readOnly
              onTabsChange={handleWorkbenchTabsChange}
              onActiveTabChange={handleWorkbenchActiveTabChange}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default TemplateDetailFileViewer;
