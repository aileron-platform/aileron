import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { Edit, Save, X, Copy, Download, Loader2 } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import MarkdownEditor from '@/shared/components/markdown/MarkdownEditor';
import Editor, { type OnChange, type OnMount } from '@monaco-editor/react';
import { useApp } from '@/app/providers/AppProvider';
import { getLanguageFromFileName } from '@/shared/utils/languageUtils';

const logger = createLogger('FileEditor');

export interface FileEditorProps {
  fileName: string;
  filePath: string;
  fileContent: string;
  fileIcon?: React.ReactNode;
  readOnly?: boolean;
  onSave?: (content: string) => Promise<void>;
  onContentChange?: (content: string) => void;
  isLoading?: boolean;
  isSaving?: boolean;
  className?: string;
}

const isMarkdownFile = (filename: string) => filename.toLowerCase().endsWith('.md');

export const FileEditor: React.FC<FileEditorProps> = ({
  fileName,
  filePath,
  fileContent,
  fileIcon,
  readOnly = false,
  onSave,
  onContentChange,
  isLoading = false,
  isSaving = false,
  className = '',
}) => {
  const { toast } = useToast();
  const { t } = useI18n();
  const { state } = useApp();

  const [isEditing, setIsEditing] = useState(false);
  const [content, setContent] = useState(fileContent);
  const [originalContent, setOriginalContent] = useState(fileContent);
  const prevFilePathRef = useRef(filePath);
  const prevFileContentRef = useRef(fileContent);
  const editorRef = useRef<any>(null);

  useEffect(() => {
    const filePathChanged = prevFilePathRef.current !== filePath;
    const fileContentChanged = prevFileContentRef.current !== fileContent;

    if (filePathChanged) {
      setContent(fileContent);
      setOriginalContent(fileContent);
      setIsEditing(false);
      prevFilePathRef.current = filePath;
      prevFileContentRef.current = fileContent;
    } else if (fileContentChanged && !isEditing) {
      setContent(fileContent);
      setOriginalContent(fileContent);
      prevFileContentRef.current = fileContent;
    }
  }, [filePath, fileContent, isEditing]);

  const currentTheme = useMemo(() => {
    return state.ui.currentTheme === 'dark' ? 'vs-dark' : 'vs';
  }, [state.ui.currentTheme]);

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
    setContent(originalContent);
    setIsEditing(false);
    onContentChange?.(originalContent);
  };

  const handleSave = async () => {
    if (!onSave) return;

    try {
      await onSave(content);
      setOriginalContent(content);
      setIsEditing(false);
      toast({
        title: t('common.fileEditor.save.success'),
        description: t('common.fileEditor.save.successDesc', { name: fileName }),
      });
    } catch (error) {
      logger.error('Failed to save file', { error });
      toast({
        title: t('common.fileEditor.save.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      toast({
        title: t('common.fileEditor.copy.success'),
        description: t('common.fileEditor.copy.successDesc'),
      });
    } catch (error) {
      logger.error('Failed to copy file content', { error });
      toast({
        title: t('common.fileEditor.copy.error'),
        variant: 'destructive',
      });
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast({
      title: t('common.fileEditor.download.success'),
      description: t('common.fileEditor.download.successDesc', { name: fileName }),
    });
  };

  const handleEditorChange: OnChange = (value) => {
    try {
      const newContent = value || '';
      setContent(newContent);
      onContentChange?.(newContent);
    } catch (error) {
      logger.error('Failed to handle editor content change', { error });
    }
  };

  const handleEditorDidMount: OnMount = (editor) => {
    try {
      editorRef.current = editor;
    } catch (error) {
      logger.error('Failed to initialize Monaco editor', { error });
    }
  };

  const fileExtension = fileName.split('.').pop() || '';

  return (
    <div className={`flex h-full flex-col ${className}`}>
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 min-w-0">
          {fileIcon}
          <span className="truncate font-medium text-sm">{fileName}</span>
          <Badge variant="secondary" className="text-[11px]">
            {fileExtension}
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={isSaving || content === originalContent}
              >
                {isSaving ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <Save className="h-4 w-4 mr-1" />
                )}
                {t('common.fileEditor.actions.save')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleCancel}
                disabled={isSaving}
              >
                <X className="h-4 w-4 mr-1" />
                {t('common.fileEditor.actions.cancel')}
              </Button>
            </>
          ) : (
            <>
              {!readOnly && (
                <Button size="sm" variant="outline" onClick={handleEdit}>
                  <Edit className="h-4 w-4 mr-1" />
                  {t('common.fileEditor.actions.edit')}
                </Button>
              )}
              <Button size="sm" variant="outline" onClick={handleCopy}>
                <Copy className="h-4 w-4 mr-1" />
                {t('common.fileEditor.actions.copy')}
              </Button>
              <Button size="sm" variant="outline" onClick={handleDownload}>
                <Download className="h-4 w-4 mr-1" />
                {t('common.fileEditor.actions.download')}
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : isMarkdownFile(fileName) ? (
          isEditing ? (
            <MarkdownEditor
              value={content}
              onChange={(newContent) => {
                setContent(newContent);
                onContentChange?.(newContent);
              }}
              placeholder={t('common.fileEditor.markdown.placeholder')}
              className="h-full border-0 rounded-none"
            />
          ) : (
            <MarkdownContent content={content} variant="detailed" className="p-4" />
          )
        ) : (
          <div className="h-full relative">
            <Editor
              height="100%"
              language={getLanguageFromFileName(fileName)}
              value={content}
              theme={currentTheme}
              onMount={handleEditorDidMount}
              onChange={handleEditorChange}
              options={{
                readOnly: !isEditing,
                minimap: { enabled: false },
                fontSize: 14,
                wordWrap: 'on',
                automaticLayout: true,
                scrollBeyondLastLine: false,
                fontFamily: 'var(--font-mono)',
              }}
            />
            {(!content || content.length === 0) && !isEditing && (
              <div className="absolute inset-0 flex items-start justify-center pt-6 pointer-events-none">
                <div className="p-6 text-sm text-muted-foreground bg-background/80 rounded-md">
                  {t('common.fileEditor.emptyFile')}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
