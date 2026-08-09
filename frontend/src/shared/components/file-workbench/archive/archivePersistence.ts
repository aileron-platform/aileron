export interface PersistedArchiveOperation<TContext> {
  operationId: string;
  archiveName: string;
  paths: string[];
  context: TContext;
  startedAt: string;
  downloadTriggeredAt?: string | null;
}

export interface ArchiveOperationLookup<TContext> {
  context: TContext;
  storage?: Storage;
}

const getBrowserStorage = (): Storage | undefined => {
  if (typeof window === 'undefined') {
    return undefined;
  }
  return window.localStorage;
};

const getStorage = (storage?: Storage): Storage | undefined => storage ?? getBrowserStorage();

export const loadPersistedArchiveOperations = (
  storageKey: string,
  storage?: Storage,
): PersistedArchiveOperation<unknown>[] => {
  const resolvedStorage = getStorage(storage);
  if (!resolvedStorage) {
    return [];
  }

  try {
    const raw = resolvedStorage.getItem(storageKey);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item) => item && typeof item === 'object' && 'context' in item);
  } catch {
    resolvedStorage.removeItem(storageKey);
    return [];
  }
};

export const savePersistedArchiveOperations = (
  storageKey: string,
  operations: PersistedArchiveOperation<unknown>[],
  storage?: Storage,
) => {
  const resolvedStorage = getStorage(storage);
  if (!resolvedStorage) {
    return;
  }

  resolvedStorage.setItem(storageKey, JSON.stringify(operations));
};

export const upsertPersistedArchiveOperation = (
  storageKey: string,
  operation: PersistedArchiveOperation<unknown>,
  storage?: Storage,
) => {
  const existing = loadPersistedArchiveOperations(storageKey, storage).filter(
    (item) => item.operationId !== operation.operationId,
  );
  savePersistedArchiveOperations(storageKey, [...existing, operation], storage);
};

export const removePersistedArchiveOperation = (
  storageKey: string,
  operationId: string,
  storage?: Storage,
) => {
  savePersistedArchiveOperations(
    storageKey,
    loadPersistedArchiveOperations(storageKey, storage).filter((item) => item.operationId !== operationId),
    storage,
  );
};

export const removePersistedArchiveOperationsForContext = <TContext>({
  context,
  storage,
  storageKey,
}: ArchiveOperationLookup<TContext> & { storageKey: string }) => {
  const serializedContext = JSON.stringify(context);
  savePersistedArchiveOperations(
    storageKey,
    loadPersistedArchiveOperations(storageKey, storage).filter(
      (item) => JSON.stringify(item.context) !== serializedContext,
    ),
    storage,
  );
};

export const removePersistedArchiveOperationsForResource = ({
  resourceId,
  resourceKey,
  storage,
  storageKey,
}: {
  resourceId: string;
  resourceKey: string;
  storage?: Storage;
  storageKey: string;
}) => {
  savePersistedArchiveOperations(
    storageKey,
    loadPersistedArchiveOperations(storageKey, storage).filter((item) => {
      if (!item.context || typeof item.context !== 'object') {
        return false;
      }
      return (item.context as Record<string, unknown>)[resourceKey] !== resourceId;
    }),
    storage,
  );
};

export const markPersistedArchiveDownloadTriggered = (
  storageKey: string,
  operationId: string,
  storage?: Storage,
) => {
  savePersistedArchiveOperations(
    storageKey,
    loadPersistedArchiveOperations(storageKey, storage).map((item) => (
      item.operationId === operationId
        ? { ...item, downloadTriggeredAt: new Date().toISOString() }
        : item
    )),
    storage,
  );
};

export const findLatestPersistedArchiveOperation = <TContext>({
  context,
  storage,
  storageKey,
}: ArchiveOperationLookup<TContext> & { storageKey: string }): PersistedArchiveOperation<TContext> | null => {
  return loadPersistedArchiveOperations(storageKey, storage)
    .filter((item): item is PersistedArchiveOperation<TContext> => (
      JSON.stringify(item.context) === JSON.stringify(context)
    ))
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0] ?? null;
};
