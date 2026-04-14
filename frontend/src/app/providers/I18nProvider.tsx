/**
 * I18nProvider - 國際化狀態管理
 * 
 * 提供多語系支援，包含：
 * - 語言切換
 * - 翻譯資源載入
 * - 動態語言切換
 * - 類型安全的翻譯函數
 */

import React, { createContext, useContext, useReducer, ReactNode, useEffect } from 'react';
import zhTWTranslations from '../../shared/locales/zh-TW/index';
import enTranslations from '../../shared/locales/en/index';
import { createLogger } from '@/shared/services/logger';
import { registerLanguageProvider } from '@/shared/api/apiClient';

const logger = createLogger('I18nProvider');

// 支援的語言類型
export type SupportedLanguage = 'zh-TW' | 'en';

// 翻譯資源類型
export interface TranslationResources {
  [key: string]: string | TranslationResources;
}

// 語言配置
export interface LanguageConfig {
  code: SupportedLanguage;
  name: string;
  nativeName: string;
  flag: string;
}

// 國際化狀態
export interface I18nState {
  currentLanguage: SupportedLanguage;
  availableLanguages: LanguageConfig[];
  translations: Record<SupportedLanguage, TranslationResources>;
  isLoading: boolean;
  loadedLanguages: SupportedLanguage[];
}

// Action 類型定義
export type I18nAction =
  | { type: 'SET_LANGUAGE'; payload: SupportedLanguage }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'LOAD_TRANSLATIONS'; payload: { language: SupportedLanguage; translations: TranslationResources } }
  | { type: 'ADD_LOADED_LANGUAGE'; payload: SupportedLanguage };

// 可用語言配置
const availableLanguages: LanguageConfig[] = [
  {
    code: 'zh-TW',
    name: 'Traditional Chinese',
    nativeName: '繁體中文',
    flag: '🇹🇼',
  },
  {
    code: 'en',
    name: 'English',
    nativeName: 'English',
    flag: '🇺🇸',
  },
];

// 初始狀態
const initialState: I18nState = {
  currentLanguage: 'en',
  availableLanguages,
  translations: {
    'zh-TW': zhTWTranslations,
    'en': enTranslations,
  },
  isLoading: false,
  loadedLanguages: ['zh-TW', 'en'],
};

// Reducer 函數
const i18nReducer = (state: I18nState, action: I18nAction): I18nState => {
  switch (action.type) {
    case 'SET_LANGUAGE':
      return {
        ...state,
        currentLanguage: action.payload,
      };
      
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
      };
      
    case 'LOAD_TRANSLATIONS':
      return {
        ...state,
        translations: {
          ...state.translations,
          [action.payload.language]: action.payload.translations,
        },
      };
      
    case 'ADD_LOADED_LANGUAGE':
      return {
        ...state,
        loadedLanguages: [...state.loadedLanguages, action.payload],
      };
      
    default:
      return state;
  }
};

interface TranslationParams extends Record<string, string | number> {
  defaultValue?: string;
}

// Context 類型定義
interface I18nContextType {
  state: I18nState;
  dispatch: React.Dispatch<I18nAction>;
  t: (key: string, params?: TranslationParams) => string;
  changeLanguage: (language: SupportedLanguage) => Promise<void>;
  loadLanguage: (language: SupportedLanguage) => Promise<void>;
}

// Context 建立
const I18nContext = createContext<I18nContextType | undefined>(undefined);

// Provider 組件
interface I18nProviderProps {
  children: ReactNode;
}

