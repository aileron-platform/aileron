import React from 'react';
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';
import { disableMonacoDiagnostics } from '@/shared/components/monaco/disableMonacoDiagnostics';
import { LocalizedMonacoEditor as Editor } from '@/shared/components/monaco/LocalizedMonacoEditor';
import { cn } from '@/shared/utils/cn';

export type SettingsDocumentFormat = 'markdown' | 'toml' | 'json' | 'starlark';

export interface SettingsDocumentEditorProps {
  value: string;
  format: SettingsDocumentFormat;
  onChange: (value: string) => void;
  placeholder?: string;
  readOnly?: boolean;
  className?: string;
  footerExtras?: React.ReactNode;
}

const LANGUAGE_BY_FORMAT: Record<SettingsDocumentFormat, string> = {
  markdown: 'markdown',
  toml: 'toml',
  json: 'json',
  starlark: 'python',
};

export const SettingsDocumentEditor: React.FC<SettingsDocumentEditorProps> = ({
  value,
  format,
  onChange,
  placeholder,
  readOnly = false,
  className,
  footerExtras,
}) => {
  if (format === 'markdown') {
    return (
      <MarkdownEditor
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={cn('h-full', className)}
        footerExtras={footerExtras}
      />
    );
  }

  return (
    <div className={cn('h-full overflow-hidden', className)}>
      <Editor
        height="100%"
        language={LANGUAGE_BY_FORMAT[format]}
        value={value}
        onMount={(_editor, monaco) => disableMonacoDiagnostics(monaco)}
        onChange={(nextValue) => onChange(nextValue ?? '')}
        options={{
          readOnly,
          minimap: { enabled: false },
          wordWrap: 'on',
          fontSize: 13,
          automaticLayout: true,
          scrollBeyondLastLine: false,
          fontFamily: 'var(--font-mono)',
        }}
      />
      {footerExtras ? (
        <div className="border-t border-border px-3 py-2">
          {footerExtras}
        </div>
      ) : null}
    </div>
  );
};

SettingsDocumentEditor.displayName = 'SettingsDocumentEditor';

export default SettingsDocumentEditor;
