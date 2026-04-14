import React, { useRef, useMemo } from 'react';
import { MarkdownEditor } from '@/shared/components/composite/MarkdownEditor';
import Editor, { OnMount, OnChange } from '@monaco-editor/react';
import { useApp } from '@/app/providers/AppProvider';
import { getLanguageFromFileName } from '@/shared/utils/languageUtils';
import { createLogger } from '@/shared/services/logger';
import { useI18n } from '@/shared/hooks/useI18n';

const logger = createLogger('TemplateFileEditor');

interface TemplateFileEditorProps {
  fileName: string;
  content: string;
  onChange: (content: string) => void;
  readOnly?: boolean;
  className?: string;
}



/**
 * 模板檔案編輯器
 * 根據檔案類型自動選擇合適的編輯器（Monaco Editor 或 MarkdownEditor）
 */
export const TemplateFileEditor: React.FC<TemplateFileEditorProps> = ({
  fileName,
  content,
  onChange,
  readOnly = false,
  className = '',
}) => {
  const editorRef = useRef<any>(null);
  const { state } = useApp();
  const { t } = useI18n();

  // 判斷是否為 Markdown 檔案
  const isMarkdown = fileName.toLowerCase().endsWith('.md') || fileName.toLowerCase().endsWith('.markdown');

  // 確定主題 - 使用 AppProvider 的 currentTheme
  const currentTheme = useMemo(() => {
    return state.ui.currentTheme === 'dark' ? 'vs-dark' : 'vs';
  }, [state.ui.currentTheme]);

  const handleEditorChange: OnChange = (value) => {
    try {
      onChange(value || '');
    } catch (error) {
      logger.error('處理內容變更時發生錯誤', { error });
    }
  };

  const handleEditorDidMount: OnMount = (editor) => {
    try {
      editorRef.current = editor;
    } catch (error) {
      logger.error('Monaco Editor 初始化失敗', { error });
    }
  };

  // Markdown 檔案使用 MarkdownEditor
  if (isMarkdown) {
    return (
      <div className={`h-full ${className}`}>
        <MarkdownEditor
          value={content}
          onChange={onChange}
          placeholder={t('template.editor.fileManagement.editor.markdownPlaceholder')}
          className="h-full border-0 rounded-none"
        />
      </div>
    );
  }

  // 其他檔案使用 Monaco Editor
  return (
    <div className={`h-full w-full ${className}`}>
      <Editor
        height="100%"
        language={getLanguageFromFileName(fileName)}
        value={content}
        theme={currentTheme}
        onMount={handleEditorDidMount}
        onChange={handleEditorChange}
        options={{
          readOnly: readOnly,
          minimap: { enabled: true },
          fontSize: 14,
          wordWrap: 'on',
          automaticLayout: true,
          scrollBeyondLastLine: false,
          fontFamily: 'var(--font-mono)',
        }}
      />
    </div>
  );
};

export default TemplateFileEditor;
