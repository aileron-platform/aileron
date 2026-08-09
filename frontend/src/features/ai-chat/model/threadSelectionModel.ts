interface ThreadSelectionCandidate {
  id: string;
}

interface ResolveThreadSelectionOptions {
  threads: readonly ThreadSelectionCandidate[];
  getSavedThreadId: () => string | null;
  queryThreadId?: string | null;
}

export const resolveThreadSelection = ({
  threads,
  getSavedThreadId,
  queryThreadId = null,
}: ResolveThreadSelectionOptions): string | null => {
  const threadIds = new Set(threads.map((thread) => thread.id));
  if (queryThreadId && threadIds.has(queryThreadId)) return queryThreadId;

  const savedThreadId = getSavedThreadId();
  if (savedThreadId && threadIds.has(savedThreadId)) return savedThreadId;

  return threads[0]?.id ?? null;
};
