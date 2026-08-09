import React, { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from 'react';
import type { OnChange, OnMount } from '@monaco-editor/react';
import { FileText } from 'lucide-react';
import { useResolvedTheme } from '@/shared/contexts/ResolvedThemeContext';
import { getLanguageFromFileName } from './model/languageUtils';
import { disableMonacoDiagnostics } from '@/shared/components/monaco/disableMonacoDiagnostics';
import { LocalizedMonacoEditor as Editor } from '@/shared/components/monaco/LocalizedMonacoEditor';
import type { FileViewerTextSelection } from './types';

export interface CodeTextEditorRef {
  undo: () => void;
  redo: () => void;
  getEditor: () => unknown;
}

interface MonacoEditorHandle {
  trigger: (source: string, handlerId: string, payload: unknown) => void;
}

interface MonacoSelectionDisposable {
  dispose: () => void;
}

interface CodeTextEditorProps {
  filePath?: string;
  fileName: string;
  content: string;
  readOnly?: boolean;
  visible?: boolean;
  onContentChange: (content: string) => void;
  onSelectionChange?: (selection: FileViewerTextSelection) => void;
}

export const CodeTextEditor = forwardRef<CodeTextEditorRef, CodeTextEditorProps>(({
  filePath,
  fileName,
  content,
  readOnly = false,
  visible = true,
  onContentChange,
  onSelectionChange,
}, ref) => {
  const editorRef = useRef<MonacoEditorHandle | null>(null);
  const selectionDisposableRef = useRef<MonacoSelectionDisposable | null>(null);
  const lastSelectionKeyRef = useRef<string | null>(null);
  const onSelectionChangeRef = useRef(onSelectionChange);
  const resolvedTheme = useResolvedTheme();
  onSelectionChangeRef.current = onSelectionChange;

  useEffect(() => () => {
    selectionDisposableRef.current?.dispose();
    selectionDisposableRef.current = null;
  }, []);

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
    resolvedTheme === 'dark' ? 'vs-dark' : 'vs'
  ), [resolvedTheme]);

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor as MonacoEditorHandle;
    disableMonacoDiagnostics(monaco);
    selectionDisposableRef.current?.dispose();
    lastSelectionKeyRef.current = null;
    selectionDisposableRef.current = editor.onDidChangeCursorSelection(({ selection }) => {
      if (selection.isEmpty()) {
        lastSelectionKeyRef.current = null;
        return;
      }

      const endLine = selection.endColumn === 1
        && selection.endLineNumber > selection.startLineNumber
        ? selection.endLineNumber - 1
        : selection.endLineNumber;
      const selectionKey = `${filePath ?? fileName}:${selection.startLineNumber}-${endLine}`;
      if (lastSelectionKeyRef.current === selectionKey || !filePath || !onSelectionChangeRef.current) {
        return;
      }

      lastSelectionKeyRef.current = selectionKey;
      onSelectionChangeRef.current({
        filePath,
        fileName,
        startLine: selection.startLineNumber,
        endLine,
      });
    });
  };

  const handleEditorChange: OnChange = (value) => {
    onContentChange(value ?? '');
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
