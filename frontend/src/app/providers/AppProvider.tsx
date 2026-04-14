/**
 * AppProvider - 應用程式全域狀態管理
 * 
 * 提供應用程式層級的狀態管理，包含：
 * - 使用者狀態
 * - 系統設定
 * - 主題管理
 * - 全域 UI 狀態
 */

import React, { createContext, useContext, useReducer, ReactNode, useEffect } from 'react';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('AppProvider');

// 應用程式狀態類型定義
export interface AppState {
  // 使用者狀態
  user: {
    id: string | null;
    name: string | null;
    email: string | null;
    preferences: {
      theme: 'light' | 'dark' | 'system';
      language: 'zh-TW' | 'en';
    };
  };
  
  // 系統狀態
  system: {
    isLoading: boolean;
    notifications: Notification[];
    errors: Error[];
  };
  
  // UI 狀態
  ui: {
    sidebarCollapsed: boolean;
    currentTheme: 'light' | 'dark';
  };
}

// 通知類型
export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: Date;
  autoClose?: boolean;
}

// 錯誤類型
export interface Error {
  id: string;
  message: string;
  stack?: string;
  timestamp: Date;
}

// Action 類型定義
export type AppAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_THEME'; payload: 'light' | 'dark' | 'system' }
  | { type: 'SET_RESOLVED_THEME'; payload: 'light' | 'dark' }
  | { type: 'SET_LANGUAGE'; payload: 'zh-TW' | 'en' }
  | { type: 'TOGGLE_SIDEBAR' }
  | {
      type: 'SET_USER_INFO';
      payload:
        | {
            id: string;
            name: string | null;
            email: string | null;
          }
        | null;
    }
  | { type: 'ADD_NOTIFICATION'; payload: Omit<Notification, 'id' | 'timestamp'> }
  | { type: 'REMOVE_NOTIFICATION'; payload: string }
  | { type: 'ADD_ERROR'; payload: Omit<Error, 'id' | 'timestamp'> }
  | { type: 'CLEAR_ERRORS' };

// 初始狀態
const initialState: AppState = {
  user: {
    id: null,
    name: null,
    email: null,
    preferences: {
      theme: 'system',
      language: 'en',
    },
  },
  system: {
    isLoading: false,
    notifications: [],
    errors: [],
  },
  ui: {
    sidebarCollapsed: false,
    currentTheme: 'light',
  },
};

// Reducer 函數
const appReducer = (state: AppState, action: AppAction): AppState => {
  switch (action.type) {
    case 'SET_LOADING':
      return {
        ...state,
        system: {
          ...state.system,
          isLoading: action.payload,
        },
      };
      
    case 'SET_THEME':
      return {
        ...state,
        user: {
          ...state.user,
          preferences: {
            ...state.user.preferences,
            theme: action.payload,
          },
        },
      };

    case 'SET_RESOLVED_THEME':
      return {
        ...state,
        ui: {
          ...state.ui,
          currentTheme: action.payload,
        },
      };
      
    case 'SET_LANGUAGE':
      return {
        ...state,
        user: {
          ...state.user,
          preferences: {
            ...state.user.preferences,
            language: action.payload,
          },
        },
      };

    case 'SET_USER_INFO':
      return {
        ...state,
        user: {
          ...state.user,
          id: action.payload ? action.payload.id : null,
          name: action.payload ? action.payload.name : null,
          email: action.payload ? action.payload.email : null,
        },
      };
      
    case 'TOGGLE_SIDEBAR':
      return {
        ...state,
        ui: {
          ...state.ui,
          sidebarCollapsed: !state.ui.sidebarCollapsed,
        },
      };
      
    case 'ADD_NOTIFICATION':
      const notification: Notification = {
        ...action.payload,
        id: Date.now().toString(),
        timestamp: new Date(),
      };
      return {
        ...state,
        system: {
          ...state.system,
          notifications: [...state.system.notifications, notification],
        },
      };
      
    case 'REMOVE_NOTIFICATION':
      return {
        ...state,
        system: {
          ...state.system,
          notifications: state.system.notifications.filter(n => n.id !== action.payload),
        },
      };
      
    case 'ADD_ERROR':
      const error: Error = {
        ...action.payload,
        id: Date.now().toString(),
        timestamp: new Date(),
      };
      return {
        ...state,
        system: {
          ...state.system,
          errors: [...state.system.errors, error],
        },
      };
      
    case 'CLEAR_ERRORS':
      return {
        ...state,
        system: {
          ...state.system,
          errors: [],
        },
      };
      
    default:
      return state;
  }
};

// Context 類型定義
interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

