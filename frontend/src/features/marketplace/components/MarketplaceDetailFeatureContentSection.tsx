import React from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  MoreHorizontal,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type { MarketplaceFeatureContentItem } from '@/shared/types/marketplace';
import { MarketplaceSectionSidebarShell } from './MarketplaceSectionSidebarShell';
import { downloadBlob } from '../utils/downloadBlob';

const MARKETPLACE_DETAIL_SIDEBAR_DEFAULT_WIDTH = 320;
const MARKETPLACE_DETAIL_SIDEBAR_MIN_WIDTH = 240;
const MARKETPLACE_DETAIL_SIDEBAR_MAX_WIDTH = 520;
const MARKETPLACE_DETAIL_SIDEBAR_COLLAPSED_WIDTH = 44;

export interface MarketplaceDetailFeatureContentItem<TItem extends MarketplaceFeatureContentItem = MarketplaceFeatureContentItem> extends MarketplaceFeatureContentItem {
  source: TItem;
  fileName: string;
  content: string;
}

interface MarketplaceDetailFeatureContentSectionProps<TItem extends MarketplaceFeatureContentItem> {
  title: string;
  items: TItem[];
  icon: React.ComponentType<{ className?: string }>;
  emptyLabel: string;
  getFileName?: (item: TItem) => string;
  getContent?: (item: TItem) => string;
  renderItem?: (item: MarketplaceDetailFeatureContentItem<TItem>) => React.ReactNode;
}

const resolveI18nText = (
  t: (key: string, params?: Record<string, unknown>) => string,
  key: string,
  fallbackKey: string,
) => {
  const value = t(key);
  return value === key ? t(fallbackKey) : value;
};

const defaultFileName = (item: MarketplaceFeatureContentItem, extension = 'md') =>
  item.path?.split('/').pop() ?? `${item.id}.${extension}`;

const defaultContent = (item: MarketplaceFeatureContentItem) =>
  item.content ?? `# ${item.name}\n\n${item.description ?? ''}`;

