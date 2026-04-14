/**
 * 程式碼編輯器組件
 * 為單個檔案提供獨立的編輯器實例
 */

import React, { useRef, useMemo, useEffect, forwardRef, useImperativeHandle } from 'react';
import Editor, { OnMount, OnChange } from '@monaco-editor/react';
import { dispatchAddCodeReferenceEvent } from '../../../components/ChatPanel/chatEvents';
import { FileText } from 'lucide-react';
import { useApp } from '@/app/providers/AppProvider';
import { getLanguageFromFileName } from '@/shared/utils/languageUtils';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('CodeEditor');

export interface CodeEditorRef {
  undo: () => void;
  redo: () => void;
  getEditor: () => any;
}

interface CodeEditorProps {
  filePath: string;
  fileName: string;
  content: string;
  visible: boolean;
  onContentChange: (content: string) => void;
  onModifiedChange: (isModified: boolean) => void;
  originalContent: string;
}



export const CodeEditor = forwardRef<CodeEditorRef, CodeEditorProps>(({
  filePath,
  fileName,
  content,
  visible,
  onContentChange,
  onModifiedChange,
  originalContent,
}, ref) => {
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const lastSelectionRef = useRef<string | null>(null);
  const { state } = useApp();

  // 暴露 undo/redo 方法給父組件
  useImperativeHandle(ref, () => ({
    undo: () => {
      editorRef.current?.trigger('keyboard', 'undo', null);
    },
    redo: () => {
      editorRef.current?.trigger('keyboard', 'redo', null);
    },
    getEditor: () => editorRef.current,
  }), []);

  // 檢測是否為二進位檔案或大檔案
  const isBinaryOrLargeFile = useMemo(() => {
    return content.includes('Binary file:') ||
      content.includes('Large text file:') ||
      content.includes('(Binary files cannot be displayed') ||
      content.includes('(File too large to display');
  }, [content]);

  // 處理編輯器掛載
  const handleEditorDidMount: OnMount = (editor, monaco) => {
    try {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // 監聽選取範圍變更
      editor.onDidChangeCursorSelection((e) => {
        try {
          const selection = e.selection;
          if (!selection.isEmpty()) {
            const fromLine = selection.startLineNumber;
            const toLine = selection.endLineNumber;
            const referenceKey = `${filePath}:${fromLine}-${toLine}`;

            if (lastSelectionRef.current !== referenceKey) {
              lastSelectionRef.current = referenceKey;
              dispatchAddCodeReferenceEvent({
                filePath,
                fileName,
                startLine: fromLine,
                endLine: toLine,
              });
            }
          } else {
            lastSelectionRef.current = null;
          }
        } catch (error) {
          logger.error('處理選取範圍變更時發生錯誤', { error });
        }
      });
    } catch (error) {
      logger.error('Monaco Editor 初始化失敗', { error });
    }
  };

  // 處理內容變更
  const handleEditorChange: OnChange = (value) => {
    try {
      const newContent = value || '';
      onContentChange(newContent);

      // 檢查是否修改
      const isModified = newContent !== originalContent;
      onModifiedChange(isModified);
    } catch (error) {
      logger.error('處理內容變更時發生錯誤', { error });
    }
  };

  // 確定主題 - 使用 AppProvider 的 currentTheme
  const currentTheme = useMemo(() => {
    return state.ui.currentTheme === 'dark' ? 'vs-dark' : 'vs';
  }, [state.ui.currentTheme]);

  // 如果是二進位檔案或大檔案，顯示提示訊息
  if (isBinaryOrLargeFile) {
    return (
      <div
        className="w-full h-full flex items-center justify-center p-8"
        style={{ display: visible ? 'flex' : 'none' }}
      >
        <div className="text-center max-w-2xl">
          <FileText className="w-12 h-12 mx-auto mb-4 opacity-50 text-muted-foreground" />
          <div className="text-sm text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 p-4 rounded-lg">
            {content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="w-full h-full"
      style={{ display: visible ? 'block' : 'none' }}
    >
      <Editor
        height="100%"
        language={getLanguageFromFileName(fileName)}
        value={content}
        theme={currentTheme}
        onMount={handleEditorDidMount}
        onChange={handleEditorChange}
        options={{
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
});

CodeEditor.displayName = 'CodeEditor';
