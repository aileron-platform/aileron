/**
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../providers/WorkspaceProvider';
import { getNavigationItems, type NavigationConfig } from './workspaceNavigationModel';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  buildWorkspaceNavigationPath,
  isWorkspaceNavigationItemActive,
  isWorkspaceSubItemActive,
} from './workspaceSidebarModel';

interface HoverMenuItem {
  item: NavigationConfig;
  buttonRef: React.RefObject<HTMLButtonElement>;
}

/**
 */
type SubMenuItem = NavigationConfig['subItems'][number];

const NavigationItemIcon: React.FC<{
  item: NavigationConfig;
  className?: string;
}> = ({ item, className }) => {
  const Icon = item.icon;

  if (item.iconSrc) {
    return (
      <span
        className={cn(
          'flex flex-shrink-0 items-center justify-center overflow-hidden rounded border border-sidebar-border bg-sidebar',
          className,
        )}
      >
        <img src={item.iconSrc} alt="" className="h-4 w-4 object-contain" />
      </span>
    );
  }

  return <Icon className={className} />;
};

export interface WorkspaceSidebarProps {
  collapsed: boolean;
}

export const WorkspaceSidebar: React.FC<WorkspaceSidebarProps> = ({ collapsed }) => {
  const {
    state,
    dispatch,
    permissions,
    workspaceRuntime,
  } = useWorkspace();
  const { t } = useI18n();
  const navigate = useNavigate();

  const navigationItems = React.useMemo(
    () => getNavigationItems({
      agenticTools: workspaceRuntime.agenticTools,
      hasWorkspaceOperation: permissions.hasOperation,
    }),
    [permissions, workspaceRuntime.agenticTools],
  );

  const [hoverMenuItem, setHoverMenuItem] = useState<HoverMenuItem | null>(null);
  const popupMenuRef = useRef<HTMLDivElement>(null);
  const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const buttonRefs = useRef<Record<string, React.RefObject<HTMLButtonElement>>>({});

  const getButtonRef = useCallback((itemId: string): React.RefObject<HTMLButtonElement> => {
    if (!buttonRefs.current[itemId]) {
      buttonRefs.current[itemId] = React.createRef<HTMLButtonElement>();
    }
    return buttonRefs.current[itemId];
  }, []);

  useEffect(() => {
    return () => {
      clearHideTimeout();
    };
  }, []);

  const clearHideTimeout = () => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  };

  const showPopupMenu = (item: NavigationConfig, buttonRef: React.RefObject<HTMLButtonElement>) => {
    clearHideTimeout();
    if (collapsed && item.hasSubMenu) {
      setHoverMenuItem({ item, buttonRef });
    }
  };

  const hidePopupMenu = () => {
    clearHideTimeout();
    hideTimeoutRef.current = setTimeout(() => {
      setHoverMenuItem(null);
    }, 100);
  };

  const handleNavigationClick = (e: React.MouseEvent, item: NavigationConfig) => {
    e.preventDefault();
    e.stopPropagation();

    if (collapsed) {
      setHoverMenuItem(null);
    }

    if (item.hasSubMenu) {
      dispatch({ type: 'TOGGLE_NAVIGATION_ITEM', payload: item.id });
      return;
    }

    navigate(buildWorkspaceNavigationPath(item.id, undefined, workspaceRuntime.workspaceId));
  };

  const handleSubItemClick = (parentId: string, subItem: SubMenuItem) => {
    navigate(buildWorkspaceNavigationPath(parentId, subItem, workspaceRuntime.workspaceId));
  };

  const handleMouseEnter = (item: NavigationConfig, buttonRef: React.RefObject<HTMLButtonElement>) => {
    showPopupMenu(item, buttonRef);
  };

  const handleMouseLeave = () => {
    hidePopupMenu();
  };

  const handleCollapsedSubItemClick = (subItem: SubMenuItem) => {
    if (hoverMenuItem) {
      const parentId = hoverMenuItem.item.id;
      navigate(buildWorkspaceNavigationPath(parentId, subItem, workspaceRuntime.workspaceId));
      setHoverMenuItem(null);
    }
  };

  // isWorkspaceSubItemActive only reads currentFeature and the per-feature subView fields,
  // so depend on those granular fields instead of the whole state object to avoid recreating
  // this callback on every provider dispatch.
  const isSubItemActive = useCallback((item: NavigationConfig, subItem: SubMenuItem): boolean => {
    return isWorkspaceSubItemActive(state, item.id, subItem);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    state.currentFeature,
    state.versionControl.subView,
    state.workspaceSettings.subView,
    state.containerManagement.subView,
    state.agentToolSettings.subView,
  ]);

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      <nav className="p-2 flex-1 overflow-y-auto min-h-0">
        {navigationItems.map((item) => {
          const isExpanded = state.expandedNavigationItems.includes(item.id);
          const buttonRef = getButtonRef(item.id);
          const isActive = isWorkspaceNavigationItemActive(state, item);

          return (
            <div key={item.id}>
              <button
                ref={buttonRef}
                onClick={(e) => handleNavigationClick(e, item)}
                onMouseEnter={() => handleMouseEnter(item, buttonRef)}
                onMouseLeave={handleMouseLeave}
                className={`w-full flex items-center rounded-lg mb-1 transition-colors ${collapsed ? 'justify-center p-2' : 'p-2'
                  } ${isActive
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
                    : 'hover:bg-sidebar-accent text-sidebar-foreground'
                  }`}
              >
                <NavigationItemIcon item={item} className="w-4 h-4 flex-shrink-0" />
                {!collapsed && (
                  <>
                    <span className="ml-2 text-sm text-left flex-1">{t(item.labelKey)}</span>
                    {item.hasSubMenu && (
                      <ChevronDown className={`w-3.5 h-3.5 flex-shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''
                        }`} />
                    )}
                  </>
                )}
              </button>

              {item.hasSubMenu && item.subItems && !collapsed && isExpanded && (
                <div className="ml-7 space-y-0.5 mb-1">
                  {item.subItems.map((subItem) => (
                    <button
                      key={subItem.id}
                      onClick={() => handleSubItemClick(item.id, subItem)}
                      className={`w-full flex items-center p-1.5 rounded text-sm hover:bg-sidebar-accent ${isSubItemActive(item, subItem)
                        ? 'bg-sidebar-accent text-sidebar-foreground font-medium'
                        : 'text-sidebar-foreground'
                        }`}
                    >
                      <subItem.icon className="w-3.5 h-3.5 mr-1.5 flex-shrink-0" />
                      <span className="text-left flex-1">{t(subItem.labelKey)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {collapsed && hoverMenuItem && hoverMenuItem.item.hasSubMenu && hoverMenuItem.item.subItems && (
        <div
          ref={popupMenuRef}
          className="fixed z-50"
          style={{
            left: `${(hoverMenuItem.buttonRef.current?.getBoundingClientRect().left ?? 0) + 48}px`,
            top: `${hoverMenuItem.buttonRef.current?.getBoundingClientRect().top ?? 0}px`,
          }}
          onMouseEnter={clearHideTimeout}
          onMouseLeave={hidePopupMenu}
        >
          <div className="bg-popover border border-border rounded-lg shadow-lg p-1 min-w-48">
            <div className="px-2 py-1.5 border-b border-border mb-1">
              <div className="flex items-center gap-2 text-sm font-medium">
                <NavigationItemIcon item={hoverMenuItem.item} className="w-4 h-4" />
                <span>{t(hoverMenuItem.item.labelKey)}</span>
              </div>
            </div>
            <div className="space-y-0.5">
              {hoverMenuItem.item.subItems.map((subItem) => {
                const isActive = isSubItemActive(hoverMenuItem.item, subItem);

                return (
                  <button
                    key={subItem.id}
                    onClick={() => handleCollapsedSubItemClick(subItem)}
                    className={cn(
                      'w-full flex items-center p-2 rounded text-sm hover:bg-accent hover:text-accent-foreground text-left',
                      isActive
                        ? 'bg-accent text-accent-foreground font-medium'
                        : 'text-foreground'
                    )}
                  >
                    <subItem.icon className="w-4 h-4 mr-2 flex-shrink-0" />
                    <span className="flex-1">{t(subItem.labelKey)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
