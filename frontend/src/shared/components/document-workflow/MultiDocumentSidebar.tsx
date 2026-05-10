import React from 'react';
import { Search } from 'lucide-react';
import { FileTreeSearchBar } from '@/shared/components/file-workbench';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/shared/utils/cn';

export interface MultiDocumentSidebarItem {
  id: string;
  label: string;
  description?: string;
}

export interface MultiDocumentSidebarLabels {
  searchPlaceholder: string;
  loading: string;
  empty: string;
  dirty: string;
}

export interface MultiDocumentSidebarProps<TItem extends MultiDocumentSidebarItem> {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: TItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  labels: MultiDocumentSidebarLabels;
  actions?: React.ReactNode;
  isLoading?: boolean;
  showSearch?: boolean;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  getDirty?: (item: TItem) => boolean;
  renderItemMeta?: (item: TItem) => React.ReactNode;
  getSearchText?: (item: TItem) => string[];
}

const defaultSearchText = <TItem extends MultiDocumentSidebarItem>(item: TItem): string[] => {
  const values = [item.label, item.description];
  return values.filter((value): value is string => typeof value === 'string');
};

export const MultiDocumentSidebar = <TItem extends MultiDocumentSidebarItem>({
  title,
  icon: Icon,
  items,
  selectedId,
  onSelect,
  labels,
  actions,
  isLoading = false,
  showSearch = false,
  searchValue = '',
  onSearchChange,
  searchPlaceholder,
  getDirty,
  renderItemMeta,
  getSearchText,
}: MultiDocumentSidebarProps<TItem>) => {
  const normalizedQuery = searchValue.trim().toLowerCase();
  const placeholder = searchPlaceholder ?? labels.searchPlaceholder;

  const filteredItems = React.useMemo(() => {
    if (!showSearch || !normalizedQuery) {
      return items;
    }
    return items.filter((item) => {
      const searchableText = (getSearchText?.(item) ?? defaultSearchText(item)).join(' ').toLowerCase();
      return searchableText.includes(normalizedQuery);
    });
  }, [getSearchText, items, normalizedQuery, showSearch]);

  React.useEffect(() => {
    if (filteredItems.length === 0) {
      if (selectedId !== null) {
        onSelect(null);
      }
      return;
    }

    const selectedExists = selectedId ? filteredItems.some((item) => item.id === selectedId) : false;
    if (!selectedId || !selectedExists) {
      onSelect(filteredItems[0].id);
    }
  }, [filteredItems, onSelect, selectedId]);

  const body = isLoading && items.length === 0 ? (
    <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
      {labels.loading}
    </div>
  ) : filteredItems.length === 0 ? (
    <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
      {labels.empty}
    </div>
  ) : (
    filteredItems.map((item) => {
      const isActive = item.id === selectedId;
      const isDirty = getDirty?.(item) ?? false;
      return (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect(item.id)}
          className={cn(
            'w-full rounded-lg border px-3 py-3 text-left transition-colors',
            isActive
              ? 'border-primary/60 bg-primary/10 shadow-sm'
              : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40',
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 items-center gap-2">
                {isDirty ? (
                  <span
                    aria-label={labels.dirty}
                    className="h-2 w-2 rounded-full bg-amber-500"
                  />
                ) : null}
                <div className="truncate text-sm font-medium">{item.label}</div>
              </div>
              {item.description ? (
                <div className="truncate text-xs text-muted-foreground">{item.description}</div>
              ) : null}
              {renderItemMeta ? <div className="mt-1 text-xs text-muted-foreground">{renderItemMeta(item)}</div> : null}
            </div>
          </div>
        </button>
      );
    })
  );

  return (
    <div className="flex h-full min-h-0 flex-col border-r border-border bg-background text-foreground">
      <div className="flex h-10 items-center justify-between border-b border-border bg-card px-3">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="h-4 w-4 flex-shrink-0 text-primary" />
          <span className="truncate text-sm font-medium">{title}</span>
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
      </div>
      {showSearch && onSearchChange ? (
        <FileTreeSearchBar
          value={searchValue}
          onChange={onSearchChange}
          placeholder={placeholder}
          showClearButton
          onClear={() => onSearchChange('')}
          containerClassName="border-b border-border bg-muted/20"
          iconClassName="text-muted-foreground"
        />
      ) : null}
      <div className="flex-1 min-h-0 overflow-y-auto p-3">
        {body}
      </div>
    </div>
  );
};

export default MultiDocumentSidebar;
