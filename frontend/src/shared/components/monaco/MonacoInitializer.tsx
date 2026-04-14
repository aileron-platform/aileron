import React, { useEffect } from 'react';
import { loader } from '@monaco-editor/react';
import { useI18n } from '../../hooks/useI18n';

/**
 * MonacoInitializer - Monaco Editor 初始化組件
 * 
 * 負責配置 Monaco Editor 的全域設定，例如：
 * - 語言/地區設定 (Localization)
 * - CDN 配置 (如果有需要)
 */
export const MonacoInitializer: React.FC = () => {
    const { state } = useI18n();
    const { currentLanguage } = state;

    useEffect(() => {
        // 映射應用程式語言代碼到 Monaco Editor 支援的語言代碼
        // Monaco 使用 'zh-tw' 而不是 'zh-TW'
        const monacoLocale = currentLanguage === 'zh-TW' ? 'zh-tw' : 'en';

        // 配置 Monaco Editor 的載入器
        loader.config({
            // 指定語言
            'vs/nls': {
                availableLanguages: {
                    '*': monacoLocale,
                },
            },
        });
    }, [currentLanguage]);

    // 此組件不渲染任何 UI
    return null;
};
