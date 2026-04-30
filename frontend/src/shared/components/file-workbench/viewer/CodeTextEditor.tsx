import React, { forwardRef, useImperativeHandle, useMemo, useRef } from 'react';
import Editor, { type OnChange, type OnMount } from '@monaco-editor/react';
import { FileText } from 'lucide-react';
import { useApp } from '@/app/providers/AppProvider';
import { getLanguageFromFileName } from '@/shared/utils/languageUtils';

export interface CodeTextEditorRef {
  undo: () => void;
  redo: () => void;
  getEditor: () => unknown;
}

interface CodeTextEditorProps {
  fileName: string;
  content: string;
  originalContent: string;
  readOnly?: boolean;
  visible?: boolean;
  onContentChange: (content: string) => void;
  onModifiedChange: (isModified: boolean) => void;
}

export const CodeTextEditor = forwardRef<CodeTextEditorRef, CodeTextEditorProps>(({
  fileName,
  content,
  originalContent,
  readOnly = false,
  visible = true,
  onContentChange,
  onModifiedChange,
}, ref) => {
  const editorRef = useRef<any>(null);
  const { state } = useApp();

  useImperativeHandle(ref, () => ({
    undo: () => editorRef.current?.trigger('keyboard', 'undo', null),
    redo: () => editorRef.current?.trigger('keyboard', 'redo', null),
    getEditor: () => editorRef.current,
  }), []);

  const isBinaryOrLargeFile = useMemo(() => (
    content.includes('Binary file:')
    || content.includes('Large text file:')
    || content.includes('(Binary files cannot be displayed')
    || content.includes('(File too large to display')
  ), [content]);

  const currentTheme = useMemo(() => (
    state.ui.currentTheme === 'dark' ? 'vs-dark' : 'vs'
  ), [state.ui.currentTheme]);

  const handleEditorDidMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  const handleEditorChange: OnChange = (value) => {
    const newContent = value || '';
    onContentChange(newContent);
    onModifiedChange(newContent !== originalContent);
  };

  if (isBinaryOrLargeFile) {
    return (
      <div
        className="flex h-full w-full items-center justify-center p-8"
        style={{ display: visible ? 'flex' : 'none' }}
      >
        <div className="max-w-2xl text-center">
          <FileText className="mx-auto mb-4 h-12 w-12 text-muted-foreground opacity-50" />
          <div className="whitespace-pre-wrap rounded-lg bg-muted/30 p-4 font-mono text-sm text-muted-foreground">
            {content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full" style={{ display: visible ? 'block' : 'none' }}>
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
          readOnly,
        }}
      />
    </div>
  );
});

CodeTextEditor.displayName = 'CodeTextEditor';
