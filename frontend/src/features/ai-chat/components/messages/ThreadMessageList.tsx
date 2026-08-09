import { FileText } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { ThreadExecutionMetadata, ThreadTurnMetadata, TimelineMessageItem } from '../../model/threadTimelineModel';
import { ThreadMessageItem } from './ThreadMessageItem';
import { toTimelinePresentation } from './toUiMessages';

interface ThreadMessageListProps {
  items: TimelineMessageItem[];
  turn: ThreadTurnMetadata;
  executions: ThreadExecutionMetadata[];
  showInitMessages: boolean;
}

type GitDiffMessage = Extract<TimelineMessageItem, { type: 'git_diff' }>;

type DiffLine = {
  id: string;
  kind: 'hunk' | 'added' | 'removed' | 'context';
  oldLine: number | null;
  newLine: number | null;
  text: string;
};

const parseChangedFiles = (message: GitDiffMessage) => {
  const statLines = message.content.diff
    .split('\n')
    .filter((line) => line.includes('|') && !line.startsWith('diff --git'));

  const files = statLines.flatMap((line) => {
    const match = line.match(/^\s*(.+?)\s+\|\s+\d+\s+([+-]+)\s*$/);
    if (!match) return [];

    const marker = match[2] ?? '';
    return [
      {
        path: (match[1] ?? '').trim(),
        additions: [...marker].filter((char) => char === '+').length,
        deletions: [...marker].filter((char) => char === '-').length,
      },
    ];
  });

  if (files.length === 1) {
    return [
      {
        ...files[0],
        additions: message.content.diffStats.additions,
        deletions: message.content.diffStats.deletions,
      },
    ];
  }

  return files;
};

const parseHunkStart = (line: string): { oldLine: number; newLine: number } | null => {
  const match = line.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
  if (!match) return null;

  return {
    oldLine: Number(match[1]),
    newLine: Number(match[2]),
  };
};

const parseDiffLines = (diff: string): DiffLine[] => {
  const lines: DiffLine[] = [];
  let oldLine = 0;
  let newLine = 0;

  diff.split('\n').forEach((line, index) => {
    if (
      line.startsWith('diff --git') ||
      line.startsWith('index ') ||
      line.startsWith('new file mode') ||
      line.startsWith('deleted file mode') ||
      line.startsWith('--- ') ||
      line.startsWith('+++ ') ||
      /^\s*\d+ files? changed/.test(line) ||
      /^\s*.+\s+\|\s+\d+\s+[+-]+/.test(line) ||
      line.trim() === ''
    ) {
      return;
    }

    if (line.startsWith('@@')) {
      const hunkStart = parseHunkStart(line);
      oldLine = hunkStart?.oldLine ?? oldLine;
      newLine = hunkStart?.newLine ?? newLine;
      lines.push({
        id: `${index}-hunk`,
        kind: 'hunk',
        oldLine: null,
        newLine: null,
        text: line,
      });
      return;
    }

    if (line.startsWith('+')) {
      lines.push({
        id: `${index}-added`,
        kind: 'added',
        oldLine: null,
        newLine,
        text: line.slice(1),
      });
      newLine += 1;
      return;
    }

    if (line.startsWith('-')) {
      lines.push({
        id: `${index}-removed`,
        kind: 'removed',
        oldLine,
        newLine: null,
        text: line.slice(1),
      });
      oldLine += 1;
      return;
    }

    lines.push({
      id: `${index}-context`,
      kind: 'context',
      oldLine,
      newLine,
      text: line.startsWith(' ') ? line.slice(1) : line,
    });
    oldLine += 1;
    newLine += 1;
  });

  return lines;
};

const diffLineClassName: Record<DiffLine['kind'], string> = {
  hunk: 'bg-muted/70 text-muted-foreground',
  added: 'bg-emerald-500/10 text-emerald-950 dark:text-emerald-100',
  removed: 'bg-destructive/10 text-destructive',
  context: 'text-foreground',
};

const diffLineTestId: Record<DiffLine['kind'], string> = {
  hunk: 'diff-line-hunk',
  added: 'diff-line-added',
  removed: 'diff-line-removed',
  context: 'diff-line-context',
};

const UnifiedDiffView = ({ diff }: { diff: string }) => {
  const lines = parseDiffLines(diff);

  return (
    <div className="max-h-[28rem] overflow-auto py-2 font-mono text-xs leading-5">
      <div className="min-w-max overflow-hidden rounded-md border border-border">
        {lines.map((line) => (
          <div
            key={line.id}
            data-testid={diffLineTestId[line.kind]}
            className={`grid grid-cols-[3.5rem_3.5rem_1fr] ${diffLineClassName[line.kind]}`}
          >
            <span className="select-none border-r border-border/70 px-2 text-right text-muted-foreground">
              {line.oldLine ?? ''}
            </span>
            <span className="select-none border-r border-border/70 px-2 text-right text-muted-foreground">
              {line.newLine ?? ''}
            </span>
            <span className="grid grid-cols-[1rem_1fr] whitespace-pre px-3">
              <span aria-hidden="true">{line.kind === 'added' ? '+' : line.kind === 'removed' ? '-' : ''}</span>
              <span>{line.text}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

const FilesChangedBlock = ({ message }: { message: GitDiffMessage }) => {
  const { t } = useI18n();
  const files = parseChangedFiles(message);

  return (
    <section className="space-y-2 pt-2 text-sm" data-testid="files-changed-block">
      <header className="flex min-w-0 items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-foreground">{t('aiChat.filesChanged.title')}</h2>
        <div className="flex shrink-0 items-center gap-2 text-sm">
          <span className="font-medium text-foreground">{message.content.diffStats.files}</span>
          <span className="font-medium text-emerald-600">+{message.content.diffStats.additions}</span>
          {message.content.diffStats.deletions > 0 && (
            <span className="font-medium text-destructive">-{message.content.diffStats.deletions}</span>
          )}
        </div>
      </header>

      <div className="space-y-2">
        {files.map((file) => (
          <details key={file.path} open className="group">
            <summary className="flex cursor-pointer list-none items-center gap-2 border-y border-border py-2 text-sm">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-foreground">{file.path}</span>
              {file.additions > 0 && <span className="font-medium text-emerald-600">+{file.additions}</span>}
              {file.deletions > 0 && <span className="font-medium text-destructive">-{file.deletions}</span>}
            </summary>
            <UnifiedDiffView diff={message.content.diff} />
          </details>
        ))}
      </div>
    </section>
  );
};

export const ThreadMessageList = ({ items, turn, executions, showInitMessages }: ThreadMessageListProps) => {
  const uiTurn = toTimelinePresentation(items, turn, executions);
  const visibleMessages = showInitMessages
    ? uiTurn.messages
    : uiTurn.messages.filter((message) => message.role !== 'init');
  const activityState = turn.status === 'running' || turn.status === 'waiting_for_input'
    ? 'working'
    : 'finished';

  return (
    <div className="space-y-3">
      {visibleMessages.map((message) => (
        <ThreadMessageItem key={message.id} message={message} activityState={activityState} />
      ))}
      {uiTurn.gitDiffMessages.map((message) => (
        <FilesChangedBlock key={message.id} message={message} />
      ))}
    </div>
  );
};
