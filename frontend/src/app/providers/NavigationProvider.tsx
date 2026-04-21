/**
 * NavigationProvider - 導航狀態管理
 * 
 * 提供全域導航狀態管理，包含：
 * - 當前 Hub 和模組
 * - 導航歷史
 * - 麵包屑導航
 * - 側邊欄狀態
 */

import React, { createContext, useContext, useReducer, ReactNode, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { createLogger } from '@/shared/services/logger';
import { ROUTES } from '@/shared/constants/routes';

const logger = createLogger('NavigationProvider');

// 導航項目類型
export interface NavigationItem {
  id: string;
  label: string;
  path: string;
  icon?: React.ComponentType;
  parentId?: string;
  children?: NavigationItem[];
}

// 模組類型
export type ModuleType = 'workspace' | 'template' | 'automation';

// 導航狀態
export interface NavigationState {
  currentModule: ModuleType;
  currentPath: string;
  breadcrumbs: NavigationItem[];
  history: string[];
  historyIndex: number;
  sidebarExpanded: boolean;
  navigationItems: NavigationItem[];
  selectedWorkspaceId: string | null;
}

// Action 類型定義
export type NavigationAction =
  | { type: 'SET_CURRENT_MODULE'; payload: ModuleType }
  | { type: 'SET_CURRENT_PATH'; payload: string }
  | { type: 'SET_BREADCRUMBS'; payload: NavigationItem[] }
  | { type: 'TOGGLE_SIDEBAR' }
  | { type: 'SET_SIDEBAR_EXPANDED'; payload: boolean }
  | { type: 'SET_NAVIGATION_ITEMS'; payload: NavigationItem[] }
  | { type: 'SET_SELECTED_WORKSPACE'; payload: string | null }
  | { type: 'SYNC_HISTORY'; payload: { path: string; mode: 'push' | 'external' } }
  | { type: 'SET_HISTORY_INDEX'; payload: number };

// localStorage 鍵名
const SELECTED_WORKSPACE_KEY = 'selectedWorkspaceId';

// 從 localStorage 讀取已儲存的工作區 ID
const loadSelectedWorkspaceId = (): string | null => {
  try {
    const saved = localStorage.getItem(SELECTED_WORKSPACE_KEY);
    return saved || null;
  } catch (error) {
    logger.error('Failed to load selected workspace from localStorage', { error });
    return null;
  }
};

// 將工作區 ID 儲存到 localStorage
const saveSelectedWorkspaceId = (workspaceId: string | null): void => {
  try {
    if (workspaceId) {
      localStorage.setItem(SELECTED_WORKSPACE_KEY, workspaceId);
    } else {
      localStorage.removeItem(SELECTED_WORKSPACE_KEY);
    }
  } catch (error) {
    logger.error('Failed to save selected workspace to localStorage', { error });
  }
};

// 初始狀態
const initialState: NavigationState = {
  currentModule: 'workspace',
  currentPath: '/workspaces',
  breadcrumbs: [],
  history: ['/workspaces'],
  historyIndex: 0,
  sidebarExpanded: true,
  navigationItems: [],
  selectedWorkspaceId: loadSelectedWorkspaceId(),
};

const HISTORY_LIMIT = 50;

const pushHistoryEntry = (state: NavigationState, path: string) => {
  const baseHistory =
    state.historyIndex >= 0
      ? state.history.slice(0, state.historyIndex + 1)
      : [];

  if (baseHistory.length > 0 && baseHistory[baseHistory.length - 1] === path) {
    return {
      history: baseHistory,
      historyIndex: baseHistory.length - 1,
    };
  }

  const nextHistory = [...baseHistory, path];
  while (nextHistory.length > HISTORY_LIMIT) {
    nextHistory.shift();
  }

  return {
    history: nextHistory,
    historyIndex: nextHistory.length - 1,
  };
};

// Reducer 函數
const navigationReducer = (state: NavigationState, action: NavigationAction): NavigationState => {
  switch (action.type) {
    case 'SET_CURRENT_MODULE':
      return {
        ...state,
        currentModule: action.payload,
      };
      
    case 'SET_CURRENT_PATH':
      return {
        ...state,
        currentPath: action.payload,
      };
      
    case 'SYNC_HISTORY': {
      if (action.payload.mode === 'external') {
        const existingIndex = state.history.indexOf(action.payload.path);
        if (existingIndex !== -1) {
          return {
            ...state,
            historyIndex: existingIndex,
          };
        }
      }

      const { history, historyIndex } = pushHistoryEntry(state, action.payload.path);
      return {
        ...state,
        history,
        historyIndex,
      };
    }

    case 'SET_HISTORY_INDEX': {
      const clampedIndex = Math.max(0, Math.min(action.payload, state.history.length - 1));
      return {
        ...state,
        historyIndex: clampedIndex,
      };
    }
      
    case 'SET_BREADCRUMBS':
      return {
        ...state,
        breadcrumbs: action.payload,
      };
      
    case 'TOGGLE_SIDEBAR':
      return {
        ...state,
        sidebarExpanded: !state.sidebarExpanded,
      };
      
    case 'SET_SIDEBAR_EXPANDED':
      return {
        ...state,
        sidebarExpanded: action.payload,
      };
      
    case 'SET_NAVIGATION_ITEMS':
      return {
        ...state,
        navigationItems: action.payload,
      };

    case 'SET_SELECTED_WORKSPACE':
      // 儲存到 localStorage
      saveSelectedWorkspaceId(action.payload);
      return {
        ...state,
        selectedWorkspaceId: action.payload,
      };

    default:
      return state;
  }
};

// Context 類型定義
interface NavigationContextType {
  state: NavigationState;
  dispatch: React.Dispatch<NavigationAction>;
  navigateTo: (path: string, module?: ModuleType) => void;
  goBack: () => void;
  goForward: () => void;
  updateBreadcrumbs: (items: NavigationItem[]) => void;
  toggleSidebar: () => void;
}

// Context 建立
const NavigationContext = createContext<NavigationContextType | undefined>(undefined);

// Provider 組件
interface NavigationProviderProps {
  children: ReactNode;
}

export const NavigationProvider: React.FC<NavigationProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(navigationReducer, initialState);
  const navigate = useNavigate();
  const location = useLocation();
  const pendingNavigation = useRef<{ mode: 'push' | 'restore'; targetIndex?: number } | null>(null);

  // 導航到指定路徑
  const navigateTo = (path: string, module?: ModuleType) => {
    if (!path) {
      return;
    }

    if (path === state.currentPath) {
      if (module && state.currentModule !== module) {
        dispatch({ type: 'SET_CURRENT_MODULE', payload: module });
      }
      return;
    }

    pendingNavigation.current = { mode: 'push' };
    navigate(path);
    dispatch({ type: 'SET_CURRENT_PATH', payload: path });

    if (module && state.currentModule !== module) {
      dispatch({ type: 'SET_CURRENT_MODULE', payload: module });
    }
  };

  // 返回上一頁
  const goBack = () => {
    if (state.historyIndex <= 0) {
      return;
    }

    const targetIndex = state.historyIndex - 1;
    const targetPath = state.history[targetIndex];
    if (!targetPath) {
      return;
    }

    pendingNavigation.current = { mode: 'restore', targetIndex };
    navigate(targetPath);
  };

  // 前進到下一頁
  const goForward = () => {
    if (state.historyIndex >= state.history.length - 1) {
      return;
    }

    const targetIndex = state.historyIndex + 1;
    const targetPath = state.history[targetIndex];
    if (!targetPath) {
      return;
    }

    pendingNavigation.current = { mode: 'restore', targetIndex };
    navigate(targetPath);
  };

  // 更新麵包屑
  const updateBreadcrumbs = (items: NavigationItem[]) => {
    dispatch({ type: 'SET_BREADCRUMBS', payload: items });
  };

  // 切換側邊欄
  const toggleSidebar = () => {
    dispatch({ type: 'TOGGLE_SIDEBAR' });
  };

  // 監聽路由變化
  React.useEffect(() => {
    dispatch({ type: 'SET_CURRENT_PATH', payload: location.pathname });

    const pending = pendingNavigation.current;
    if (pending?.mode === 'push') {
      dispatch({ type: 'SYNC_HISTORY', payload: { path: location.pathname, mode: 'push' } });
    } else if (pending?.mode === 'restore' && typeof pending.targetIndex === 'number') {
      dispatch({ type: 'SET_HISTORY_INDEX', payload: pending.targetIndex });
    } else {
      dispatch({ type: 'SYNC_HISTORY', payload: { path: location.pathname, mode: 'external' } });
    }
    pendingNavigation.current = null;

    // 根據路徑判斷當前模組
    if (
      location.pathname === ROUTES.TEMPLATE_MANAGEMENT ||
      location.pathname.startsWith(`${ROUTES.TEMPLATE_MANAGEMENT}/`)
    ) {
      dispatch({ type: 'SET_CURRENT_MODULE', payload: 'template' });
    } else if (
      location.pathname === ROUTES.AUTOMATION ||
      location.pathname.startsWith(`${ROUTES.AUTOMATION}/`)
    ) {
      dispatch({ type: 'SET_CURRENT_MODULE', payload: 'automation' });
    } else {
      dispatch({ type: 'SET_CURRENT_MODULE', payload: 'workspace' });
    }
  }, [location.pathname]);

  const contextValue: NavigationContextType = {
    state,
    dispatch,
    navigateTo,
    goBack,
    goForward,
    updateBreadcrumbs,
    toggleSidebar,
  };

  return (
    <NavigationContext.Provider value={contextValue}>
      {children}
    </NavigationContext.Provider>
  );
};

// Hook for using navigation context
export const useNavigation = (): NavigationContextType => {
  const context = useContext(NavigationContext);
  if (context === undefined) {
    throw new Error('useNavigation must be used within a NavigationProvider');
  }
  return context;
};

export default NavigationProvider;
