import React, { useCallback, useLayoutEffect, useMemo } from 'react';
import Editor from '@monaco-editor/react';
import { AlertCircle, File as FileIcon, Folder as FolderIcon, Loader2, Lock, RefreshCw } from 'lucide-react';
import { useApp } from '@/app/providers/AppProvider';
import {
  FileEditorPanel,
  FileTreeContextMenu,
  FileTreePanel,
  StandardFileTreeLayout,
  useFileTreeContextMenu,
  useFileTreeManager,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-tree-manager';
import { findNodeByPath, getAllFileNodes, isImageFile } from '@/shared/components/file-tree-manager/utils/fileTreeUtils';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { useI18n } from '@/shared/hooks/useI18n';
import { getLanguageFromFileName } from '@/shared/utils/languageUtils';
import { createLogger } from '@/shared/services/logger';
import { flattenFileTree } from '@/features/template-management/utils/templateFiles';

const logger = createLogger('TemplateDetailFileViewer');

interface TemplateDetailFileViewerProps {
  templateId: string;
  basePath: string;
  title: string;
  onTreeUpdate?: (nodes: FileTreeNode[], flattenedCount: number) => void;
}

const isMarkdownFile = (filename: string) => filename.toLowerCase().endsWith('.md');

const getTemplateFileContentUrl = (templateId: string, scope: string, path: string) =>
  `/api/v1/templates/${templateId}/files/content?scope=${encodeURIComponent(scope)}&path=${encodeURIComponent(path)}`;

export const TemplateDetailFileViewer: React.FC<TemplateDetailFileViewerProps> = ({
  templateId,
  basePath,
  title,
  onTreeUpdate,
}) => {
  const { t } = useI18n();
  const { state } = useApp();

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

  const currentTheme = useMemo(
    () => (state.ui.currentTheme === 'dark' ? 'vs-dark' : 'vs'),
    [state.ui.currentTheme],
  );

  const { state: treeState, editor, handleFileSelect, handleFileDoubleClick, loadTree } = manager;

  useLayoutEffect(() => {
    const nodes = treeState.nodes;
    const flattened = flattenFileTree(nodes as Parameters<typeof flattenFileTree>[0]);
    onTreeUpdate?.(nodes, flattened.length);

    nodes
      .filter(node => node.type === 'directory')
      .forEach(node => treeState.expandNode(node.path));

    const activePath = editor.activeTab?.path;
    const activeNode = activePath ? findNodeByPath(nodes, activePath) : null;

    if (activeNode?.type === 'file') {
      return;
    }

    const firstFile = getAllFileNodes(nodes)[0];
    if (firstFile) {
      void handleFileSelect(firstFile);
    }
  }, [editor.activeTab?.path, handleFileSelect, onTreeUpdate, treeState.expandNode, treeState.nodes]);

  const handleNodeClick = useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    treeState.selectNodeWithModifier(node.path, modifier);

    if (node.type === 'file' && modifier === 'none') {
      void handleFileSelect(node);
    }
  }, [handleFileSelect, treeState]);

  const handleNodeDoubleClick = useCallback((node: FileTreeNode) => {
    void handleFileDoubleClick(node);
  }, [handleFileDoubleClick]);

  const handleContextMenu = useCallback((node: FileTreeNode, event: React.MouseEvent) => {
    treeState.openContextMenu(event.clientX, event.clientY, node);
  }, [treeState]);

  const handleCopyPath = useCallback((path: string) => {
    void navigator.clipboard?.writeText(path).catch((error) => {
      logger.error('複製 template 檔案路徑失敗', { error, path });
    });
  }, []);

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

  const renderReadOnlyEditor = useCallback((tab: {
    name: string;
    path: string;
    content: string;
  }) => {
    if (isImageFile(tab.name)) {
      return (
        <div className="flex h-full flex-col bg-background">
          <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
            <span>{tab.path}</span>
            <span className="inline-flex items-center gap-1">
              <Lock className="h-3.5 w-3.5" />
              {t('template.detail.fileViewer.viewerNotice')}
            </span>
          </div>
          <div className="flex flex-1 items-center justify-center overflow-auto bg-muted/10 p-6">
            <img
              src={getTemplateFileContentUrl(templateId, basePath, tab.path)}
              alt={tab.name}
              className="max-h-full max-w-full rounded border border-border bg-background shadow-sm"
            />
          </div>
        </div>
      );
    }

    if (isMarkdownFile(tab.name)) {
      return (
        <div className="flex h-full flex-col bg-background">
          <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
            <span>{tab.path}</span>
            <span className="inline-flex items-center gap-1">
              <Lock className="h-3.5 w-3.5" />
              {t('template.detail.fileViewer.viewerNotice')}
            </span>
          </div>
          <div className="flex-1 overflow-auto">
            <MarkdownContent content={tab.content} variant="detailed" className="px-6 py-4" />
          </div>
        </div>
      );
    }

    return (
      <div className="flex h-full flex-col bg-background">
        <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
          <span>{tab.path}</span>
          <span className="inline-flex items-center gap-1">
            <Lock className="h-3.5 w-3.5" />
            {t('template.detail.fileViewer.viewerNotice')}
          </span>
        </div>
        <div className="relative flex-1 overflow-hidden">
          <Editor
            height="100%"
            language={getLanguageFromFileName(tab.name)}
            value={tab.content}
            theme={currentTheme}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 14,
              wordWrap: 'on',
              automaticLayout: true,
              scrollBeyondLastLine: false,
              fontFamily: 'var(--font-mono)',
            }}
          />
          {!tab.content && (
            <div className="pointer-events-none absolute inset-x-0 top-0 p-6 text-sm text-muted-foreground">
              {t('template.detail.fileViewer.emptyFile')}
            </div>
          )}
        </div>
      </div>
    );
  }, [basePath, currentTheme, t, templateId]);

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
            <FileEditorPanel
              editor={editor}
              renderEditor={renderReadOnlyEditor}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default TemplateDetailFileViewer;
