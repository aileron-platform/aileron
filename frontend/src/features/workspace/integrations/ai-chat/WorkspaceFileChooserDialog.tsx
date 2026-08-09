import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Dialog, DialogContent, DialogHeader } from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { ChevronDown, ChevronRight, File, Folder, RefreshCw, Search } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useWorkspace } from '../../providers/WorkspaceContext';
import type { FileNode } from '../../features/file-management/model/fileManagementTypes';
import type { AiChatFileChooserProps } from '@/features/ai-chat/public';

type FilterPresetKey =
  | 'markdown'
  | 'testMarkdown'
  | 'typescript'
  | 'react'
  | 'javascript'
  | 'json'
  | 'css'
  | 'all';

interface FilterPreset {
  key: FilterPresetKey;
  pattern: string;
}

const FILTER_PRESETS: FilterPreset[] = [
  { key: 'markdown', pattern: '*.md' },
  { key: 'testMarkdown', pattern: '*-test.md' },
  { key: 'typescript', pattern: '*.ts' },
  { key: 'react', pattern: '*.tsx' },
  { key: 'javascript', pattern: '*.js' },
  { key: 'json', pattern: '*.json' },
  { key: 'css', pattern: '*.css' },
  { key: 'all', pattern: '*' },
];

const getInitialExpandedNodes = (nodes: FileNode[]): Set<string> => {
  const expanded = new Set<string>();
  nodes.forEach(node => {
    if (node.type === 'directory' && node.depth === 0) {
      expanded.add(node.path);
    }
  });
  return expanded;
};