export const I18nProvider: React.FC<I18nProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(i18nReducer, initialState);

  useEffect(() => {
    registerLanguageProvider(() => state.currentLanguage);

    return () => {
      registerLanguageProvider(null);
    };
  }, [state.currentLanguage]);

  // 翻譯函數
  const t = (key: string, params?: TranslationParams): string => {
    const translations = state.translations[state.currentLanguage];
    const { defaultValue, ...interpolationParams } = params ?? {};
    const value = resolveTranslationValue(
      translations,
      key,
      interpolationParams,
      defaultValue,
    );

    if (typeof value === 'string') {
      if (interpolationParams && Object.keys(interpolationParams).length > 0) {
        return Object.entries(interpolationParams).reduce(
          (str, [paramKey, paramValue]) => {
            return str.replace(
              new RegExp(`{{${paramKey}}}`, 'g'),
              String(paramValue),
            );
          },
          value,
        );
      }
      return value;
    }

    if (typeof defaultValue === 'string') {
      if (interpolationParams && Object.keys(interpolationParams).length > 0) {
        return Object.entries(interpolationParams).reduce(
          (str, [paramKey, paramValue]) => {
            return str.replace(
              new RegExp(`{{${paramKey}}}`, 'g'),
              String(paramValue),
            );
          },
          defaultValue,
        );
      }
      return defaultValue;
    }

    logger.warn(`Translation not found for key`, { key });
    return key;
  };

  const resolveTranslationValue = (
    translations: TranslationResources,
    key: string,
    params?: Record<string, string | number>,
    defaultValue?: string
  ): string | TranslationResources | undefined => {
    const directValue = getNestedValue(translations, key);

    if (typeof directValue === 'string') {
      return directValue;
    }

    if (params?.count !== undefined) {
      const count = Number(params.count);
      const pluralKey = `${key}_${getPluralSuffix(state.currentLanguage, count)}`;
      const pluralValue = getNestedValue(translations, pluralKey);

      if (typeof pluralValue === 'string') {
        return pluralValue;
      }

      if (!pluralKey.endsWith('_other')) {
        const fallbackPluralValue = getNestedValue(translations, `${key}_other`);
        if (typeof fallbackPluralValue === 'string') {
          return fallbackPluralValue;
        }
      }
    }

    if (typeof defaultValue === 'string') {
      return defaultValue;
    }

    return directValue;
  };

  const getPluralSuffix = (language: SupportedLanguage, count: number): 'one' | 'other' => {
    if (language === 'en') {
      return count === 1 ? 'one' : 'other';
    }
    return 'other';
  };

  // 獲取嵌套物件的值
  const getNestedValue = (obj: TranslationResources, path: string): string | TranslationResources => {
    return path.split('.').reduce((current, key) => {
      return current && typeof current === 'object' ? current[key] : undefined;
    }, obj) as string | TranslationResources;
  };

  // 載入語言資源（現在使用預載入的翻譯）
  const loadLanguage = async (language: SupportedLanguage): Promise<void> => {
    if (state.loadedLanguages.includes(language)) {
      return;
    }

    dispatch({ type: 'SET_LOADING', payload: true });

    try {
      // 使用預載入的翻譯資源
      const translationsMap = {
        'zh-TW': zhTWTranslations,
        'en': enTranslations,
      };

      dispatch({
        type: 'LOAD_TRANSLATIONS',
        payload: {
          language,
          translations: translationsMap[language],
        },
      });

      dispatch({ type: 'ADD_LOADED_LANGUAGE', payload: language });
    } catch (error) {
      logger.error('Failed to load language', { language, error });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  // 切換語言
  const changeLanguage = async (language: SupportedLanguage): Promise<void> => {
    // 先載入語言資源
    await loadLanguage(language);
    
    // 切換語言
    dispatch({ type: 'SET_LANGUAGE', payload: language });
    
    // 儲存到 localStorage
    localStorage.setItem('preferred-language', language);
    
    // 更新 HTML lang 屬性
    document.documentElement.lang = language;
  };

  // 初始化載入預設語言
  useEffect(() => {
    const initializeLanguage = async () => {
      // 從 localStorage 讀取偏好語言
      const savedLanguage = localStorage.getItem('preferred-language') as SupportedLanguage;
      const initialLanguage = savedLanguage || 'en';
      
      await loadLanguage(initialLanguage);
      dispatch({ type: 'SET_LANGUAGE', payload: initialLanguage });
      document.documentElement.lang = initialLanguage;
    };

    initializeLanguage();
  }, []);

  const contextValue: I18nContextType = {
    state,
    dispatch,
    t,
    changeLanguage,
    loadLanguage,
  };

  return (
    <I18nContext.Provider value={contextValue}>
      {children}
    </I18nContext.Provider>
  );
};

// Hook for using i18n context
export const useI18n = (): I18nContextType => {
  const context = useContext(I18nContext);
  if (context === undefined) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
};

export default I18nProvider;
