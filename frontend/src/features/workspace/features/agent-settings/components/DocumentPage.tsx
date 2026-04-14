import React, { useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('DocumentPage');
import { Edit, ChevronLeft, ChevronRight, Copy, Download, MoreHorizontal, Trash2, Plus, RefreshCw, Puzzle, ChevronDown } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import type { ClaudeDocument } from '../../claude-code/types';
import { useI18n } from '@/shared/hooks/useI18n';
import { SCOPE_BADGE_CLASSES } from '../constants/scopeStyles';
import { CLAUDE_CODE_ICONS } from '../../../components/navigation-constants';

// 定義 Dialog 組件的共用介面
export interface DocumentDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: ClaudeDocument | null;
  onClose: () => void;
  onSubmit: (document: ClaudeDocument) => Promise<void> | void;
}

export interface DocumentPageConfig {
  metaKey: 'slash-commands' | 'output-styles' | 'subagents' | 'memory';
  contentFormat?: 'markdown' | 'toml';
  createButtonLabel: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
  dialogTitle: string;
  hideScopeBadge?: boolean;
}

export interface DocumentPageProps {
  documents: ClaudeDocument[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate: (document: ClaudeDocument) => Promise<ClaudeDocument>;
  onUpdate: (document: ClaudeDocument) => Promise<ClaudeDocument>;
  onDelete: (id: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => Promise<void>;
  dialogComponent: React.ComponentType<DocumentDialogProps>;
  config: DocumentPageConfig;
  i18nNamespace?: string;
}

// TOML 結構化卡片渲染
const TomlContentView: React.FC<{ content: string }> = ({ content }) => {
  const [rawExpanded, setRawExpanded] = useState(false);

  const parsed = useMemo(() => {
    try {
      // 簡易 TOML 解析：提取 description 和 prompt 欄位
      const descMatch = content.match(/^description\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMatch = content.match(/^prompt\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      // 也嘗試多行字串
      const promptMultiMatch = content.match(/^prompt\s*=\s*"""([\s\S]*?)"""/m);

      const description = descMatch ? descMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null;
      let prompt = promptMultiMatch ? promptMultiMatch[1] : (promptMatch ? promptMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null);

      return { description, prompt };
    } catch {
      return { description: null, prompt: null };
    }
  }, [content]);

  return (
    <div className="space-y-4">
      {parsed.description && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">Description</h4>
          <p className="text-sm text-foreground">{parsed.description}</p>
        </div>
      )}

      {parsed.prompt && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">Prompt</h4>
          <MarkdownContent content={parsed.prompt} />
        </div>
      )}

      <div className="rounded-lg border border-border">
        <button
          type="button"
          className="flex w-full items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted/50"
          onClick={() => setRawExpanded(!rawExpanded)}
        >
          <ChevronDown className={`h-4 w-4 transition-transform ${rawExpanded ? 'rotate-0' : '-rotate-90'}`} />
          Raw TOML
        </button>
        {rawExpanded && (
          <div className="border-t border-border p-4">
            <pre className="whitespace-pre-wrap text-xs font-mono text-foreground">{content}</pre>
          </div>
        )}
      </div>
    </div>
  );
};

export const DocumentPage: React.FC<DocumentPageProps> = ({
  documents,
  selectedId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
  isLoading = false,
  error = null,
  onRefresh,
  dialogComponent: DialogComponent,
  config,
  i18nNamespace = 'workspace.claudeCode',
}) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [activeDocument, setActiveDocument] = useState<ClaudeDocument | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const { t } = useI18n();

  // 根據 config.metaKey 動態選擇 icon
  const Icon = useMemo(() => {
    switch (config.metaKey) {
      case 'slash-commands':
        return CLAUDE_CODE_ICONS['slash-commands'];
      case 'output-styles':
        return CLAUDE_CODE_ICONS['output-styles'];
      case 'subagents':
        return CLAUDE_CODE_ICONS['subagents'];
      case 'memory':
        return CLAUDE_CODE_ICONS['memory'];
      default:
        return CLAUDE_CODE_ICONS['slash-commands'];
    }
  }, [config.metaKey]);

  const metaLabelKey = `${i18nNamespace}.documents.meta.${config.metaKey}.title`;
  const translatedMetaLabel = t(metaLabelKey);
  const metaLabel = translatedMetaLabel === metaLabelKey ? config.dialogTitle : translatedMetaLabel;

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedId) ?? null,
    [documents, selectedId],
  );

  // 權限檢查函數
  const canEdit = (document: ClaudeDocument | null): boolean => {
    return document?.scope !== 'plugin';
  };

  const canDelete = (document: ClaudeDocument | null): boolean => {
    return document?.scope !== 'plugin';
  };

  // 複製內容到剪貼板
  const handleCopyContent = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      // TODO: 添加成功提示
    } catch (err) {
      logger.error('無法複製到剪貼板', { error: err });
      // TODO: 添加錯誤提示
    }
  };

  const handleEditDocument = () => {
    if (!selectedDocument) return;
    if (!canEdit(selectedDocument)) {
      // Plugin documents 無法編輯
      return;
    }
    setDialogMode('edit');
    setActiveDocument(selectedDocument);
    setDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!selectedDocument) return;
    if (!canDelete(selectedDocument)) {
      // Plugin documents 無法刪除
      return;
    }

    const confirmed = window.confirm(
      t(`${i18nNamespace}.documents.confirmDelete`, { title: selectedDocument.title }),
    );
    if (!confirmed) return;
    try {
      setIsProcessing(true);
      await onDelete(selectedDocument.id);
      const nextDocuments = documents.filter((doc) => doc.id !== selectedDocument.id);
      if (nextDocuments.length > 0) {
        onSelect(nextDocuments[0].id);
      } else {
        onSelect(null);
      }
    } catch (error) {
      logger.error('刪除文件失敗', { error });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = () => {
    if (!selectedDocument) return;

    const blob = new Blob([selectedDocument.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedDocument.title}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    // TODO: 添加下載成功提示
  };

  const handleCreateRequest = () => {
    setDialogMode('create');
    setActiveDocument(null);
    setDialogOpen(true);
  };

  const handleRefresh = async () => {
    if (!onRefresh) return;
    try {
      setIsProcessing(true);
      await onRefresh();
    } catch (error) {
      logger.error('重新整理文件列表失敗', { error });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDialogSubmit = async (document: ClaudeDocument) => {
    try {
      setIsProcessing(true);
      if (dialogMode === 'create') {
        const created = await onCreate(document);
        onSelect(created?.id ?? document.id);
      } else {
        const updated = await onUpdate(document);
        onSelect(updated?.id ?? document.id);
      }
      setDialogOpen(false);
      setActiveDocument(null);
    } catch (error) {
      logger.error('儲存文件失敗', { error });
    } finally {
      setIsProcessing(false);
    }
  };

  // 導航功能
  const currentIndex = selectedDocument ? documents.findIndex((doc) => doc.id === selectedDocument.id) : -1;
  const canNavigatePrevious = currentIndex > 0;
  const canNavigateNext = currentIndex >= 0 && currentIndex < documents.length - 1;

  const navigateToPrevious = () => {
    if (canNavigatePrevious) {
      onSelect(documents[currentIndex - 1].id);
    }
  };

  const navigateToNext = () => {
    if (canNavigateNext) {
      onSelect(documents[currentIndex + 1].id);
    }
  };

  const totalCount = documents.length;

  const mainContent = selectedDocument ? (
    <div className="flex flex-col h-full">
      <FeatureHeader
        title={metaLabel}
        icon={Icon}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-[11px]">
              {t(`${i18nNamespace}.documents.stats.total`, { count: totalCount })}
            </Badge>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={handleRefresh}
              disabled={isProcessing || isLoading || !onRefresh}
            >
              <RefreshCw className="mr-1 h-3 w-3" /> {t(`${i18nNamespace}.documents.actions.refresh`)}
            </Button>
            <Button size="sm" className="h-7 px-2 text-xs" onClick={handleCreateRequest} disabled={isProcessing}>
              <Plus className="mr-1 h-3 w-3" /> {config.createButtonLabel}
            </Button>
          </div>
        }
      />

      {/* Document Header */}
      <div className="px-4 py-3 border-b border-border bg-background">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Icon className="h-5 w-5 text-primary dark:text-primary" />
              <h3 className="font-semibold text-foreground">{selectedDocument.title}</h3>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              onClick={navigateToPrevious}
              disabled={!canNavigatePrevious || isProcessing}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              onClick={navigateToNext}
              disabled={!canNavigateNext || isProcessing}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-7 px-2">
                  <MoreHorizontal className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={handleEditDocument}
                disabled={isProcessing || !canEdit(selectedDocument)}
              >
                <Edit className="h-3 w-3 mr-2" />
                {t(`${i18nNamespace}.documents.actions.edit`)}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleCopyContent(selectedDocument.content)}
                disabled={isProcessing}
              >
                <Copy className="h-3 w-3 mr-2" />
                {t(`${i18nNamespace}.documents.actions.copyContent`)}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDownload} disabled={isProcessing}>
                <Download className="h-3 w-3 mr-2" />
                {t(`${i18nNamespace}.documents.actions.download`)}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={handleDelete}
                className="text-destructive"
                disabled={isProcessing || !canDelete(selectedDocument)}
              >
                <Trash2 className="h-3 w-3 mr-2" />
                {t(`${i18nNamespace}.documents.actions.delete`)}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* 範圍和大小資訊 */}
      <div className="flex items-center gap-2 mt-1.5">
        {!config.hideScopeBadge && (
          <Badge variant="outline" className={`text-[11px] ${SCOPE_BADGE_CLASSES[selectedDocument.scope]}`}>
            {t(`${i18nNamespace}.documents.scope.values.${selectedDocument.scope}`, { defaultValue: selectedDocument.scope })}
          </Badge>
        )}
        {selectedDocument.size && (
          <Badge variant="outline" className="text-[11px]">
            {t(`${i18nNamespace}.documents.size.badge`, { size: selectedDocument.size })}
          </Badge>
        )}
        {/* Plugin 來源標記 */}
        {selectedDocument.scope === 'plugin' && selectedDocument.pluginName && (
          <Badge variant="outline" className="flex items-center gap-1 text-[11px]">
            <Puzzle className="h-3 w-3" />
            {selectedDocument.pluginName}@{selectedDocument.marketplaceName}
          </Badge>
        )}
      </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {(config.contentFormat ?? (selectedDocument?.metadata?.format as string)) === 'toml' ? (
          <TomlContentView content={selectedDocument?.content || ''} />
        ) : (
          <MarkdownContent content={selectedDocument?.content || ''} />
        )}
      </div>
    </div>
  ) : (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={metaLabel}
        icon={Icon}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-[11px]">
              {t(`${i18nNamespace}.documents.stats.total`, { count: totalCount })}
            </Badge>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={handleRefresh}
              disabled={isProcessing || isLoading || !onRefresh}
            >
              <RefreshCw className="mr-1 h-3 w-3" /> {t(`${i18nNamespace}.documents.actions.refresh`)}
            </Button>
            <Button size="sm" className="h-7 px-2 text-xs" onClick={handleCreateRequest} disabled={isProcessing}>
              <Plus className="mr-1 h-3 w-3" /> {config.createButtonLabel}
            </Button>
          </div>
        }
      />

      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <Icon className="h-10 w-10 text-muted-foreground" />
        <div className="space-y-1">
          <p className="text-base font-medium text-muted-foreground">{config.emptyStateTitle}</p>
          <p className="text-sm text-muted-foreground">{config.emptyStateDescription}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={handleCreateRequest} disabled={isProcessing}>
            <Plus className="mr-1 h-4 w-4" /> {config.createButtonLabel}
          </Button>
          {onRefresh && (
            <Button size="sm" variant="ghost" onClick={handleRefresh} disabled={isProcessing || isLoading}>
              <RefreshCw className="mr-1 h-4 w-4" /> {t(`${i18nNamespace}.documents.actions.refresh`)}
            </Button>
          )}
        </div>
      </div>
    </div>
  );

  const renderEmptyState = () => (
    <div className="flex h-full flex-col items-center justify-center gap-3 border border-dashed border-border p-8 text-center">
      <div className="rounded-full bg-muted p-3">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="text-base font-medium text-foreground">{config.emptyStateTitle}</h3>
      <p className="text-sm text-muted-foreground">{config.emptyStateDescription}</p>
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={handleCreateRequest} disabled={isProcessing}>
          <Plus className="mr-1 h-4 w-4" /> {config.createButtonLabel}
        </Button>
        {onRefresh && (
          <Button size="sm" variant="ghost" onClick={handleRefresh} disabled={isProcessing || isLoading}>
            <RefreshCw className="mr-1 h-4 w-4" /> {t(`${i18nNamespace}.documents.actions.refresh`)}
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex h-full flex-col gap-0 overflow-hidden">
      {error && (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {error}
        </div>
      )}
      <div className="flex-1 overflow-hidden">
        {isLoading && documents.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t(`${i18nNamespace}.documents.loading`)}
          </div>
        ) : documents.length === 0 ? (
          renderEmptyState()
        ) : (
          mainContent
        )}
      </div>

      <DialogComponent
        open={dialogOpen}
        mode={dialogMode}
        initialValue={activeDocument}
        onClose={() => {
          setDialogOpen(false);
          setActiveDocument(null);
        }}
        onSubmit={handleDialogSubmit}
      />
    </div>
  );
};

DocumentPage.displayName = 'DocumentPage';

// 向下相容舊名稱
export { DocumentPage as ClaudeDocumentPage };

export default DocumentPage;
