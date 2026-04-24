import React, { useMemo } from 'react';
import { FileText } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

interface DiffLine {
  type: 'add' | 'remove' | 'context' | 'header';
  oldLineNumber?: number;
  newLineNumber?: number;
  content: string;
}

interface VersionControlDiffContentProps {
  diffContent?: string | null;
  selectedPath?: string | null;
  isLoading?: boolean;
  error?: string | null;
  i18nPrefix?: string;
}

function parseDiff(diffContent: string): DiffLine[] {
  const lines = diffContent.split('\n');
  const result: DiffLine[] = [];
  let oldLineNumber = 1;
  let newLineNumber = 1;

  for (const line of lines) {
    if (line.startsWith('@@')) {
      result.push({ type: 'header', content: line });
      const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/);
      if (match) {
        oldLineNumber = parseInt(match[1], 10);
        newLineNumber = parseInt(match[2], 10);
      }
    } else if (line.startsWith('+')) {
      result.push({ type: 'add', newLineNumber: newLineNumber++, content: line.substring(1) });
    } else if (line.startsWith('-')) {
      result.push({ type: 'remove', oldLineNumber: oldLineNumber++, content: line.substring(1) });
    } else if (line.startsWith(' ')) {
      result.push({
        type: 'context',
        oldLineNumber: oldLineNumber++,
        newLineNumber: newLineNumber++,
        content: line.substring(1),
      });
    }
  }

  return result;
}

export function isBinaryOrLargeDiff(diffContent: string): boolean {
  return diffContent.includes('Binary file:') ||
    diffContent.includes('Large text file:') ||
    diffContent.includes('Binary files') ||
    diffContent.includes('(Binary files cannot be displayed)') ||
    diffContent.includes('(File too large to display');
}

export const VersionControlDiffContent: React.FC<VersionControlDiffContentProps> = ({
  diffContent,
  selectedPath,
  isLoading = false,
  error,
  i18nPrefix = 'shared.versionControl.diff',
}) => {
  const { t } = useI18n();
  const effectiveError = error ?? (diffContent && isBinaryOrLargeDiff(diffContent) ? diffContent : null);
  const diffLines = useMemo(
    () => diffContent && !isBinaryOrLargeDiff(diffContent) ? parseDiff(diffContent) : [],
    [diffContent],
  );

  const renderDiffLine = (line: DiffLine, index: number) => {
    const lineClass = line.type === 'add'
      ? 'bg-green-50 dark:bg-green-500/10 border-l-2 border-l-green-600 dark:border-l-green-400'
      : line.type === 'remove'
        ? 'bg-red-50 dark:bg-red-500/10 border-l-2 border-l-red-600 dark:border-l-red-400'
        : line.type === 'header'
          ? 'bg-blue-50 dark:bg-blue-500/10 border-l-2 border-l-blue-600 dark:border-l-blue-400 font-medium'
          : 'bg-background';
    const prefix = line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' ';
    const prefixClass = line.type === 'add'
      ? 'text-green-600 dark:text-green-400'
      : line.type === 'remove'
        ? 'text-red-600 dark:text-red-400'
        : 'text-muted-foreground';

    return (
      <div key={index} className={`flex text-sm font-mono ${lineClass}`}>
        <div className="flex">
          <div className="w-12 px-2 py-1 text-right text-muted-foreground bg-muted/20 border-r border-border">
            {line.oldLineNumber || ''}
          </div>
          <div className="w-12 px-2 py-1 text-right text-muted-foreground bg-muted/20 border-r border-border">
            {line.newLineNumber || ''}
          </div>
        </div>
        <div className="flex-1 px-2 py-1 overflow-x-auto">
          <span className={`mr-2 font-bold ${prefixClass}`}>{prefix}</span>
          <span className="whitespace-pre-wrap text-foreground">{line.content}</span>
        </div>
      </div>
    );
  };

  const isBinaryOrLargeError = effectiveError && isBinaryOrLargeDiff(effectiveError);

  return (
    <div className="h-full flex flex-col bg-background">
      <div className="flex-1 overflow-auto">
        {effectiveError ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md px-4">
              <FileText className={`w-12 h-12 mx-auto mb-4 opacity-50 ${isBinaryOrLargeError ? 'text-muted-foreground' : 'text-destructive'}`} />
              <div className={`text-sm mb-2 ${isBinaryOrLargeError ? 'text-foreground' : 'text-destructive'}`}>
                {isBinaryOrLargeError ? t(`${i18nPrefix}.binaryOrLarge`) : t(`${i18nPrefix}.loadFailed`)}
              </div>
              <div className="text-xs text-muted-foreground whitespace-pre-wrap text-left bg-muted/30 p-3 rounded border border-border">
                {effectiveError}
              </div>
              {isBinaryOrLargeError && selectedPath && (
                <div className="mt-4 text-xs text-muted-foreground">
                  {t(`${i18nPrefix}.filePath`, { path: selectedPath })}
                </div>
              )}
            </div>
          </div>
        ) : isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-sm text-muted-foreground">{t(`${i18nPrefix}.loading`)}</div>
          </div>
        ) : diffLines.length > 0 ? (
          <div className="min-h-full">
            {diffLines.map((line, index) => renderDiffLine(line, index))}
          </div>
        ) : selectedPath ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <div className="text-sm">{t(`${i18nPrefix}.noDifference`)}</div>
              <div className="text-xs mt-2 font-mono">{selectedPath}</div>
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <div className="text-sm">{t(`${i18nPrefix}.empty`)}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
