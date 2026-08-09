/**
 * 
 */

import React, { createContext, useContext, useReducer, ReactNode, useEffect } from 'react';
import { useAuth } from '@/features/auth/public';
import { createLogger } from '@/shared/services/logger';
import {
  ResolvedThemeProvider,
  type ResolvedTheme,
} from '@/shared/contexts/ResolvedThemeContext';

const logger = createLogger('AppProvider');

interface AppState {
  user: {
    id: string | null;
    name: string | null;
    email: string | null;
    preferences: {
      theme: 'light' | 'dark' | 'system';
      language: 'zh-TW' | 'en';
    };
  };
  
  system: {
    isLoading: boolean;
    notifications: Notification[];
    errors: Error[];
  };
  
  ui: {
    currentTheme: ResolvedTheme;
  };
}

interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: Date;
  autoClose?: boolean;
}

interface Error {
  id: string;
  message: string;
  stack?: string;
  timestamp: Date;
}

type AppAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_THEME'; payload: 'light' | 'dark' | 'system' }
  | { type: 'SET_RESOLVED_THEME'; payload: ResolvedTheme }
  | { type: 'SET_LANGUAGE'; payload: 'zh-TW' | 'en' }
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
    currentTheme: 'light',
  },
};

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

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
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
      logger.error('Failed to load user preferences', { error });
      return initialState;
    }
  };

  const [state, dispatch] = useReducer(appReducer, getInitialState());
  const { isAuthenticated, isLoading, user: authUser } = useAuth();

  useEffect(() => {
    if (isLoading) {
      return;
    }

    const nextUserInfo = isAuthenticated && authUser
      ? {
          id: authUser.id,
          name: authUser.display_name ?? authUser.username,
          email: authUser.email,
        }
      : null;

    if (
      state.user.id !== (nextUserInfo?.id ?? null) ||
      state.user.name !== (nextUserInfo?.name ?? null) ||
      state.user.email !== (nextUserInfo?.email ?? null)
    ) {
      dispatch({ type: 'SET_USER_INFO', payload: nextUserInfo });
    }

  // state.user.* are intentionally omitted because this effect writes those values and
  // the in-body equality guard already prevents redundant dispatches.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authUser, dispatch, isAuthenticated, isLoading]);

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
      logger.error('Failed to save user preferences', { error });
    }
  }, [state.user.preferences.theme, state.user.preferences.language]);

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
      <ResolvedThemeProvider value={state.ui.currentTheme}>
        {children}
      </ResolvedThemeProvider>
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
