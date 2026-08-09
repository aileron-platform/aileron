import { resolveThreadTitle } from './threadTitleModel';
import type { ThreadSummary } from './threadModel';

export type ThreadListSortMode = 'activity' | 'created' | 'title';

type Translate = (key: string) => string;

const effectiveActivityTime = (thread: ThreadSummary): number => {
  if (thread.status === 'draft') {
    return Date.parse(thread.createdAt);
  }
  return Date.parse(thread.updatedAt);
};

export const sortThreadSummaries = (
  threads: ThreadSummary[],
  mode: ThreadListSortMode,
  t: Translate,
): ThreadSummary[] => {
  const sorted = [...threads];
  if (mode === 'created') {
    return sorted.sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt));
  }
  if (mode === 'title') {
    return sorted.sort((left, right) =>
      resolveThreadTitle(left.title, t).localeCompare(resolveThreadTitle(right.title, t)),
    );
  }
  return sorted.sort((left, right) => {
    const byActivity = effectiveActivityTime(right) - effectiveActivityTime(left);
    if (byActivity !== 0) return byActivity;
    return Date.parse(right.createdAt) - Date.parse(left.createdAt);
  });
};
