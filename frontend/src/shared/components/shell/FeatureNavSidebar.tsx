import React from 'react';
import { ChevronDown, type LucideIcon } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';

export interface FeatureNavSubItem {
  id: string;
  labelKey: string;
  icon: LucideIcon;
}

export interface FeatureNavItem {
  id: string;
  icon: LucideIcon;
  labelKey: string;
  subItems?: FeatureNavSubItem[];
  count?: number | null;
  disabled?: boolean;
}

export interface FeatureNavSidebarProps {
  items: FeatureNavItem[];
  activeId: string | null;
  activeSubId?: string | null;
  onSelect: (itemId: string) => void;
  onSelectSub?: (itemId: string, subId: string) => void;
  header?: React.ReactNode;
  footer?: React.ReactNode;
  /** Render the feature-owned header when this content is used outside ProductShell. */
  showHeader?: boolean;
  /** The shell-owned collapsed state for the navigation region. */
  collapsed?: boolean;
  testId?: string;
}

interface HoverMenuState {
  item: FeatureNavItem;
  anchor: DOMRect;
}

export const FeatureNavSidebarContent: React.FC<FeatureNavSidebarProps> = ({
  items,
  activeId,
  activeSubId = null,
  onSelect,
  onSelectSub,
  header,
  footer,
  showHeader = true,
  collapsed = false,
  testId,
}) => {
  const { t } = useI18n();

  const [expandedItems, setExpandedItems] = React.useState<string[]>(() => (
    activeId && activeSubId ? [activeId] : []
  ));
  const [hoverMenu, setHoverMenu] = React.useState<HoverMenuState | null>(null);
  const hideTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearHideTimeout = React.useCallback(() => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  }, []);

  React.useEffect(() => () => clearHideTimeout(), [clearHideTimeout]);

  React.useEffect(() => {
    if (!activeId || !activeSubId) {
      return;
    }
    setExpandedItems((current) => (
      current.includes(activeId) ? current : [...current, activeId]
    ));
  }, [activeId, activeSubId]);

  const scheduleHidePopup = React.useCallback(() => {
    clearHideTimeout();
    hideTimeoutRef.current = setTimeout(() => setHoverMenu(null), 100);
  }, [clearHideTimeout]);

  const handleItemClick = (item: FeatureNavItem) => {
    if (item.disabled) {
      return;
    }
    if (collapsed) {
      setHoverMenu(null);
    }
    if (item.subItems) {
      setExpandedItems((current) => (
        current.includes(item.id)
          ? current.filter((id) => id !== item.id)
          : [...current, item.id]
      ));
    }
    onSelect(item.id);
  };

  return (
    <div
      data-testid={testId}
      className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden"
    >
      {showHeader ? (
        <div className={cn(
          'flex h-10 shrink-0 items-center border-b border-sidebar-border bg-card',
          collapsed ? 'justify-center px-0' : 'justify-between gap-2 px-3',
        )}>
          {!collapsed ? <div className="flex min-w-0 items-center gap-2">{header}</div> : null}
          {!collapsed ? <div className="shrink-0" /> : null}
        </div>
      ) : null}

      <nav className="min-h-0 flex-1 overflow-y-auto p-2">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = activeId === item.id;
          const isExpanded = expandedItems.includes(item.id);
          const count = item.count ?? null;

          return (
            <div key={item.id}>
              <button
                type="button"
                title={t(item.labelKey)}
                aria-label={t(item.labelKey)}
                aria-current={isActive ? 'page' : undefined}
                disabled={item.disabled}
                onClick={() => handleItemClick(item)}
                onMouseEnter={(event) => {
                  clearHideTimeout();
                  if (collapsed && item.subItems) {
                    setHoverMenu({ item, anchor: event.currentTarget.getBoundingClientRect() });
                  }
                }}
                onMouseLeave={scheduleHidePopup}
                className={cn(
                  'mb-1 flex w-full items-center rounded-lg p-2 transition-colors',
                  collapsed && 'justify-center',
                  item.disabled && 'cursor-not-allowed opacity-50',
                  isActive
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed ? (
                  <>
                    <span className="ml-2 flex-1 text-left text-sm">{t(item.labelKey)}</span>
                    {count !== null ? (
                      <span
                        aria-hidden="true"
                        className="ml-2 min-w-5 rounded-full bg-muted px-1.5 py-0.5 text-[11px] leading-none text-muted-foreground"
                      >
                        {count}
                      </span>
                    ) : null}
                    {item.subItems ? (
                      <ChevronDown className={cn('h-3.5 w-3.5 shrink-0 transition-transform', isExpanded && 'rotate-180')} />
                    ) : null}
                  </>
                ) : null}
              </button>

              {item.subItems && !collapsed && isExpanded ? (
                <div className="mb-1 ml-7 space-y-0.5">
                  {item.subItems.map((subItem) => {
                    const SubIcon = subItem.icon;
                    const isSubActive = isActive && activeSubId === subItem.id;
                    return (
                      <button
                        key={subItem.id}
                        type="button"
                        aria-label={t(subItem.labelKey)}
                        onClick={() => onSelectSub?.(item.id, subItem.id)}
                        className={cn(
                          'flex w-full items-center rounded p-1.5 text-sm hover:bg-sidebar-accent',
                          isSubActive ? 'bg-sidebar-accent font-medium text-sidebar-foreground' : 'text-sidebar-foreground',
                        )}
                      >
                        <SubIcon className="mr-1.5 h-3.5 w-3.5 shrink-0" />
                        <span className="flex-1 text-left">{t(subItem.labelKey)}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </nav>

      {!collapsed && footer ? (
        <div className="shrink-0 border-t border-sidebar-border p-2">{footer}</div>
      ) : null}

      {collapsed && hoverMenu?.item.subItems ? (
        <div
          className="fixed z-50"
          style={{ left: hoverMenu.anchor.left + 48, top: hoverMenu.anchor.top }}
          onMouseEnter={clearHideTimeout}
          onMouseLeave={scheduleHidePopup}
        >
          <div className="min-w-48 rounded-lg border border-border bg-popover p-1 shadow-lg">
            <div className="mb-1 border-b border-border px-2 py-1.5">
              <div className="flex items-center gap-2 text-sm font-medium">
                <hoverMenu.item.icon className="h-4 w-4" />
                <span>{t(hoverMenu.item.labelKey)}</span>
              </div>
            </div>
            <div className="space-y-0.5">
              {hoverMenu.item.subItems.map((subItem) => {
                const SubIcon = subItem.icon;
                const isSubActive = activeId === hoverMenu.item.id && activeSubId === subItem.id;
                return (
                  <button
                    key={subItem.id}
                    type="button"
                    aria-label={t(subItem.labelKey)}
                    onClick={() => {
                      onSelectSub?.(hoverMenu.item.id, subItem.id);
                      setHoverMenu(null);
                    }}
                    className={cn(
                      'flex w-full items-center rounded p-2 text-left text-sm hover:bg-accent hover:text-accent-foreground',
                      isSubActive ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground',
                    )}
                  >
                    <SubIcon className="mr-2 h-4 w-4 shrink-0" />
                    <span className="flex-1">{t(subItem.labelKey)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}

    </div>
  );
};
