import React from 'react';
import { ChevronDown, type LucideIcon } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import type { ResourceAccessRole } from '@/shared/authorization/resourceAccessRole';
import type { ResourceAccessSource } from '@/shared/authorization/resourceAuthorization';
import { KNOWLEDGE_BASE_NAVIGATION_ITEMS } from './knowledgeBaseNavigation';
import {
  buildKnowledgeBaseNavPath,
  resolveKnowledgeBaseActiveNav,
  type KnowledgeBaseFeatureId,
  type KnowledgeBaseVersionControlSubView,
} from '../model/knowledgeBaseShellModel';

interface KnowledgeBaseSidebarProps {
  knowledgeBaseId: string;
  accessRole: ResourceAccessRole;
  accessSource: ResourceAccessSource;
  storageInfo: string;
  ownerLabel: string;
  shareCount: number | null;
  attachmentCount: number | null;
  collapsed?: boolean;
}

const ROLE_BADGE_VARIANT: Record<
  ResourceAccessRole,
  'default' | 'secondary' | 'outline'
> = {
  owner: 'default',
  manager: 'secondary',
  reader: 'outline',
};
interface HoverMenuState {
  item: (typeof KNOWLEDGE_BASE_NAVIGATION_ITEMS)[number];
  anchor: DOMRect;
}

/**
 * Product content for the semantic navigation region. ProductShell owns the
 * rail width, resize handle, header and collapse control; this component only
 * renders navigation content for the current collapsed state.
 */
export const KnowledgeBaseSidebar: React.FC<KnowledgeBaseSidebarProps> = ({
  knowledgeBaseId,
  accessRole,
  accessSource,
  storageInfo,
  ownerLabel,
  shareCount,
  attachmentCount,
  collapsed = false,
}) => {
  const { t } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const activeNav = resolveKnowledgeBaseActiveNav(location.pathname);
  const [expandedItems, setExpandedItems] = React.useState<string[]>(() => (
    activeNav.featureId && activeNav.subItemId ? [activeNav.featureId] : []
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

  const scheduleHidePopup = React.useCallback(() => {
    clearHideTimeout();
    hideTimeoutRef.current = setTimeout(() => setHoverMenu(null), 100);
  }, [clearHideTimeout]);

  const items = React.useMemo(() => KNOWLEDGE_BASE_NAVIGATION_ITEMS.map((item) => ({
    ...item,
    count: item.countId === 'shares' ? shareCount : item.countId === 'attachments' ? attachmentCount : null,
  })), [attachmentCount, shareCount]);

  const handleItemClick = (item: (typeof items)[number]) => {
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
    navigate(buildKnowledgeBaseNavPath(
      knowledgeBaseId,
      item.id as KnowledgeBaseFeatureId,
    ));
  };

  const footer = (
    <div
      data-testid="kb-sidebar-status-bar"
      className="space-y-1.5 rounded-md bg-sidebar-accent/40 p-2 text-xs text-sidebar-foreground"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground">{t('knowledgeBase.detail.status.owner')}</span>
        <span className="min-w-0 truncate font-medium">{ownerLabel}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground">{t('knowledgeBase.detail.status.role')}</span>
        <Badge variant={ROLE_BADGE_VARIANT[accessRole]}>
          {accessSource === 'platform_admin'
            ? t('knowledgeBase.common.role.platformAdmin')
            : t(`knowledgeBase.common.role.${accessRole}`)}
        </Badge>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground">{t('knowledgeBase.detail.status.storage')}</span>
        <span className="min-w-0 truncate font-medium">{storageInfo}</span>
      </div>
    </div>
  );

  return (
    <div data-testid="kb-sidebar" className="flex h-full min-h-0 flex-col">
      <nav className="min-h-0 flex-1 overflow-y-auto p-2">
        {items.map((item) => {
          const Icon: LucideIcon = item.icon;
          const isActive = activeNav.featureId === item.id;
          const isExpanded = expandedItems.includes(item.id);
          const count = item.count ?? null;
          return (
            <div key={item.id}>
              <button
                type="button"
                title={t(item.labelKey)}
                aria-label={t(item.labelKey)}
                aria-current={isActive ? 'page' : undefined}
                onClick={() => handleItemClick(item)}
                onMouseEnter={(event) => {
                  clearHideTimeout();
                  if (collapsed && item.subItems) {
                    setHoverMenu({ item, anchor: event.currentTarget.getBoundingClientRect() });
                  }
                }}
                onMouseLeave={scheduleHidePopup}
                className={`mb-1 flex w-full items-center rounded-lg p-2 transition-colors ${collapsed ? 'justify-center' : ''} ${
                  isActive
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent'
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed ? (
                  <>
                    <span className="ml-2 flex-1 text-left text-sm">{t(item.labelKey)}</span>
                    {count !== null ? (
                      <span aria-hidden="true" className="ml-2 min-w-5 rounded-full bg-muted px-1.5 py-0.5 text-[11px] leading-none text-muted-foreground">
                        {count}
                      </span>
                    ) : null}
                    {item.subItems ? <ChevronDown className={`h-3.5 w-3.5 shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''}`} /> : null}
                  </>
                ) : null}
              </button>
              {item.subItems && !collapsed && isExpanded ? (
                <div className="mb-1 ml-7 space-y-0.5">
                  {item.subItems.map((subItem) => {
                    const SubIcon = subItem.icon;
                    const isSubActive = isActive && activeNav.subItemId === subItem.id;
                    return (
                      <button
                        key={subItem.id}
                        type="button"
                        aria-label={t(subItem.labelKey)}
                        onClick={() => navigate(buildKnowledgeBaseNavPath(
                          knowledgeBaseId,
                          item.id as KnowledgeBaseFeatureId,
                          subItem.id as KnowledgeBaseVersionControlSubView,
                        ))}
                        className={`flex w-full items-center rounded p-1.5 text-sm hover:bg-sidebar-accent ${
                          isSubActive ? 'bg-sidebar-accent font-medium text-sidebar-foreground' : 'text-sidebar-foreground'
                        }`}
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
      {!collapsed ? <div className="shrink-0 border-t border-sidebar-border p-2">{footer}</div> : null}
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
                const isSubActive = activeNav.featureId === hoverMenu.item.id && activeNav.subItemId === subItem.id;
                return (
                  <button
                    key={subItem.id}
                    type="button"
                    aria-label={t(subItem.labelKey)}
                    onClick={() => {
                      navigate(buildKnowledgeBaseNavPath(
                        knowledgeBaseId,
                        hoverMenu.item.id as KnowledgeBaseFeatureId,
                        subItem.id as KnowledgeBaseVersionControlSubView,
                      ));
                      setHoverMenu(null);
                    }}
                    className={`flex w-full items-center rounded p-2 text-left text-sm hover:bg-accent hover:text-accent-foreground ${
                      isSubActive ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground'
                    }`}
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
