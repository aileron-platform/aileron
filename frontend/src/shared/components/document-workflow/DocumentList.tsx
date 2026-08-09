import React from 'react';
import { cn } from '@/shared/utils/cn';

export interface DocumentListItem {
  id: string;
  label: string;
  description?: string;
}

export interface DocumentListLabels {
  loading: string;
  empty: string;
  dirty: string;
}

export type DocumentListEmptySelectionBehavior = 'clearOnEmpty' | 'preserveOnEmpty';

export interface DocumentListProps<TItem extends DocumentListItem> {
  items: TItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  labels: DocumentListLabels;
  isLoading?: boolean;
  autoSelectFirst?: boolean;
  emptySelectionBehavior?: DocumentListEmptySelectionBehavior;
  getDirty?: (item: TItem) => boolean;
  renderItemMeta?: (item: TItem) => React.ReactNode;
  renderItemContextMenu?: (item: TItem) => React.ReactNode;
}

export const DocumentList = <TItem extends DocumentListItem>({
  items,
  selectedId,
  onSelect,
  labels,
  isLoading = false,
  autoSelectFirst = true,
  emptySelectionBehavior = 'clearOnEmpty',
  getDirty,
  renderItemMeta,
  renderItemContextMenu,
}: DocumentListProps<TItem>) => {
  const [contextMenu, setContextMenu] = React.useState<{
    item: TItem;
    x: number;
    y: number;
  } | null>(null);

  const closeContextMenu = React.useCallback(() => setContextMenu(null), []);

  React.useEffect(() => {
    if (items.length === 0) {
      if (emptySelectionBehavior === 'clearOnEmpty' && selectedId !== null) {
        onSelect(null);
      }
      return;
    }

    const selectedExists = selectedId ? items.some((item) => item.id === selectedId) : false;
    if ((!selectedId || !selectedExists) && autoSelectFirst) {
      onSelect(items[0].id);
    }
  }, [autoSelectFirst, emptySelectionBehavior, items, onSelect, selectedId]);

  const body = isLoading && items.length === 0 ? (
    <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
      {labels.loading}
    </div>
  ) : items.length === 0 ? (
    <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
      {labels.empty}
    </div>
  ) : (
    items.map((item) => {
      const isActive = item.id === selectedId;
      const isDirty = getDirty?.(item) ?? false;
      return (
        <button
          key={item.id}
          type="button"
          aria-label={item.label}
          onClick={() => onSelect(item.id)}
          onContextMenu={(event) => {
            if (!renderItemContextMenu) return;
            event.preventDefault();
            setContextMenu({ item, x: event.clientX, y: event.clientY });
          }}
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
    <>
      {body}
      {contextMenu && renderItemContextMenu ? (
        <div
          role="menu"
          className="fixed z-50 min-w-36 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={closeContextMenu}
        >
          {renderItemContextMenu(contextMenu.item)}
        </div>
      ) : null}
    </>
  );
};
