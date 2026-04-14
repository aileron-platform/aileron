import React, { useMemo, useState } from 'react';
import { ColumnsLayout } from '@/shared/components/layout/ColumnsLayout';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';
import type { TemplateFileNode } from '@/shared/types/templates';
import { Search, Folder as FolderIcon, File as FileIcon, ChevronDown, ChevronRight, Eye, Copy, Download } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

interface FilesTabContentProps {
  files: TemplateFileNode[];
}

interface FlatFileEntry { path: string; content?: string }

const flattenFiles = (nodes: TemplateFileNode[]): FlatFileEntry[] => {
  const out: FlatFileEntry[] = [];
  const walk = (n: TemplateFileNode, prefix: string) => {
    const next = prefix ? `${prefix}/${n.name}` : n.name;
    if (n.type === 'file') out.push({ path: next, content: n.content });
    if (n.type === 'directory' && n.children) n.children.forEach(c => walk(c, next));
  };
  nodes.forEach(n => walk(n, ''));
  return out;
};

export const FilesTabContent: React.FC<FilesTabContentProps> = ({ files }) => {
  const { layout, setTriPrimaryOpen, setTriPrimaryWidth } = useTemplateManagementContext();

  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedPath, setSelectedPath] = useState<string | null>(() => {
    const first = flattenFiles(files)[0]?.path || null;
    return first;
  });
  const { t } = useI18n();

  const handleToggleDir = (path: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });
  };

  const filtered = useMemo(() => search.trim().toLowerCase(), [search]);

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (error) {
      logger.error(t('template.detail.files.errors.copyFailed'), { error });
    }
  };
  const handleDownload = (name: string, text: string) => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name || 'file.txt';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // 遞迴渲染樹狀清單
  const renderTree = (nodes: TemplateFileNode[], prefix: string) => {
    return nodes.map(node => {
      const nodePath = prefix ? `${prefix}/${node.name}` : node.name;
      const isMatch = !filtered || nodePath.toLowerCase().includes(filtered);
      if (!isMatch && node.type === 'file') return null;

      if (node.type === 'directory') {
        const isOpen = expanded.has(nodePath);
        const visibleChildren = node.children || [];
        // 若搜尋有值，強制顯示目錄（以便顯示符合的子孫）
        const showDir = filtered ? true : true;
        return (
          <div key={nodePath} className="select-none">
            <button
              type="button"
              onClick={() => handleToggleDir(nodePath)}
              className="w-full px-2 py-1 flex items-center gap-2 text-sm hover:bg-muted/40 rounded-sm"
            >
              {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <FolderIcon className="h-4 w-4 text-blue-500" />
              <span className="truncate">{node.name}</span>
            </button>
            {showDir && isOpen && (
              <div className="ml-4">
                {renderTree(visibleChildren, nodePath)}
              </div>
            )}
          </div>
        );
      }

      // file
      return (
        <button
          key={nodePath}
          type="button"
          onClick={() => setSelectedPath(nodePath)}
          className={`w-full px-2 py-1 flex items-center gap-2 text-sm rounded-sm hover:bg-muted/40 ${selectedPath === nodePath ? 'bg-primary/10 border border-primary/30' : ''}`}
        >
          <FileIcon className="h-4 w-4 text-gray-500" />
          <span className="truncate font-mono">{node.name}</span>
        </button>
      );
    });
  };

  const selectedFile = useMemo(() => {
    if (!selectedPath) return null;
    // 走訪找檔案
    const stack: Array<{ n: TemplateFileNode; p: string }> = [];
    files.forEach(n => stack.push({ n, p: '' }));
    while (stack.length) {
      const { n, p } = stack.pop()!;
      const path = p ? `${p}/${n.name}` : n.name;
      if (n.type === 'file' && path === selectedPath) return { name: n.name, path, content: n.content || '' };
      if (n.type === 'directory' && n.children) n.children.forEach(c => stack.push({ n: c, p: path }));
    }
    return null;
  }, [files, selectedPath]);

  const totalFiles = useMemo(() => flattenFiles(files).length, [files]);

  return (
    <ColumnsLayout
      primaryOpen={layout.triPrimaryOpen}
      onPrimaryOpenChange={setTriPrimaryOpen}
    >
      {/* 第二欄：樹狀選單 */}
      <ColumnsLayout.PrimarySidebar
        width={320}
        controlledWidth={layout.triPrimaryWidth}
        onWidthChange={setTriPrimaryWidth}
        className="flex h-full flex-col bg-background text-foreground border-r border-border"
      >
        <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-3">
          <div className="flex items-center gap-2">
            <FolderIcon className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{t('template.detail.files.sidebar.title')}</span>
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">{totalFiles}</Badge>
          </div>
        </div>
        <div className="space-y-3 border-b border-border bg-muted/30 p-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('template.detail.files.sidebar.searchPlaceholder')}
              className="h-8 pl-10 text-xs"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {files.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-xs text-muted-foreground">
              {t('template.detail.files.sidebar.empty')}
            </div>
          ) : (
            <div className="space-y-1">
              {renderTree(files, '')}
            </div>
          )}
        </div>
      </ColumnsLayout.PrimarySidebar>

      {/* 第三欄：檔案內容 */}
      <ColumnsLayout.Content className="bg-background">
        {selectedFile ? (
          <div className="h-full flex flex-col">
            <div className="sticky top-0 z-10 border-b border-border bg-background px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <FileIcon className="h-4 w-4 text-muted-foreground" />
                    <h3 className="truncate font-medium text-sm">{selectedFile.path}</h3>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => handleCopy(selectedFile.content)}>
                    <Copy className="h-3.5 w-3.5 mr-1" /> {t('template.detail.files.actions.copy')}
                  </Button>
                  <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => handleDownload(selectedFile.name, selectedFile.content)}>
                    <Download className="h-3.5 w-3.5 mr-1" /> {t('template.detail.files.actions.download')}
                  </Button>
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {selectedFile.content ? (
                <pre className="mt-2 p-3 bg-muted rounded text-xs overflow-x-auto whitespace-pre-wrap">{selectedFile.content}</pre>
              ) : (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <Eye className="h-8 w-8 mx-auto mb-2" />
                    <p className="text-sm">{t('template.detail.files.detail.noContent')}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <Eye className="h-8 w-8 mx-auto mb-2" />
              <p className="text-sm">{t('template.detail.files.detail.selectPrompt')}</p>
            </div>
          </div>
        )}
      </ColumnsLayout.Content>
    </ColumnsLayout>
  );
};

export default FilesTabContent;

