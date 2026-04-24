/**
 * WorkspaceSidebar - 工作區側邊欄
 * 完全複製自原始 NavigationSidebar 設計，保持相同的 UI 和行為
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronDown, Navigation } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../providers/WorkspaceProvider';
import { MAIN_NAVIGATION_ITEMS, getNavigationItems, type NavigationConfig } from './navigation-constants';
import { normalizeAgentType } from '../features/agent-settings/utils';
import { AGENT_NAVIGATION_IDS } from '../features/agent-settings/agentToolConfigs';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { useOpenSpecWorkspace } from '../features/openspec/OpenSpecWorkspaceContext';

interface HoverMenuItem {
  item: NavigationConfig;
  buttonRef: React.RefObject<HTMLButtonElement>;
}

/**
 * 子選單項目型別
 */
type SubMenuItem = NavigationConfig['subItems'][number];

export const WorkspaceSidebar: React.FC = () => {
  const { state, dispatch, workspaceRuntime } = useWorkspace();
  const { t } = useI18n();
  const navigate = useNavigate();
  const { summary } = useOpenSpecWorkspace();

  // 根據 cliType 動態取得導航項目
  const cliType = normalizeAgentType(workspaceRuntime.cliType);
  const navigationItems = React.useMemo(() => getNavigationItems(cliType), [cliType]);

  // 追蹤收折狀態下 hover 的導航項目
  const [hoverMenuItem, setHoverMenuItem] = useState<HoverMenuItem | null>(null);
  const popupMenuRef = useRef<HTMLDivElement>(null);
  const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  // 集中管理所有導航項目的 button refs，避免在 map 迴圈中建立新 ref 造成記憶體洩漏
  const buttonRefs = useRef<Record<string, React.RefObject<HTMLButtonElement>>>({});

  // 獲取或創建指定項目的 button ref
  const getButtonRef = useCallback((itemId: string): React.RefObject<HTMLButtonElement> => {
    if (!buttonRefs.current[itemId]) {
      buttonRefs.current[itemId] = React.createRef<HTMLButtonElement>();
    }
    return buttonRefs.current[itemId];
  }, []);

  // 組件卸載時清理定時器，避免在已卸載的組件上執行 setState
  useEffect(() => {
    return () => {
      clearHideTimeout();
    };
  }, []);

  /**
   * 檢查子選單項目是否為當前激活狀態
   */
  const isSubItemActive = useCallback((item: NavigationConfig, subItem: SubMenuItem): boolean => {
    return state.currentFeature === item.id &&
      ((item.id === 'version-control' && state.versionControl.subView === subItem.id) ||
        (item.id === 'openspec' && state.openspec.subView === subItem.id) ||
        (item.id === 'workspace-settings' && state.workspaceSettings.subView === subItem.id) ||
        (item.id === 'container-management' && state.containerManagement.subView === subItem.id) ||
        (item.id === 'claude-code' && state.claudeCodeSettings.subView === subItem.id) ||
        (AGENT_NAVIGATION_IDS.includes(item.id) && item.id !== 'claude-code' && state.agentToolSettings.subView === subItem.id) ||
        (item.id === 'preview' && state.preview.subView === subItem.id));
  }, [state.currentFeature, state.versionControl.subView, state.openspec.subView, state.workspaceSettings.subView,
  state.containerManagement.subView, state.claudeCodeSettings.subView, state.agentToolSettings.subView, state.preview.subView]);

  // 清除延遲關閉的定時器
  const clearHideTimeout = () => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  };

  // 顯示彈出選單
  const showPopupMenu = (item: NavigationConfig, buttonRef: React.RefObject<HTMLButtonElement>) => {
    clearHideTimeout();
    if (state.sidebarCollapsed && item.hasSubMenu) {
      setHoverMenuItem({ item, buttonRef });
    }
  };

  // 隱藏彈出選單（帶延遲）
  const hidePopupMenu = () => {
    clearHideTimeout();
    hideTimeoutRef.current = setTimeout(() => {
      setHoverMenuItem(null);
    }, 100);
  };

  const handleNavigationClick = (e: React.MouseEvent, item: NavigationConfig) => {
    e.preventDefault();
    e.stopPropagation();

    // 收折狀態下點擊後關閉彈出選單
    if (state.sidebarCollapsed) {
      setHoverMenuItem(null);
    }

    // 處理子選單展開/收合
    if (item.hasSubMenu) {
      dispatch({ type: 'TOGGLE_NAVIGATION_ITEM', payload: item.id });
    }

    // 導航到對應路由 - 使用工作區範圍內的絕對路徑
    navigate(item.id === 'openspec' ? '/workspaces/openspec/in-progress' : `/workspaces/${item.id}`);
  };

  const handleSubItemClick = (parentId: string, subItemId: string) => {
    // 導航到對應的子路由 - 使用工作區範圍內的絕對路徑
    navigate(`/workspaces/${parentId}/${subItemId}`);
  };

  // 處理滑鼠移入導航項目（僅在收折狀態下且該項目有子選單時）
  const handleMouseEnter = (item: NavigationConfig, buttonRef: React.RefObject<HTMLButtonElement>) => {
    showPopupMenu(item, buttonRef);
  };

  // 處理滑鼠移出導航項目
  const handleMouseLeave = () => {
    hidePopupMenu();
  };

  // 點擊子選單項目導航（收折狀態下彈出選單）
  const handleCollapsedSubItemClick = (subItem: SubMenuItem) => {
    if (hoverMenuItem) {
      const parentId = hoverMenuItem.item.id;
      navigate(`/workspaces/${parentId}/${subItem.id}`);
      setHoverMenuItem(null);
    }
  };

  const getSubItemCount = useCallback((itemId: string, subItemId: string): number | null => {
    if (itemId !== 'openspec') {
      return null;
    }

    if (subItemId === 'in-progress' || subItemId === 'complete' || subItemId === 'archived') {
      if (!summary?.initialized) {
        return 0;
      }
      if (subItemId === 'in-progress') {
        return summary.counts.inProgress;
      }
      return summary.counts[subItemId];
    }

    return null;
  }, [summary]);

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      <div className={`h-10 px-3 border-b border-sidebar-border bg-card flex items-center flex-shrink-0 ${state.sidebarCollapsed ? 'justify-center' : 'justify-between'
        }`}>
        {!state.sidebarCollapsed && (
          <div className="flex items-center gap-2">
            <Navigation className="h-4 w-4 text-sidebar-primary" />
            <h2 className="text-sm font-medium text-sidebar-foreground">{t('workspace.sidebar.title')}</h2>
          </div>
        )}
        <button
          onClick={() => dispatch({ type: 'TOGGLE_SIDEBAR' })}
          className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground"
        >
          <ChevronLeft className={`w-3.5 h-3.5 transition-transform ${state.sidebarCollapsed ? 'rotate-180' : ''}`} />
        </button>
      </div>

      <nav className="p-2 flex-1 overflow-y-auto min-h-0">
        {navigationItems.map((item) => {
          const Icon = item.icon;
          const isExpanded = state.expandedNavigationItems.includes(item.id);
          const buttonRef = getButtonRef(item.id);

          return (
            <div key={item.id}>
              <button
                ref={buttonRef}
                onClick={(e) => handleNavigationClick(e, item)}
                onMouseEnter={() => handleMouseEnter(item, buttonRef)}
                onMouseLeave={handleMouseLeave}
                className={`w-full flex items-center rounded-lg mb-1 transition-colors ${state.sidebarCollapsed ? 'justify-center p-2' : 'p-2'
                  } ${state.currentFeature === item.id
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
                    : 'hover:bg-sidebar-accent text-sidebar-foreground'
                  }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                {!state.sidebarCollapsed && (
                  <>
                    <span className="ml-2 text-sm text-left flex-1">{t(item.labelKey)}</span>
                    {item.hasSubMenu && (
                      <ChevronDown className={`w-3.5 h-3.5 flex-shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''
                        }`} />
                    )}
                  </>
                )}
              </button>

              {/* 子選單 */}
              {item.hasSubMenu && item.subItems && !state.sidebarCollapsed && isExpanded && (
                <div className="ml-7 space-y-0.5 mb-1">
                  {item.subItems.map((subItem) => (
                    (() => {
                      const count = getSubItemCount(item.id, subItem.id);
                      return (
                        <button
                          key={subItem.id}
                          onClick={() => handleSubItemClick(item.id, subItem.id)}
                          className={`w-full flex items-center p-1.5 rounded text-sm hover:bg-sidebar-accent ${isSubItemActive(item, subItem)
                            ? 'bg-sidebar-accent text-sidebar-foreground font-medium'
                            : 'text-sidebar-foreground'
                            }`}
                        >
                          <subItem.icon className="w-3.5 h-3.5 mr-1.5 flex-shrink-0" />
                          <span className="text-left flex-1">{t(subItem.labelKey)}</span>
                          {count !== null ? (
                            <span className="ml-2 min-w-5 rounded-full bg-muted px-1.5 py-0.5 text-[11px] leading-none text-muted-foreground">
                              {count}
                            </span>
                          ) : null}
                        </button>
                      );
                    })()
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* 收折狀態下的彈出式子選單 */}
      {state.sidebarCollapsed && hoverMenuItem && hoverMenuItem.item.hasSubMenu && hoverMenuItem.item.subItems && (
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
            {/* 顯示主項目標題 */}
            <div className="px-2 py-1.5 border-b border-border mb-1">
              <div className="flex items-center gap-2 text-sm font-medium">
                <hoverMenuItem.item.icon className="w-4 h-4" />
                <span>{t(hoverMenuItem.item.labelKey)}</span>
              </div>
            </div>
            {/* 子選單項目 */}
            <div className="space-y-0.5">
              {hoverMenuItem.item.subItems.map((subItem) => {
                const isActive = isSubItemActive(hoverMenuItem.item, subItem);
                const count = getSubItemCount(hoverMenuItem.item.id, subItem.id);

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
                    {count !== null ? (
                      <span className="ml-2 min-w-5 rounded-full bg-muted px-1.5 py-0.5 text-[11px] leading-none text-muted-foreground">
                        {count}
                      </span>
                    ) : null}
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

export default WorkspaceSidebar;
