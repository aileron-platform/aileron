import React, { createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from 'react';
import zhTWTranslations from '../locales/zh-TW/index';
import enTranslations from '../locales/en/index';
import { createLogger } from '@/shared/services/logger';
import type { SupportedLanguage } from '@/shared/types/i18n';
import { registerLanguageProvider } from '@/shared/api/apiClient';

const logger = createLogger('I18nProvider');

interface TranslationResources {
  [key: string]: string | TranslationResources;
}

interface I18nContextState {
  currentLanguage: SupportedLanguage;
}

const translations: Record<SupportedLanguage, TranslationResources> = {
  'zh-TW': zhTWTranslations,
  'en': enTranslations,
};

interface TranslationParams extends Record<string, string | number> {
  defaultValue?: string;
}

interface I18nContextType {
  state: I18nContextState;
  t: (key: string, params?: TranslationParams) => string;
  changeLanguage: (language: SupportedLanguage) => Promise<void>;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

const getPluralSuffix = (language: SupportedLanguage, count: number): 'one' | 'other' => {
  if (language === 'en') {
    return count === 1 ? 'one' : 'other';
  }
  return 'other';
};

const getNestedValue = (obj: TranslationResources, path: string): string | TranslationResources => {
  return path.split('.').reduce((current, key) => {
    return current && typeof current === 'object' ? current[key] : undefined;
  }, obj) as string | TranslationResources;
};

const resolveTranslationValue = (
  translations: TranslationResources,
  key: string,
  language: SupportedLanguage,
  params?: Record<string, string | number>,
  defaultValue?: string,
): string | TranslationResources | undefined => {
  const directValue = getNestedValue(translations, key);

  if (typeof directValue === 'string') {
    return directValue;
  }

  if (params?.count !== undefined) {
    const count = Number(params.count);
    const pluralKey = `${key}_${getPluralSuffix(language, count)}`;
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

const interpolateTranslation = (
  value: string,
  params?: Record<string, string | number>,
): string => {
  if (!params || Object.keys(params).length === 0) {
    return value;
  }

  return Object.entries(params).reduce(
    (str, [paramKey, paramValue]) => str.replace(
      new RegExp(`{{${paramKey}}}`, 'g'),
      String(paramValue),
    ),
    value,
  );
};

interface I18nProviderProps {
  children: ReactNode;
}

export const I18nProvider: React.FC<I18nProviderProps> = ({ children }) => {
  const [currentLanguage, setCurrentLanguage] = useState<SupportedLanguage>('en');

  useEffect(() => {
    registerLanguageProvider(() => currentLanguage);

    return () => {
      registerLanguageProvider(null);
    };
  }, [currentLanguage]);

  const t = useCallback((key: unknown, params?: TranslationParams): string => {
    const defaultValue = params?.defaultValue;
    if (typeof key !== 'string') {
      logger.warn('Translation key must be a string', { keyType: typeof key });
      return typeof defaultValue === 'string' ? defaultValue : '';
    }

    const currentTranslations = translations[currentLanguage];
    const { defaultValue: _, ...interpolationParams } = params ?? {};
    const value = resolveTranslationValue(
      currentTranslations,
      key,
      currentLanguage,
      interpolationParams,
      defaultValue,
    );

    if (typeof value === 'string') {
      return interpolateTranslation(value, interpolationParams);
    }

    if (typeof defaultValue === 'string') {
      return interpolateTranslation(defaultValue, interpolationParams);
    }

    logger.warn(`Translation not found for key: ${key}`);
    return key;
  }, [currentLanguage]);

  const changeLanguage = useCallback(async (language: SupportedLanguage): Promise<void> => {
    setCurrentLanguage(language);
    localStorage.setItem('preferred-language', language);
    document.documentElement.lang = language;
  }, []);

  useEffect(() => {
    const savedLanguage = localStorage.getItem('preferred-language') as SupportedLanguage;
    const initialLanguage = savedLanguage || 'en';

    setCurrentLanguage(initialLanguage);
    document.documentElement.lang = initialLanguage;
  }, []);

  const contextValue = useMemo<I18nContextType>(() => ({
    state: { currentLanguage },
    t,
    changeLanguage,
  }), [changeLanguage, currentLanguage, t]);

  return (
    <I18nContext.Provider value={contextValue}>
      {children}
    </I18nContext.Provider>
  );
};

export const useI18n = (): I18nContextType => {
  const context = useContext(I18nContext);
  if (context === undefined) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
};

export const useOptionalI18n = (): I18nContextType | undefined => useContext(I18nContext);
