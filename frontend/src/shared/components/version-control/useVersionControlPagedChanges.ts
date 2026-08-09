import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { createKnowledgeBaseChangesCapability } from '@/shared/version-control/versionControlChangesCapability';
import type { VersionControlFileChange } from '@/shared/version-control';

type ChangesCapability = ReturnType<typeof createKnowledgeBaseChangesCapability>;
type ChangeGroup = 'staged' | 'unstaged' | 'untracked';

const initialCursors: Record<ChangeGroup, string | null> = {
  staged: null,
  unstaged: null,
  untracked: null,
};

const mergePage = (
  current: VersionControlFileChange[],
  nextFiles: VersionControlFileChange[],
  cursor: string | null,
) => {
  if (!cursor) return nextFiles;
  const existingPaths = new Set(current.map(file => file.path));
  return [...current, ...nextFiles.filter(file => !existingPaths.has(file.path))];
};

export const useVersionControlPagedChanges = (changes: ChangesCapability) => {
  const [cursors, setCursors] = useState(initialCursors);
  const [accumulatedStaged, setAccumulatedStaged] = useState<VersionControlFileChange[]>([]);
  const [accumulatedUnstaged, setAccumulatedUnstaged] = useState<VersionControlFileChange[]>([]);
  const [accumulatedUntracked, setAccumulatedUntracked] = useState<VersionControlFileChange[]>([]);
  const stagedLoadMoreRef = useRef<HTMLDivElement>(null);
  const unstagedLoadMoreRef = useRef<HTMLDivElement>(null);

  // Change groups only exist once the repository is initialized; querying them
  // earlier makes the runtime answer with repository_not_initialized.
  const statusQuery = changes.useStatusQuery();
  const enabled = statusQuery.data?.isInitialized === true;

  const stagedQuery = changes.useChangesQuery({
    group: 'staged',
    cursor: cursors.staged ?? undefined,
    limit: 100,
    enabled,
  });
  const unstagedQuery = changes.useChangesQuery({
    group: 'unstaged',
    cursor: cursors.unstaged ?? undefined,
    limit: 100,
    enabled,
  });
  const untrackedQuery = changes.useChangesQuery({
    group: 'untracked',
    cursor: cursors.untracked ?? undefined,
    limit: 100,
    enabled,
  });
  const conflictsQuery = changes.useChangesQuery({
    group: 'conflicts',
    limit: 500,
    enabled,
  });
  const queries = [stagedQuery, unstagedQuery, untrackedQuery, conflictsQuery];

  const numstatParams = useMemo(() => {
    const deferredPaths = (files: VersionControlFileChange[]) => files
      .filter(file => file.additions == null && file.deletions == null)
      .map(file => file.path);
    return {
      stagedPaths: deferredPaths(stagedQuery.data?.staged.items ?? []),
      unstagedPaths: deferredPaths(unstagedQuery.data?.unstaged.items ?? []),
    };
  }, [stagedQuery.data?.staged.items, unstagedQuery.data?.unstaged.items]);
  changes.useChangesNumstatQuery(numstatParams);

  useEffect(() => {
    const items = stagedQuery.data?.staged.items;
    if (items) setAccumulatedStaged(current => mergePage(current, items, cursors.staged));
  }, [cursors.staged, stagedQuery.data?.staged.items]);
  useEffect(() => {
    const items = unstagedQuery.data?.unstaged.items;
    if (items) setAccumulatedUnstaged(current => mergePage(current, items, cursors.unstaged));
  }, [cursors.unstaged, unstagedQuery.data?.unstaged.items]);
  useEffect(() => {
    const items = untrackedQuery.data?.untracked.items;
    if (items) setAccumulatedUntracked(current => mergePage(current, items, cursors.untracked));
  }, [cursors.untracked, untrackedQuery.data?.untracked.items]);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      const page = stagedQuery.data?.staged;
      if (entry.isIntersecting && page?.hasMore && page.nextCursor && !stagedQuery.isFetching) {
        setCursors(current => ({ ...current, staged: page.nextCursor }));
      }
    }, { threshold: 1, rootMargin: '100px' });
    const target = stagedLoadMoreRef.current;
    if (target) observer.observe(target);
    return () => observer.disconnect();
  }, [stagedQuery.data?.staged, stagedQuery.isFetching]);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      const unstagedPage = unstagedQuery.data?.unstaged;
      const untrackedPage = untrackedQuery.data?.untracked;
      if (entry.isIntersecting && !unstagedQuery.isFetching && !untrackedQuery.isFetching) {
        setCursors(current => ({
          ...current,
          unstaged: unstagedPage?.hasMore && unstagedPage.nextCursor
            ? unstagedPage.nextCursor
            : current.unstaged,
          untracked: untrackedPage?.hasMore && untrackedPage.nextCursor
            ? untrackedPage.nextCursor
            : current.untracked,
        }));
      }
    }, { threshold: 1, rootMargin: '100px' });
    const target = unstagedLoadMoreRef.current;
    if (target) observer.observe(target);
    return () => observer.disconnect();
  }, [
    unstagedQuery.data?.unstaged,
    unstagedQuery.isFetching,
    untrackedQuery.data?.untracked,
    untrackedQuery.isFetching,
  ]);

  const reset = useCallback(() => {
    setCursors(initialCursors);
    setAccumulatedStaged([]);
    setAccumulatedUnstaged([]);
    setAccumulatedUntracked([]);
  }, []);

  const stagedFiles = useMemo(
    () => (
      cursors.staged === null
        ? (stagedQuery.data?.staged.items ?? [])
        : accumulatedStaged
    ).map(file => ({ ...file, changeType: 'staged' as const })),
    [accumulatedStaged, cursors.staged, stagedQuery.data?.staged.items],
  );
  const unstagedFiles = useMemo(
    () => (
      cursors.unstaged === null
        ? (unstagedQuery.data?.unstaged.items ?? [])
        : accumulatedUnstaged
    ).map(file => ({ ...file, changeType: 'unstaged' as const })),
    [accumulatedUnstaged, cursors.unstaged, unstagedQuery.data?.unstaged.items],
  );
  const untrackedFiles = useMemo(
    () => (
      cursors.untracked === null
        ? (untrackedQuery.data?.untracked.items ?? [])
        : accumulatedUntracked
    ).map(file => ({ ...file, changeType: 'untracked' as const })),
    [accumulatedUntracked, cursors.untracked, untrackedQuery.data?.untracked.items],
  );
  const conflictFiles = useMemo(
    () => (conflictsQuery.data?.conflicts.items ?? []).map(file => ({
      ...file,
      changeType: 'unstaged' as const,
    })),
    [conflictsQuery.data?.conflicts.items],
  );

  return {
    queries: {
      all: queries,
      staged: stagedQuery,
      unstaged: unstagedQuery,
      untracked: untrackedQuery,
      conflicts: conflictsQuery,
    },
    files: {
      staged: stagedFiles,
      unstaged: unstagedFiles,
      untracked: untrackedFiles,
      conflicts: conflictFiles,
    },
    loadMore: { stagedRef: stagedLoadMoreRef, unstagedRef: unstagedLoadMoreRef },
    isFirstLoad: (statusQuery.isLoading || queries.some(query => query.isLoading))
      && queries.every(query => !query.data),
    error: queries.find(query => query.error)?.error ?? null,
    reset,
  };
};
