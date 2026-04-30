import React from 'react';
import Editor, { loader, type EditorProps } from '@monaco-editor/react';
import type { SupportedLanguage } from '@/app/providers/I18nProvider';
import { useI18n } from '@/shared/hooks/useI18n';

const readFallbackLanguage = (): SupportedLanguage => {
  if (typeof document !== 'undefined' && document.documentElement.lang === 'zh-TW') {
    return 'zh-TW';
  }
  if (typeof window !== 'undefined' && window.localStorage.getItem('preferred-language') === 'zh-TW') {
    return 'zh-TW';
  }
  return 'en';
};

export const configureMonacoLocale = (language: SupportedLanguage): void => {
  try {
    loader.config({
      'vs/nls': {
        availableLanguages: {
          '*': language === 'zh-TW' ? 'zh-tw' : 'en',
        },
      },
    });
  } catch {
    // Test mocks can replace the editor component without exposing the loader.
  }
};

export const LocalizedMonacoEditor: React.FC<EditorProps> = (props) => {
  const { state } = useI18n();
  const currentLanguage = state?.currentLanguage ?? readFallbackLanguage();

  configureMonacoLocale(currentLanguage);

  return <Editor {...props} />;
};