export const WorkspaceFileChooserDialog: React.FC<AiChatFileChooserProps> = ({
  open,
  onOpenChange,
  onFileSelect,
  t,
}) => {
  const { fileTreeState, fileTreeActions } = useWorkspace();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<FilterPresetKey>('all');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);

  const activePattern = useMemo(() => {
    return FILTER_PRESETS.find(preset => preset.key === selectedFilter)?.pattern ?? '*';
  }, [selectedFilter]);

  const refreshFileTreeRef = useRef(fileTreeActions.refreshFileTree);
  refreshFileTreeRef.current = fileTreeActions.refreshFileTree;

  useEffect(() => {
    if (!open) {
      hasLoadedRef.current = false;
      return;
    }
    if (!hasLoadedRef.current) {
      hasLoadedRef.current = true;
      void refreshFileTreeRef.current();
    }
  }, [open]);

  useEffect(() => {
    if (open) {
      setExpandedNodes(prev => {
        if (prev.size > 0) {
          return prev;
        }
        return getInitialExpandedNodes(fileTreeState.nodes);
      });
    } else {
      setSearchTerm('');
      setSelectedFilter('all');
      setSelectedFilePath(null);
      setExpandedNodes(new Set());
    }
  }, [fileTreeState.nodes, open]);

  const toggleNode = useCallback(async (nodeId: string, node: FileNode) => {
    const isExpanded = expandedNodes.has(nodeId);

    if (isExpanded) {
      setExpandedNodes((prev) => {
        const newSet = new Set(prev);
        newSet.delete(nodeId);
        return newSet;
      });
    } else {
      if (node.type === 'directory' && (!node.children || node.children.length === 0) && node.hasChildren) {
        await fileTreeActions.expandNode(nodeId);
      }
      setExpandedNodes((prev) => {
        const newSet = new Set(prev);
        newSet.add(nodeId);
        return newSet;
      });
    }
  }, [expandedNodes, fileTreeActions]);

  const matchesFilter = (fileName: string, pattern: string): boolean => {
    if (pattern === '*') {
      return true;
    }

    const regexPattern = pattern
      .replace(/\./g, '\\.')
      .replace(/\*/g, '.*')
      .replace(/\?/g, '.');

    const regex = new RegExp(`^${regexPattern}$`, 'i');
    return regex.test(fileName);
  };

  const matchesSearch = (fileName: string, term: string): boolean => {
    if (!term) {
      return true;
    }
    return fileName.toLowerCase().includes(term.toLowerCase());
  };

  const filterFileTree = useCallback(
    (nodes: FileNode[]): FileNode[] => {
      return nodes.reduce<FileNode[]>((filtered, node) => {
        if (node.type === 'directory') {
          const children = node.children ? filterFileTree(node.children) : [];
          if (children.length > 0 || matchesSearch(node.name, searchTerm)) {
            filtered.push({
              ...node,
              children,
            });
          }
        } else if (matchesFilter(node.name, activePattern) && matchesSearch(node.name, searchTerm)) {
          filtered.push(node);
        }
        return filtered;
      }, []);
    },
    [activePattern, searchTerm]
  );

  const filteredTree = useMemo(() => filterFileTree(fileTreeState.nodes), [fileTreeState.nodes, filterFileTree]);

  const countFiles = useCallback((node: FileNode): number => {
    if (node.type === 'file') {
      return 1;
    }
    return node.children ? node.children.reduce((total, child) => total + countFiles(child), 0) : 0;
  }, []);

  const totalFiles = useMemo(() => {
    return filteredTree.reduce((total, node) => total + countFiles(node), 0);
  }, [countFiles, filteredTree]);

  const formatSize = (size?: number) => {
    if (!size) {
      return '';
    }
    if (size >= 1024) {
      return `${(size / 1024).toFixed(1)}KB`;
    }
    return `${size}B`;
  };

  const renderFileNode = (node: FileNode): React.ReactNode => {
    const hasChildren = Boolean(node.children && node.children.length > 0) || node.hasChildren;
    const nodeKey = node.path;
    const isExpanded = expandedNodes.has(nodeKey);
    const paddingLeft = node.depth * 16 + 8;

    return (
      <div key={nodeKey}>
        <div
          className={cn(
            'flex items-center rounded-sm px-2 py-1 text-sm transition-colors',
            node.type === 'file'
              ? 'hover:bg-muted/60 cursor-pointer'
              : hasChildren
                ? 'hover:bg-muted/40 cursor-pointer'
                : 'cursor-default',
            node.type === 'file' && selectedFilePath === node.path && 'bg-primary/10 text-primary'
          )}
          style={{ paddingLeft }}
          onClick={() => {
            if (node.type === 'directory') {
              if (hasChildren) {
                void toggleNode(nodeKey, node);
              }
              return;
            }
            setSelectedFilePath(node.path);
            onFileSelect(node.path);
            onOpenChange(false);
          }}
        >
          {node.type === 'directory' && (
            <div className="mr-1 flex h-4 w-4 items-center justify-center">
              {node.isLoading ? (
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              ) : (
                hasChildren && (isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)
              )}
            </div>
          )}
          {node.type === 'directory' ? (
            <Folder className="mr-2 h-4 w-4 text-blue-500" />
          ) : (
            <File className="mr-2 h-4 w-4 text-muted-foreground" />
          )}
          <span className="flex-1 truncate">{node.name}</span>
          {node.type === 'file' && <span className="ml-2 text-xs text-muted-foreground">{formatSize(node.size)}</span>}
        </div>
        {node.type === 'directory' && node.children && node.children.length > 0 && isExpanded && (
          <div>{node.children.map((child) => renderFileNode(child))}</div>
        )}
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="z-[100] flex h-[80vh] max-w-4xl flex-col p-0">
        <DialogHeader className="border-b px-6 py-4">
          <div className="flex items-center justify-between pr-8">
            <DialogHeading icon={Folder}>
              {t('workspace.chat.dialogs.fileChooser.title')}
            </DialogHeading>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void fileTreeActions.refreshFileTree()}
              disabled={fileTreeState.isLoading}
              className="gap-1.5"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', fileTreeState.isLoading && 'animate-spin')} />
              {t('workspace.fileManagement.tree.actions.refresh.tooltip')}
            </Button>
          </div>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col">
          <div className="space-y-3 border-b px-6 py-3">
            <div className="rounded bg-muted/30 p-2 text-xs text-muted-foreground">
              {t('workspace.chat.dialogs.fileChooser.projectPathLabel', { path: '/workspace' })}
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">
                {t('workspace.chat.dialogs.fileChooser.quickFilterTitle')}
              </div>
              <div className="flex flex-wrap gap-2">
                {FILTER_PRESETS.map(preset => {
                  const isActive = selectedFilter === preset.key;
                  return (
                    <Badge
                      key={preset.key}
                      variant={isActive ? 'default' : 'secondary'}
                      className="cursor-pointer hover:bg-primary/80"
                      onClick={() => setSelectedFilter(preset.key)}
                    >
                      {t(`workspace.chat.dialogs.fileChooser.filterPresets.${preset.key}.label`)}
                    </Badge>
                  );
                })}
              </div>
              {selectedFilter !== 'all' && (
                <div className="text-xs text-muted-foreground">
                  {t('workspace.chat.dialogs.fileChooser.currentFilter', {
                    description: t(`workspace.chat.dialogs.fileChooser.filterPresets.${selectedFilter}.description`),
                  })}
                </div>
              )}
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('workspace.chat.dialogs.fileChooser.searchPlaceholder')}
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          <div className="min-h-0 flex-1 px-6 py-3">
            <ScrollArea className="h-full">
              <div className="pr-4">
                {fileTreeState.error && (
                  <div className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                    {fileTreeState.error}
                  </div>
                )}
                {fileTreeState.isLoading ? (
                  <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                    {t('common.loading')}
                  </div>
                ) : filteredTree.length === 0 ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="text-sm text-muted-foreground">
                      {searchTerm || selectedFilter !== 'all'
                        ? t('workspace.chat.dialogs.fileChooser.noMatches')
                        : t('workspace.chat.dialogs.fileChooser.noFiles')}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">{filteredTree.map(node => renderFileNode(node))}</div>
                )}
              </div>
            </ScrollArea>
          </div>

          <div className="border-t bg-background px-6 py-3">
            <div className="flex items-center justify-between">
              <div className="text-xs text-muted-foreground">
                {totalFiles > 0 && t('workspace.chat.dialogs.fileChooser.foundCount', { count: totalFiles })}
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