export const MarketplaceDetailFeatureContentSection = <TItem extends MarketplaceFeatureContentItem>({
  title,
  items,
  icon: Icon,
  emptyLabel,
  getFileName = defaultFileName,
  getContent = defaultContent,
  renderItem,
}: MarketplaceDetailFeatureContentSectionProps<TItem>) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [selectedId, setSelectedId] = React.useState(items[0]?.id ?? '');
  const [searchTerm, setSearchTerm] = React.useState('');
  const [sidebarWidth, setSidebarWidth] = React.useState(MARKETPLACE_DETAIL_SIDEBAR_DEFAULT_WIDTH);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false);
  const [isSidebarResizing, setIsSidebarResizing] = React.useState(false);
  const sidebarResizeRef = React.useRef<{ startX: number; startWidth: number } | null>(null);

  const normalizedItems = React.useMemo(
    () => items.map(item => ({
      ...item,
      source: item,
      fileName: getFileName(item),
      content: getContent(item),
    })),
    [getContent, getFileName, items],
  );

  React.useEffect(() => {
    setSelectedId(normalizedItems[0]?.id ?? '');
    setSearchTerm('');
  }, [normalizedItems]);

  const filteredItems = React.useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) return normalizedItems;
    return normalizedItems.filter(item =>
      [item.name, item.description, item.path, item.content].filter(Boolean).join(' ').toLowerCase().includes(query),
    );
  }, [normalizedItems, searchTerm]);

  React.useEffect(() => {
    if (!filteredItems.some(item => item.id === selectedId)) {
      setSelectedId(filteredItems[0]?.id ?? '');
    }
  }, [filteredItems, selectedId]);

  const selectedItem = filteredItems.find(item => item.id === selectedId) ?? filteredItems[0];
  const selectedIndex = selectedItem ? filteredItems.findIndex(item => item.id === selectedItem.id) : -1;
  const canNavigatePrevious = selectedIndex > 0;
  const canNavigateNext = selectedIndex >= 0 && selectedIndex < filteredItems.length - 1;
  const searchPlaceholder = resolveI18nText(
    t,
    'marketplace.detail.viewer.searchPlaceholder',
    'marketplace.center.filters.searchPlaceholder',
  );
  const itemNameFallback = resolveI18nText(
    t,
    'marketplace.detail.viewer.fileNameFallback',
    'marketplace.common.unknown',
  );
  const descriptionFallback = resolveI18nText(
    t,
    'marketplace.detail.viewer.descriptionFallback',
    'marketplace.common.unknown',
  );

  const navigateToPrevious = () => {
    if (canNavigatePrevious) setSelectedId(filteredItems[selectedIndex - 1].id);
  };

  const navigateToNext = () => {
    if (canNavigateNext) setSelectedId(filteredItems[selectedIndex + 1].id);
  };

  const handleCopy = async () => {
    if (!selectedItem) return;
    try {
      await navigator.clipboard.writeText(selectedItem.content);
      toast({ title: t('marketplace.detail.viewer.copySuccess') });
    } catch {
      toast({ title: t('marketplace.detail.viewer.copyFailed'), variant: 'destructive' });
    }
  };

  const handleDownload = () => {
    if (!selectedItem) return;
    const blob = new Blob([selectedItem.content], { type: 'text/markdown' });
    downloadBlob(blob, selectedItem.fileName);
  };

  const handleSidebarResizeStart = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsSidebarCollapsed(false);
    setIsSidebarResizing(true);
    sidebarResizeRef.current = {
      startX: event.clientX,
      startWidth: isSidebarCollapsed ? MARKETPLACE_DETAIL_SIDEBAR_MIN_WIDTH : sidebarWidth,
    };
    document.body.classList.add('select-none', 'cursor-col-resize');
  };

  React.useEffect(() => {
    if (!isSidebarResizing) return undefined;

    const handleMouseMove = (event: MouseEvent) => {
      const dragState = sidebarResizeRef.current;
      if (!dragState) return;
      const nextWidth = Math.min(
        Math.max(dragState.startWidth + event.clientX - dragState.startX, MARKETPLACE_DETAIL_SIDEBAR_MIN_WIDTH),
        MARKETPLACE_DETAIL_SIDEBAR_MAX_WIDTH,
      );
      setSidebarWidth(nextWidth);
    };

    const handleMouseUp = () => {
      sidebarResizeRef.current = null;
      setIsSidebarResizing(false);
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };
  }, [isSidebarResizing]);

  const sidebarActions = (
    <>
      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" aria-label={t('marketplace.detail.viewer.refresh')}>
        <RefreshCw className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        aria-label={t('marketplace.detail.viewer.collapseSidebar')}
        title={t('marketplace.detail.viewer.collapseSidebar')}
        onClick={() => setIsSidebarCollapsed(true)}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>
    </>
  );

  const sidebarBody = (
    <div className="flex-1 space-y-2 overflow-y-auto p-3">
      {filteredItems.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-xs text-muted-foreground">
          {emptyLabel}
        </div>
      ) : (
        filteredItems.map(item => {
          const isActive = selectedItem?.id === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelectedId(item.id)}
              className={cn(
                'w-full rounded-lg border px-3 py-3 text-left transition-colors',
                isActive
                  ? 'border-primary/60 bg-primary/10 shadow-sm'
                  : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40',
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {item.fileName || item.name || itemNameFallback}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {item.description || item.path || descriptionFallback}
                  </div>
                </div>
                <div className="text-right text-[11px] text-muted-foreground">
                  {t('common.markdownFileViewer.units.bytes', { count: item.content.length })}
                </div>
              </div>
            </button>
          );
        })
      )}
    </div>
  );

  return (
    <div className="flex h-full overflow-hidden">
      <div
        className="relative flex-shrink-0"
        style={{ width: isSidebarCollapsed ? MARKETPLACE_DETAIL_SIDEBAR_COLLAPSED_WIDTH : sidebarWidth }}
      >
        {isSidebarCollapsed ? (
          <div className="flex h-full flex-col items-center gap-2 border-r border-border bg-background px-1 py-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              aria-label={t('marketplace.detail.viewer.expandSidebar')}
              title={t('marketplace.detail.viewer.expandSidebar')}
              onClick={() => setIsSidebarCollapsed(false)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Icon className="h-4 w-4 text-primary" />
          </div>
        ) : (
          <MarketplaceSectionSidebarShell
            title={title}
            icon={<Icon className="h-4 w-4" />}
            actions={sidebarActions}
            searchValue={searchTerm}
            onSearchChange={setSearchTerm}
            onSearchClear={() => setSearchTerm('')}
            searchPlaceholder={searchPlaceholder}
            body={sidebarBody}
          />
        )}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label={t('marketplace.detail.viewer.resizeSidebar')}
          className={cn(
            'absolute right-0 top-0 z-20 h-full w-1 cursor-col-resize transition-colors',
            isSidebarResizing ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
          )}
          onMouseDown={handleSidebarResizeStart}
        />
      </div>

      <main className="min-w-0 flex-1 bg-background">
        {selectedItem ? (
          <div className="flex h-full flex-col">
            <div className="sticky top-0 z-10 border-b border-border bg-background">
              <div className="border-b border-border bg-background p-4">
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <div className="flex min-w-0 shrink-0 items-center gap-2">
                      <Icon className="h-5 w-5 shrink-0 text-primary" />
                      <h3 className="max-w-64 truncate font-semibold text-foreground">
                        {selectedItem.fileName || selectedItem.name || itemNameFallback}
                      </h3>
                    </div>
                    <p className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
                      {selectedItem.description || selectedItem.path || descriptionFallback}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <Button variant="outline" size="sm" onClick={navigateToPrevious} disabled={!canNavigatePrevious}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={navigateToNext} disabled={!canNavigateNext}>
                      <ChevronRight className="h-4 w-4" />
                    </Button>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={handleCopy}>
                          <Copy className="mr-2 h-3 w-3" />
                          {t('marketplace.detail.viewer.copy')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={handleDownload}>
                          <Download className="mr-2 h-3 w-3" />
                          {t('marketplace.detail.viewer.download')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>

              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <div className="mx-auto max-w-4xl">
                {renderItem ? renderItem(selectedItem) : <MarkdownContent content={selectedItem.content} />}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <Icon className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{emptyLabel}</p>
          </div>
        )}
      </main>
    </div>
  );
};
