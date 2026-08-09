import React from 'react';
import { FileTreeSearchBar } from '@/shared/components/file-workbench';
import { DocumentList, type DocumentListItem } from './DocumentList';

export type DocumentListSidebarItem = DocumentListItem;

export interface DocumentListSidebarLabels {
  searchPlaceholder: string;
  loading: string;
  empty: string;
  dirty: string;
}

export interface DocumentListSidebarProps<TItem extends DocumentListSidebarItem> {
  title?: string;
  icon?: React.ComponentType<{ className?: string }>;
  items: TItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  labels: DocumentListSidebarLabels;
  actions?: React.ReactNode;
  showHeader?: boolean;
  isLoading?: boolean;
  autoSelectFirst?: boolean;
  showSearch?: boolean;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  getDirty?: (item: TItem) => boolean;
  renderItemMeta?: (item: TItem) => React.ReactNode;
  renderItemContextMenu?: (item: TItem) => React.ReactNode;
  getSearchText?: (item: TItem) => string[];
}

const defaultSearchText = <TItem extends DocumentListSidebarItem>(item: TItem): string[] => {
  const values = [item.label, item.description];
  return values.filter((value): value is string => typeof value === 'string');
};

export const DocumentListSidebar = <TItem extends DocumentListSidebarItem>({
  title,
  icon: Icon,
  items,
  selectedId,
  onSelect,
  labels,
  actions,
  showHeader = true,
  isLoading = false,
  autoSelectFirst = true,
  showSearch = false,
  searchValue = '',
  onSearchChange,
  searchPlaceholder,
  getDirty,
  renderItemMeta,
  renderItemContextMenu,
  getSearchText,
}: DocumentListSidebarProps<TItem>) => {
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

  return (
    <div className="flex h-full min-h-0 flex-col border-r border-border bg-background text-foreground">
      {showHeader && title ? (
        <div className="flex h-10 items-center justify-between border-b border-border bg-card px-3">
          <div className="flex min-w-0 items-center gap-2">
            {Icon ? <Icon className="h-4 w-4 flex-shrink-0 text-primary" /> : null}
            <span className="truncate text-sm font-medium">{title}</span>
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
        </div>
      ) : null}
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
        <DocumentList
          items={filteredItems}
          selectedId={selectedId}
          onSelect={onSelect}
          labels={{
            loading: labels.loading,
            empty: labels.empty,
            dirty: labels.dirty,
          }}
          isLoading={isLoading && items.length === 0}
          autoSelectFirst={autoSelectFirst}
          emptySelectionBehavior="clearOnEmpty"
          getDirty={getDirty}
          renderItemMeta={renderItemMeta}
          renderItemContextMenu={renderItemContextMenu}
        />
      </div>
    </div>
  );
};