// Context 建立
const AppContext = createContext<AppContextType | undefined>(undefined);

// Provider 組件
interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  // 初始化狀態時從 localStorage 載入設定
  const getInitialState = (): AppState => {
    if (typeof window === 'undefined') {
      return initialState;
    }

    try {
      const storedSettings = window.localStorage.getItem('mw.settings.general');
      if (!storedSettings) {
        return initialState;
      }

      const parsedSettings = JSON.parse(storedSettings) as {
        theme?: 'light' | 'dark' | 'system';
        language?: 'zh-TW' | 'en';
      };

      return {
        ...initialState,
        user: {
          ...initialState.user,
          preferences: {
            theme: parsedSettings.theme || initialState.user.preferences.theme,
            language: parsedSettings.language || initialState.user.preferences.language,
          },
        },
      };
    } catch (error) {
      logger.error('載入使用者偏好設定時發生錯誤', { error });
      return initialState;
    }
  };

  const [state, dispatch] = useReducer(appReducer, getInitialState());
  const { isAuthenticated, isLoading, user: authUser } = useAuth();

  useEffect(() => {
    if (isAuthenticated && authUser) {
      // 呼叫 /oauth2/me 取得 local DB user ID
      import('@/shared/api/apiClient').then(({ apiClient }) => {
        apiClient.get<{ sub: string; preferred_username: string; email?: string; local_user_id?: string }>('/oauth2/me')
          .then((me) => {
            const nextUserInfo = {
              id: me.local_user_id ?? me.sub,
              name: authUser.name ?? authUser.preferred_username ?? authUser.email,
              email: me.email ?? authUser.email,
            };
            if (
              state.user.id !== nextUserInfo.id ||
              state.user.name !== nextUserInfo.name ||
              state.user.email !== nextUserInfo.email
            ) {
              dispatch({ type: 'SET_USER_INFO', payload: nextUserInfo });
            }
          })
          .catch(() => {
            // fallback：直接用 Keycloak sub
            const nextUserInfo = {
              id: authUser.sub,
              name: authUser.name ?? authUser.preferred_username ?? authUser.email,
              email: authUser.email,
            };
            if (
              state.user.id !== nextUserInfo.id ||
              state.user.name !== nextUserInfo.name ||
              state.user.email !== nextUserInfo.email
            ) {
              dispatch({ type: 'SET_USER_INFO', payload: nextUserInfo });
            }
          });
      });
      return;
    }

    if (!isLoading && !isAuthenticated) {
      if (state.user.id !== null || state.user.name !== null || state.user.email !== null) {
        dispatch({ type: 'SET_USER_INFO', payload: null });
      }
    }
  // 注意：deps 不包含 state.user.* 欄位，避免 dispatch 後觸發重複 API 呼叫
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authUser, dispatch, isAuthenticated, isLoading]);

  // 監聽偏好設定變化並同步到 localStorage
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      const settingsToStore = {
        theme: state.user.preferences.theme,
        language: state.user.preferences.language,
      };
      window.localStorage.setItem('mw.settings.general', JSON.stringify(settingsToStore));
    } catch (error) {
      logger.error('儲存使用者偏好設定時發生錯誤', { error });
    }
  }, [state.user.preferences.theme, state.user.preferences.language]);

  // 監聽主題變化並套用到文件根節點
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const applyResolvedTheme = (resolved: 'light' | 'dark') => {
      const root = window.document.documentElement;
      const body = window.document.body;

      if (resolved === 'dark') {
        root.classList.add('dark');
        body.classList.add('dark');
      } else {
        root.classList.remove('dark');
        body.classList.remove('dark');
      }

      root.style.colorScheme = resolved;
      dispatch({ type: 'SET_RESOLVED_THEME', payload: resolved });
    };

    const resolveTheme = () =>
      state.user.preferences.theme === 'system'
        ? mediaQuery.matches
          ? 'dark'
          : 'light'
        : state.user.preferences.theme;

    const resolvedTheme = resolveTheme();
    applyResolvedTheme(resolvedTheme);

    if (state.user.preferences.theme !== 'system') {
      return;
    }

    const handleSystemThemeChange = (event: MediaQueryListEvent) => {
      applyResolvedTheme(event.matches ? 'dark' : 'light');
    };

    mediaQuery.addEventListener('change', handleSystemThemeChange);

    return () => {
      mediaQuery.removeEventListener('change', handleSystemThemeChange);
    };
  }, [state.user.preferences.theme, dispatch]);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
};

// Hook for using app context
export const useApp = (): AppContextType => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

export default AppProvider;
