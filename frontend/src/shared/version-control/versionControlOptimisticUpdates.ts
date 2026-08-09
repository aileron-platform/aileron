import type { VersionControlChangesResponse, VersionControlFileChange } from './types';

export const applyStagePathsToChangesResponse = (
  current: VersionControlChangesResponse | undefined,
  paths: string[],
): VersionControlChangesResponse | undefined => {
  if (!current || paths.length === 0) {
    return current;
  }

  const pathSet = new Set(paths);
  const movedFromUnstaged = current.unstaged.items.filter(file => pathSet.has(file.path));
  const movedFromUntracked = current.untracked.items.filter(file => pathSet.has(file.path));
  const movedFiles: VersionControlFileChange[] = [...movedFromUnstaged, ...movedFromUntracked].map(file => ({
    ...file,
    status: file.status === '?' || file.status === '??' ? 'A' : file.status,
    type: file.type === 'untracked' ? 'added' : file.type,
    changeType: 'staged',
  }));

  if (movedFiles.length === 0) {
    return current;
  }

  const stagedByPath = new Map(current.staged.items.map(file => [file.path, file]));
  for (const file of movedFiles) {
    stagedByPath.set(file.path, file);
  }

  return {
    ...current,
    staged: {
      ...current.staged,
      items: Array.from(stagedByPath.values()),
      total: current.staged.total + movedFiles.length,
    },
    unstaged: {
      ...current.unstaged,
      items: current.unstaged.items.filter(file => !pathSet.has(file.path)),
      total: Math.max(0, current.unstaged.total - movedFromUnstaged.length),
    },
    untracked: {
      ...current.untracked,
      items: current.untracked.items.filter(file => !pathSet.has(file.path)),
      total: Math.max(0, current.untracked.total - movedFromUntracked.length),
    },
  };
};

export const applyUnstagePathsToChangesResponse = (
  current: VersionControlChangesResponse | undefined,
  paths: string[],
): VersionControlChangesResponse | undefined => {
  if (!current || paths.length === 0) {
    return current;
  }

  const pathSet = new Set(paths);
  const movedFiles: VersionControlFileChange[] = current.staged.items
    .filter(file => pathSet.has(file.path))
    .map(file => ({ ...file, changeType: 'unstaged' }));

  if (movedFiles.length === 0) {
    return current;
  }

  const unstagedByPath = new Map(current.unstaged.items.map(file => [file.path, file]));
  for (const file of movedFiles) {
    unstagedByPath.set(file.path, file);
  }

  return {
    ...current,
    staged: {
      ...current.staged,
      items: current.staged.items.filter(file => !pathSet.has(file.path)),
      total: Math.max(0, current.staged.total - movedFiles.length),
    },
    unstaged: {
      ...current.unstaged,
      items: Array.from(unstagedByPath.values()),
      total: current.unstaged.total + movedFiles.length,
    },
  };
};

export const applyStageAllToChangesResponse = (
  current: VersionControlChangesResponse | undefined,
): VersionControlChangesResponse | undefined => {
  if (!current) {
    return current;
  }

  const paths = [
    ...current.unstaged.items.map(file => file.path),
    ...current.untracked.items.map(file => file.path),
  ];
  const stagedTotal = current.staged.total;
  const unstagedTotal = current.unstaged.total;
  const untrackedTotal = current.untracked.total;
  const next = applyStagePathsToChangesResponse(current, paths);

  return next
    ? {
      ...next,
      staged: {
        ...next.staged,
        total: stagedTotal + unstagedTotal + untrackedTotal,
        hasMore: stagedTotal + unstagedTotal + untrackedTotal > next.staged.items.length,
      },
      unstaged: { items: [], total: 0, nextCursor: null, hasMore: false },
      untracked: { items: [], total: 0, nextCursor: null, hasMore: false },
    }
    : next;
};

export const applyUnstageAllToChangesResponse = (
  current: VersionControlChangesResponse | undefined,
): VersionControlChangesResponse | undefined => {
  if (!current) {
    return current;
  }

  const stagedTotal = current.staged.total;
  const unstagedTotal = current.unstaged.total;
  const next = applyUnstagePathsToChangesResponse(
    current,
    current.staged.items.map(file => file.path),
  );

  return next
    ? {
      ...next,
      staged: { items: [], total: 0, nextCursor: null, hasMore: false },
      unstaged: {
        ...next.unstaged,
        total: unstagedTotal + stagedTotal,
        hasMore: unstagedTotal + stagedTotal > next.unstaged.items.length,
      },
    }
    : next;
};

export const addPathsToSet = (current: Set<string>, paths: string[]): Set<string> => {
  const next = new Set(current);
  for (const path of paths) {
    next.add(path);
  }
  return next;
};

export const removePathsFromSet = (current: Set<string>, paths: string[]): Set<string> => {
  const next = new Set(current);
  for (const path of paths) {
    next.delete(path);
  }
  return next;
};
