import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { useApp } from '@/app/providers/AppProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { apiClient } from '@/shared/api/apiClient';
import { flattenFileTree } from '@/features/template-management/utils/templateFiles';
import { Search, Loader2, File as FileIcon, Folder as FolderIcon } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import Editor, { OnMount } from '@monaco-editor/react';
import { TreeView, TreeViewRenderProps } from '@/shared/components/tree/TreeView';
import { TreeNodeRow } from '@/shared/components/tree';
import { getFileIcon } from '@/features/workspace/features/file-management/utils/fileIconUtils';
import { getLanguageFromFileName } from '@/shared/utils/languageUtils';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('TemplateDetailFileViewer');

interface FileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
  content?: string;
}

interface TemplateDetailFileViewerProps {
  templateId: string;
  basePath: string;
  title: string;
  onTreeUpdate?: (nodes: FileNode[], flattenedCount: number) => void;
}

const isMarkdownFile = (filename: string) => filename.toLowerCase().endsWith('.md');



export const TemplateDetailFileViewer: React.FC<TemplateDetailFileViewerProps> = ({
  templateId,
  basePath,
  title,
  onTreeUpdate,
}) => {
  const { t } = useI18n();
  const { state } = useApp();
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [isLoadingTree, setIsLoadingTree] = useState(true);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [isLoadingContent, setIsLoadingContent] = useState(false);
  const treeUpdateRef = useRef(onTreeUpdate);
  const selectedPathRef = useRef<string | null>(null);
  const editorRef = useRef<any>(null);

  // 確定主題 - 使用 AppProvider 的 currentTheme
  const currentTheme = useMemo(() => {
    return state.ui.currentTheme === 'dark' ? 'vs-dark' : 'vs';
  }, [state.ui.currentTheme]);

  useEffect(() => {
    treeUpdateRef.current = onTreeUpdate;
  }, [onTreeUpdate]);

  useEffect(() => {
    selectedPathRef.current = selectedFile?.path ?? null;
  }, [selectedFile]);

  const normalizedSearch = useMemo(() => searchQuery.trim().toLowerCase(), [searchQuery]);
  const isSearching = normalizedSearch.length > 0;

  const filterTree = useCallback(
    (nodes: FileNode[]): FileNode[] => {
      if (!isSearching) {
        return nodes;
      }

      const filterRecursive = (list: FileNode[]): FileNode[] => {
        const result: FileNode[] = [];
        list.forEach(node => {
          const matches = node.name.toLowerCase().includes(normalizedSearch);
          const filteredChildren = node.children ? filterRecursive(node.children) : undefined;
          if (matches || (filteredChildren && filteredChildren.length > 0)) {
            result.push({
              ...node,
              children: filteredChildren,
            });
          }
        });
        return result;
      };

      return filterRecursive(nodes);
    },
    [isSearching, normalizedSearch],
  );

  const filteredTree = useMemo(() => filterTree(fileTree), [fileTree, filterTree]);

  const loadTree = useCallback(async () => {
    if (!templateId) return;
    setIsLoadingTree(true);
    setTreeError(null);
    try {
      const response = await apiClient.get<{ path: string; scope: string; nodes: FileNode[]; total: number }>(
        `/templates/${templateId}/files/tree?scope=${basePath}&path=/&max_depth=10`,
      );
      const nodes = response.nodes || [];
      setFileTree(nodes);
      const callback = treeUpdateRef.current;
      if (callback) {
        const flattened = flattenFileTree(nodes);
        callback(nodes, flattened.length);
      }
      setFileContent('');
      // Expand root level directories by default
      const initialExpanded = new Set<string>();
      nodes
        .filter(node => node.type === 'directory')
        .forEach(node => initialExpanded.add(node.path));
      setExpanded(initialExpanded);
      const findNode = (list: FileNode[], targetPath: string): FileNode | null => {
        for (const node of list) {
          if (node.path === targetPath) return node;
          if (node.children) {
            const found = findNode(node.children, targetPath);
            if (found) return found;
          }
        }
        return null;
      };
      let targetNode: FileNode | null = null;
      if (selectedPathRef.current) {
        targetNode = findNode(nodes, selectedPathRef.current);
      }
      if (!targetNode) {
        const firstFile = flattenFileTree(nodes).find(entry => entry.path);
        if (firstFile) {
          targetNode = findNode(nodes, firstFile.path) ?? null;
        }
      }
      if (targetNode) {
        setSelectedFile(targetNode);
      } else {
        setSelectedFile(null);
      }
    } catch (error) {
      logger.error('Failed to load file tree', { error });
      setTreeError(t('template.detail.fileViewer.errors.loadTree'));
    } finally {
      setIsLoadingTree(false);
    }
  }, [templateId, basePath, t]);

  const loadFileContent = useCallback(
    async (node: FileNode) => {
      if (!templateId || node.type !== 'file') return;
      setIsLoadingContent(true);
      try {
        const response = await apiClient.get<{ path: string; scope: string; content: string; size: number; updatedAt: string }>(
          `/templates/${templateId}/files/content?path=${encodeURIComponent(node.path)}&scope=${basePath}`,
        );
        setFileContent(response.content || '');
      } catch (error) {
        logger.error('Failed to load file content', { error });
        setFileContent('');
      } finally {
        setIsLoadingContent(false);
      }
    },
    [templateId, basePath],
  );

  useEffect(() => {
    loadTree();
  }, [loadTree]);

  useEffect(() => {
    if (selectedFile && selectedFile.type === 'file') {
      loadFileContent(selectedFile);
    }
  }, [selectedFile, loadFileContent]);

  const handleToggleExpand = useCallback((node: FileNode) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(node.path)) {
        next.delete(node.path);
      } else {
        next.add(node.path);
      }
      return next;
    });
  }, []);

  const handleSelectNode = useCallback((node: FileNode) => {
    if (node.type === 'file') {
      setFileContent('');
      setSelectedFile(node);
    }
  }, []);

  const renderTreeNode = useCallback(
    ({ node, depth, isLeaf, state, handlers }: TreeViewRenderProps<FileNode>) => {
      return (
        <TreeNodeRow
          depth={depth}
          isSelected={state.isSelected}
          isMultiSelected={false}
          isExpanded={state.isExpanded}
          showExpandIcon={!isLeaf}
          icon={
            !isLeaf
              ? getFileIcon(node.name, true, state.isExpanded)
              : getFileIcon(node.name, false, false)
          }
          label={<span className="text-sm truncate">{node.name}</span>}
          className="text-foreground hover:bg-muted/50"
          onClick={() => {
            if (isLeaf) {
              handlers.select();
            } else {
              handlers.toggleExpand();
            }
          }}
          onExpandToggle={() => {
            if (!isLeaf) {
              handlers.toggleExpand();
            }
          }}
        />
      );
    },
    [],
  );

  const flattenedFilesCount = useMemo(() => flattenFileTree(fileTree).length, [fileTree]);

  const handleEditorDidMount: OnMount = (editor) => {
    try {
      editorRef.current = editor;
    } catch (error) {
      logger.error('Monaco Editor 初始化失敗', { error });
    }
  };

  return (
    <div className="flex h-full border border-border rounded-lg overflow-hidden">
      <div className="w-80 border-r border-border bg-muted/20 flex flex-col">
        <div className="flex h-10 items-center justify-between border-b border-border bg-muted/40 px-4">
          <div className="flex items-center gap-2">
            <FolderIcon className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium text-foreground">{title}</span>
            <Badge variant="secondary" className="px-2 text-[11px]">
              {flattenedFilesCount}
            </Badge>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={loadTree}
            disabled={isLoadingTree}
          >
            {isLoadingTree ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              t('template.detail.fileViewer.actions.refresh')
            )}
          </Button>
        </div>

        <div className="border-b border-border px-3 py-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={event => setSearchQuery(event.target.value)}
              placeholder={t('template.detail.fileViewer.searchPlaceholder')}
              className="h-7 pl-8 text-xs"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {isLoadingTree ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('template.detail.fileViewer.loading')}
            </div>
          ) : treeError ? (
            <div className="rounded border border-destructive/40 bg-destructive/5 px-3 py-4 text-sm text-destructive">
              {treeError}
            </div>
          ) : filteredTree.length === 0 ? (
            <div className="rounded border border-dashed border-border/60 px-4 py-8 text-center text-xs text-muted-foreground">
              {isSearching
                ? t('template.detail.fileViewer.emptySearch')
                : t('template.detail.fileViewer.empty')}
            </div>
          ) : (
            <TreeView
              nodes={filteredTree}
              expandedIds={isSearching ? null : expanded}
              selectedId={selectedFile?.path ?? null}
              expandAll={isSearching}
              getNodeId={(node) => node.path}
              getNodeChildren={(node) => node.children}
              renderNode={renderTreeNode}
              onToggleExpand={handleToggleExpand}
              onSelect={handleSelectNode}
            />
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col bg-background">
        {!selectedFile ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            {t('template.detail.fileViewer.noSelection')}
          </div>
        ) : (
          <>
            <div className="flex h-10 items-center border-b border-border px-4">
              <div className="flex items-center gap-2 min-w-0">
                <FileIcon className="h-4 w-4 text-muted-foreground" />
                <span className="truncate text-sm font-medium">{selectedFile.path}</span>
              </div>
              {isLoadingContent && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {t('template.detail.fileViewer.loadingContent')}
                </div>
              )}
            </div>
            <div className="flex-1 overflow-auto">
              {isMarkdownFile(selectedFile.name) ? (
                <MarkdownContent content={fileContent} variant="detailed" className="px-6 py-4" />
              ) : (
                <div className="h-full">
                  <Editor
                    height="100%"
                    language={getLanguageFromFileName(selectedFile.name)}
                    value={fileContent}
                    theme={currentTheme}
                    onMount={handleEditorDidMount}
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
                  {(!fileContent || fileContent.length === 0) && (
                    <div className="p-6 text-sm text-muted-foreground absolute top-10 left-0 pointer-events-none">
                      {t('template.detail.fileViewer.emptyFile')}
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default TemplateDetailFileViewer;

