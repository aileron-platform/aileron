import React, { useMemo, useState, useRef, useCallback, useEffect } from 'react';
import {
  Bold,
  Code,
  Eye,
  Image,
  Italic,
  Link,
  List,
  ListOrdered,
  Edit,
  Quote,
  Undo2,
  Redo2,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  applyMarkdownKeyCommand,
  applyMarkdownToolbarCommand,
  type MarkdownToolbarCommand,
} from './markdownEditorCommands';

export interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  textareaClassName?: string;
  toolbarExtras?: React.ReactNode;
  footerExtras?: React.ReactNode;
  statusMessage?: React.ReactNode;
  readOnly?: boolean;
}

export const MarkdownEditor: React.FC<MarkdownEditorProps> = ({
  value,
  onChange,
  placeholder,
  className,
  textareaClassName,
  toolbarExtras,
  footerExtras,
  statusMessage,
  readOnly = false,
}) => {
  const { t } = useI18n();
  const resolvedPlaceholder = placeholder ?? t('common.markdownEditor.placeholder');
  const [isPreview, setIsPreview] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const historyRef = useRef<string[]>([value]);
  const historyIndexRef = useRef(0);
  const skipNextSyncRef = useRef(false);
  const [, setHistoryVersion] = useState(0);

  const forceHistoryUpdate = useCallback(() => {
    setHistoryVersion((prev) => prev + 1);
  }, []);

  const commitHistory = useCallback(
    (nextValue: string) => {
      const history = historyRef.current;
      const index = historyIndexRef.current;
      if (history[index] === nextValue) {
        return;
      }
      const trimmed = history.slice(0, index + 1);
      trimmed.push(nextValue);
      historyRef.current = trimmed;
      historyIndexRef.current = trimmed.length - 1;
      skipNextSyncRef.current = true;
      forceHistoryUpdate();
    },
    [forceHistoryUpdate]
  );

  const shouldCommitParagraph = (prev: string, next: string) => {
    if (prev === next) {
      return false;
    }

    const minLength = Math.min(prev.length, next.length);
    let prefix = 0;
    while (prefix < minLength && prev[prefix] === next[prefix]) {
      prefix += 1;
    }

    let suffix = 0;
    while (
      suffix < minLength - prefix &&
      prev[prev.length - 1 - suffix] === next[next.length - 1 - suffix]
    ) {
      suffix += 1;
    }

    const inserted = next.slice(prefix, next.length - suffix);
    const removed = prev.slice(prefix, prev.length - suffix);

    if (inserted.includes('\n') || removed.includes('\n')) {
      return true;
    }

    const changedLength = Math.max(inserted.length, removed.length);
    return changedLength > 64;
  };

  const applyEdit = useCallback(
    (
      transform: (
        text: string,
        selectionStart: number,
        selectionEnd: number
      ) => { value: string; selectionStart: number; selectionEnd: number }
    ) => {
      if (readOnly) {
        return;
      }
      if (isPreview) {
        setIsPreview(false);
      }

      const textarea = textareaRef.current;
      if (!textarea) {
        return;
      }

      const start = textarea.selectionStart ?? 0;
      const end = textarea.selectionEnd ?? start;
      const result = transform(value, start, end);
      commitHistory(result.value);
      onChange(result.value);

      requestAnimationFrame(() => {
        const target = textareaRef.current;
        if (!target) {
          return;
        }
        target.focus();
        target.setSelectionRange(result.selectionStart, result.selectionEnd);
      });
    },
    [commitHistory, isPreview, onChange, readOnly, value]
  );

  const applyToolbarCommand = (command: MarkdownToolbarCommand, placeholder: string) => {
    applyEdit((text, selectionStart, selectionEnd) => {
      return applyMarkdownToolbarCommand({
        text,
        selectionStart,
        selectionEnd,
        command,
        placeholder,
      });
    });
  };

  const handleUndo = useCallback(() => {
    if (readOnly) {
      return;
    }
    if (historyIndexRef.current <= 0) {
      return;
    }
    historyIndexRef.current -= 1;
    const previousValue = historyRef.current[historyIndexRef.current];
    skipNextSyncRef.current = true;
    forceHistoryUpdate();
    if (isPreview) {
      setIsPreview(false);
    }
    if (previousValue !== value) {
      onChange(previousValue);
    }
    requestAnimationFrame(() => {
      const target = textareaRef.current;
      if (!target) {
        return;
      }
      const caret = previousValue.length;
      target.focus();
      target.setSelectionRange(caret, caret);
    });
  }, [forceHistoryUpdate, isPreview, onChange, readOnly, value]);

  const handleRedo = useCallback(() => {
    if (readOnly) {
      return;
    }
    const history = historyRef.current;
    if (historyIndexRef.current >= history.length - 1) {
      return;
    }
    historyIndexRef.current += 1;
    const nextValue = history[historyIndexRef.current];
    skipNextSyncRef.current = true;
    forceHistoryUpdate();
    if (isPreview) {
      setIsPreview(false);
    }
    if (nextValue !== value) {
      onChange(nextValue);
    }
    requestAnimationFrame(() => {
      const target = textareaRef.current;
      if (!target) {
        return;
      }
      const caret = nextValue.length;
      target.focus();
      target.setSelectionRange(caret, caret);
    });
  }, [forceHistoryUpdate, isPreview, onChange, readOnly, value]);

  useEffect(() => {
    const history = historyRef.current;
    const index = historyIndexRef.current;
    if (skipNextSyncRef.current) {
      skipNextSyncRef.current = false;
      return;
    }
    if (history[index] !== value) {
      const trimmed = history.slice(0, index + 1);
      trimmed.push(value);
      historyRef.current = trimmed;
      historyIndexRef.current = trimmed.length - 1;
      forceHistoryUpdate();
    }
  }, [forceHistoryUpdate, value]);

  const canUndo = historyIndexRef.current > 0;
  const canRedo = historyIndexRef.current < historyRef.current.length - 1;
  const length = value?.length ?? 0;

  return (
    <div className={cn('flex h-full flex-col bg-background', className)}>
      <div className="border-b border-border bg-muted/50">
        <div className="flex items-center justify-between px-4 py-2">
          <fieldset disabled={readOnly} className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.bold')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                applyToolbarCommand('bold', t('common.markdownEditor.placeholders.bold'));
              }}
            >
              <Bold className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.italic')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                applyToolbarCommand('italic', t('common.markdownEditor.placeholders.italic'));
              }}
            >
              <Italic className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.link')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                applyToolbarCommand('link', t('common.markdownEditor.placeholders.link'));
              }}
            >
              <Link className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.code')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                applyToolbarCommand('code', t('common.markdownEditor.placeholders.code'));
              }}
            >
              <Code className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.image')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                applyToolbarCommand('image', t('common.markdownEditor.placeholders.description'));
              }}
            >
              <Image className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.unorderedList')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                applyToolbarCommand('unorderedList', t('common.markdownEditor.placeholders.listItem'));
              }}
            >
              <List className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.orderedList')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                applyToolbarCommand('orderedList', t('common.markdownEditor.placeholders.listItem'));
              }}
            >
              <ListOrdered className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.quote')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                applyToolbarCommand('quote', t('common.markdownEditor.placeholders.quote'));
              }}
            >
              <Quote className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.undo')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleUndo();
              }}
              disabled={!canUndo}
            >
              <Undo2 className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              aria-label={t('common.markdownEditor.toolbar.redo')}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleRedo();
              }}
              disabled={!canRedo}
            >
              <Redo2 className="h-3.5 w-3.5" />
            </Button>
          </fieldset>
          <div className="flex items-center gap-2">
            {toolbarExtras}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setIsPreview((prev) => !prev);
              }}
            >
              {isPreview ? <Edit className="mr-1 h-3 w-3" /> : <Eye className="mr-1 h-3 w-3" />}
              {isPreview
                ? t('common.markdownEditor.actions.backToEdit')
                : t('common.markdownEditor.actions.preview')}
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {isPreview ? (
          <div className="h-full overflow-auto bg-background p-6">
            <MarkdownContent content={value} variant="editor" />
          </div>
        ) : (
          <textarea
            value={value}
            readOnly={readOnly}
            onChange={(event) => {
              if (readOnly) {
                return;
              }
              const nextValue = event.target.value;
              if (shouldCommitParagraph(value, nextValue)) {
                commitHistory(nextValue);
              }
              onChange(nextValue);
            }}
            onKeyDown={(event) => {
              if (readOnly) {
                return;
              }
              const result = applyMarkdownKeyCommand(
                value,
                event.currentTarget.selectionStart ?? 0,
                event.currentTarget.selectionEnd ?? event.currentTarget.selectionStart ?? 0,
                event.nativeEvent
              );
              if (!result) {
                return;
              }

              event.preventDefault();
              event.stopPropagation();
              commitHistory(result.value);
              onChange(result.value);

              requestAnimationFrame(() => {
                const target = textareaRef.current;
                if (!target) {
                  return;
                }
                target.focus();
                target.setSelectionRange(result.selectionStart, result.selectionEnd);
              });
            }}
            placeholder={resolvedPlaceholder}
            className={cn(
              'h-full w-full resize-none border-0 bg-background p-6 font-mono text-sm text-foreground focus:outline-none',
              textareaClassName
            )}
            ref={textareaRef}
          />
        )}
      </div>

      <div className="border-t border-border bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span>{t('common.markdownEditor.charCount', { count: length })}</span>
            {statusMessage && <span className="text-amber-600">{statusMessage}</span>}
          </div>
          <div className="flex items-center gap-3">{footerExtras}</div>
        </div>
      </div>
    </div>
  );
};
