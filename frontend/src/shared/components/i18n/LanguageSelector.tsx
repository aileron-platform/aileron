/**
 * LanguageSelector - 語言切換器
 * 
 * 提供語言切換功能
 */

import React from 'react';
import { useI18n } from '../../../app/providers/I18nProvider';

export const LanguageSelector: React.FC = () => {
  const { state, changeLanguage } = useI18n();

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <select
        value={state.currentLanguage}
        onChange={(e) => changeLanguage(e.target.value as any)}
        className="px-2 py-1 text-xs border rounded bg-background"
      >
        {state.availableLanguages.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.flag} {lang.nativeName}
          </option>
        ))}
      </select>
    </div>
  );
};

export default LanguageSelector;
