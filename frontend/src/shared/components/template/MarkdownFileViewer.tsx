import React, { useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { Button } from '@/shared/components/ui/button';

const logger = createLogger('MarkdownFileViewer');
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  MoreHorizontal,
  Plus,
} from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

// 基礎項目接口
export interface BaseItem {
  id: string;
  fileName: string;
  description?: string;
  content: string;
}

// 操作按鈕配置
export interface ItemActions<T> {
  edit?: {
    onClick: (item: T) => void;
    label: string;
  };
  delete?: {
    onClick: (item: T) => void;
    label: string;
  };
}

// 組件屬性
export interface MarkdownFileViewerProps<T extends BaseItem> {
  items: T[];
  getItemIcon: () => React.ComponentType<{ className?: string }>;
  renderContent: (item: T) => React.ReactNode;
  getDownloadFileName: (item: T) => string;
  getDownloadFileType: (item: T) => string;
  actions?: ItemActions<T>;
  i18nKeys: {
    sidebar: {
      title: string;
      searchPlaceholder: string;
      empty: string;
    };
    list: {
      nameFallback: string;
      sizeLabel: string;
    };
    detail: {
      descriptionFallback: string;
    };
    actions: {
      copy: string;
      download: string;
      add?: string;
    };
    empty: {
      title: string;
      description: string;
    };
    errors: {
      copyFailed: string;
    };
  };
  topPanelExtra?: (item: T) => React.ReactNode;
  onAdd?: () => void;
  showAddButton?: boolean;
}

export function MarkdownFileViewer<T extends BaseItem>({
  items,
  getItemIcon,
  renderContent,
  getDownloadFileName,
  getDownloadFileType,
  actions,
  i18nKeys,
  topPanelExtra,
  onAdd,
  showAddButton = false,
}: MarkdownFileViewerProps<T>) {
  const { t } = useI18n();
  const [selectedId, setSelectedId] = useState<string | null>(items[0]?.id || null);
  const [search, setSearch] = useState('');

  // 過濾邏輯
  const filteredItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    return items.filter((item) => {
      return (
        query.length === 0 ||
        item.fileName.toLowerCase().includes(query) ||
        item.content.toLowerCase().includes(query)
      );
    });
  }, [items, search]);

  // 選中的項目
  const selectedItem = useMemo(
    () => filteredItems.find((item) => item.id === selectedId) ?? null,
    [filteredItems, selectedId],
  );

  // 導航邏輯
  const currentIndex = selectedItem ? filteredItems.findIndex((item) => item.id === selectedItem.id) : -1;
  const canNavigatePrevious = currentIndex > 0;
  const canNavigateNext = currentIndex >= 0 && currentIndex < filteredItems.length - 1;

  const navigateToPrevious = () => {
    if (canNavigatePrevious) {
      setSelectedId(filteredItems[currentIndex - 1].id);
    }
  };

  const navigateToNext = () => {
    if (canNavigateNext) {
      setSelectedId(filteredItems[currentIndex + 1].id);
    }
  };

  // 操作函數
  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
    } catch (error) {
      logger.error(t(i18nKeys.errors.copyFailed), { error });
    }
  };

  const handleDownload = (item: T) => {
    const fileName = getDownloadFileName(item);
    const fileType = getDownloadFileType(item);
    const blob = new Blob([item.content], { type: `text/${fileType}` });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName}.${fileType}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const Icon = getItemIcon();

  // 頂部面板組件
  const TopPanel = ({ item }: { item: T }) => (
    <div className="p-4 border-b border-border bg-background">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" />
            <h3 className="font-semibold text-foreground">
              {item.fileName || t(i18nKeys.list.nameFallback)}
            </h3>
          </div>
          <p className="text-sm text-muted-foreground">
            {item.description || t(i18nKeys.detail.descriptionFallback)}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={navigateToPrevious} disabled={!canNavigatePrevious}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={navigateToNext} disabled={!canNavigateNext}>
            <ChevronRight className="h-4 w-4" />
          </Button>

          {actions?.edit && (
            <Button variant="outline" size="sm" onClick={() => actions.edit!.onClick(item)}>
              {actions.edit.label}
            </Button>
          )}

          {actions?.delete && (
            <Button variant="outline" size="sm" onClick={() => actions.delete!.onClick(item)} className="text-destructive hover:text-destructive">
              {actions.delete.label}
            </Button>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleCopy(item.content)}>
                <Copy className="h-3 w-3 mr-2" />
                {t(i18nKeys.actions.copy)}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleDownload(item)}>
                <Download className="h-3 w-3 mr-2" />
                {t(i18nKeys.actions.download)}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-2">
        <Badge variant="outline" className="text-[11px]">
          {t(i18nKeys.list.sizeLabel, {
            size: t('common.markdownFileViewer.units.chars', { count: item.content.length }),
          })}
        </Badge>
        {topPanelExtra?.(item)}
      </div>
    </div>
  );

  // 主要內容
  const mainContent = selectedItem ? (
    <div className="flex flex-col h-full">
      <div className="sticky top-0 z-10 border-b border-border bg-background">
        <TopPanel item={selectedItem} />
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {renderContent(selectedItem)}
      </div>
    </div>
  ) : (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <Icon className="h-10 w-10 text-muted-foreground" />
      <div className="space-y-1">
        <p className="text-base font-medium text-muted-foreground">
          {t(i18nKeys.empty.title)}
        </p>
        <p className="text-sm text-muted-foreground">
          {t(i18nKeys.empty.description)}
        </p>
      </div>
      {showAddButton && onAdd && (
        <Button size="sm" onClick={onAdd}>
          <Plus className="mr-1 h-4 w-4" />
          {i18nKeys.actions.add && t(i18nKeys.actions.add)}
        </Button>
      )}
    </div>
  );

  return (
    <div className="flex h-full overflow-hidden">
      {/* 左側列表 */}
      <div className="w-80 flex-shrink-0">
        <div className="flex h-full flex-col bg-background text-foreground border-r border-border">
          <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-3">
            <div className="flex items-center gap-2">
              <Icon className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">{t(i18nKeys.sidebar.title)}</span>
            </div>
            {showAddButton && onAdd && (
              <Button variant="ghost" size="sm" onClick={onAdd}>
                <Plus className="h-4 w-4" />
              </Button>
            )}
          </div>

          <div className="space-y-3 border-b border-border bg-muted/30 p-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t(i18nKeys.sidebar.searchPlaceholder)}
                className="h-8 pl-10 text-xs"
              />
            </div>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {filteredItems.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-xs text-muted-foreground">
                {t(i18nKeys.sidebar.empty)}
              </div>
            ) : (
              filteredItems.map((item) => {
                const isActive = item.id === selectedId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                    className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                      isActive
                        ? 'border-primary/60 bg-primary/10 shadow-sm'
                        : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium">
                          {item.fileName || t(i18nKeys.list.nameFallback)}
                        </div>
                        <div className="truncate text-xs text-muted-foreground">
                          {item.description || t(i18nKeys.detail.descriptionFallback)}
                        </div>
                      </div>
                      <div className="text-[11px] text-muted-foreground text-right">
                        {t('common.markdownFileViewer.units.bytes', { count: item.content.length })}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* 右側內容 */}
      <div className="flex-1 bg-background">
        {mainContent}
      </div>
    </div>
  );
}

export default MarkdownFileViewer;
