import type {
  FileConflictBatchResult,
  FileConflictEntryType,
  FileConflictExecutionRequest,
  FileConflictPreflightRequest,
  FileConflictPreflightResponse,
  FileConflictResultItem,
  FileConflictTransportOptions,
  FileConflictWorkflowTransport,
} from './types';

export interface LocalFileConflictPayload {
  content?: string;
  entryType?: FileConflictEntryType;
}

export interface LocalFileConflictEntry {
  path?: string;
  type: FileConflictEntryType;
}

export interface LocalFileConflictTransportOptions<TPayload extends LocalFileConflictPayload> {
  findEntry: (path: string) => LocalFileConflictEntry | null;
  refreshTree: () => Promise<readonly LocalFileConflictEntry[] | void>;
  createEntry: (
    path: string,
    entryType: FileConflictEntryType,
    content: string,
  ) => Promise<unknown>;
  moveEntry: (sourcePath: string, targetPath: string) => Promise<unknown>;
  deleteEntry: (path: string, recursive: boolean) => Promise<unknown>;
  getPayload: (payload: TPayload) => {
    sourcePath?: string;
    entryType?: FileConflictEntryType;
    content?: string;
  };
}

const getSource = (request: FileConflictPreflightRequest) => {
  const source = request.sources?.[0];
  if (!source) {
    throw new Error('FILE_CONFLICT_SOURCE_REQUIRED');
  }
  return source;
};

const getStrategy = <TPayload extends LocalFileConflictPayload>(
  request: FileConflictExecutionRequest<TPayload>,
  sourcePath: string,
) => request.resolutions.find((resolution) => resolution.sourcePath === sourcePath)?.strategy
  ?? request.defaultStrategy;

const getUniquePath = (
  path: string,
  findEntry: (candidate: string) => LocalFileConflictEntry | null,
): string => {
  const slashIndex = path.lastIndexOf('/');
  const parent = slashIndex > 0 ? path.slice(0, slashIndex) : '/';
  const name = path.slice(slashIndex + 1);
  const extensionIndex = name.lastIndexOf('.');
  const stem = extensionIndex > 0 ? name.slice(0, extensionIndex) : name;
  const extension = extensionIndex > 0 ? name.slice(extensionIndex) : '';

  for (let index = 1; index < 10_000; index += 1) {
    const candidateName = `${stem} (${index})${extension}`;
    const candidate = parent === '/' ? `/${candidateName}` : `${parent}/${candidateName}`;
    if (!findEntry(candidate)) return candidate;
  }

  throw new Error('FILE_CONFLICT_UNIQUE_PATH_EXHAUSTED');
};

const ensureMutationSucceeded = (response: unknown): void => {
  if (!response || typeof response !== 'object' || !('success' in response)) return;
  if (response.success === false) {
    const message = 'message' in response && typeof response.message === 'string'
      ? response.message
      : 'FILE_OPERATION_FAILED';
    throw new Error(message);
  }
};

const buildResult = (
  item: FileConflictResultItem,
): FileConflictBatchResult => ({
  items: [item],
  total: 1,
  succeeded: item.status === 'created'
    || item.status === 'kept-both'
    || item.status === 'replaced'
    || item.status === 'merged'
    ? 1
    : 0,
  skipped: item.status === 'skipped' || item.status === 'cancelled' ? 1 : 0,
  failed: item.status === 'failed' ? 1 : 0,
});

export const createLocalFileConflictTransport = <TPayload extends LocalFileConflictPayload>(
  options: LocalFileConflictTransportOptions<TPayload>,
): FileConflictWorkflowTransport<TPayload> => ({
  preflight: async (
    request: FileConflictPreflightRequest,
    _transportOptions: FileConflictTransportOptions,
  ): Promise<FileConflictPreflightResponse> => {
    const refreshedEntries = await options.refreshTree();
    const source = getSource(request);
    const target = refreshedEntries
      ? refreshedEntries.find(entry => entry.path === request.targetPath) ?? null
      : options.findEntry(request.targetPath);
    if (!target) return { conflicts: [], total: 1 };

    return {
      conflicts: [{
        sourcePath: source.sourcePath,
        targetPath: request.targetPath,
        sourceType: source.entryType,
        targetType: target.type,
        canReplace: source.entryType === target.type,
      }],
      total: 1,
    };
  },
  execute: async (
    request: FileConflictExecutionRequest<TPayload>,
    _transportOptions: FileConflictTransportOptions,
  ): Promise<FileConflictBatchResult> => {
    const source = getSource(request);
    const payload = options.getPayload(request.payload);
    const sourcePath = payload.sourcePath ?? source.sourcePath;
    const entryType = payload.entryType ?? source.entryType;
    const target = options.findEntry(request.targetPath);
    const strategy = target ? getStrategy(request, source.sourcePath) : 'cancel';

    if (target && strategy === 'cancel') {
      return buildResult({
        sourcePath,
        finalPath: null,
        status: 'cancelled',
        size: 0,
        type: entryType,
        error: null,
      });
    }
    if (target && strategy === 'skip') {
      return buildResult({
        sourcePath,
        finalPath: null,
        status: 'skipped',
        size: 0,
        type: entryType,
        error: null,
      });
    }
    if (target && strategy === 'replace' && target.type !== entryType) {
      return buildResult({
        sourcePath,
        finalPath: null,
        status: 'failed',
        size: 0,
        type: entryType,
        error: 'FILE_CONFLICT_TYPE_MISMATCH',
      });
    }

    const finalPath = target && strategy === 'keep-both'
      ? getUniquePath(request.targetPath, options.findEntry)
      : request.targetPath;
    const status = target && strategy === 'replace'
      ? 'replaced'
      : target && strategy === 'keep-both'
        ? 'kept-both'
        : 'created';

    try {
      if (target && strategy === 'replace') {
        ensureMutationSucceeded(await options.deleteEntry(
          request.targetPath,
          target.type === 'directory',
        ));
      }
      if (request.operation === 'create') {
        ensureMutationSucceeded(await options.createEntry(
          finalPath,
          entryType,
          payload.content ?? '',
        ));
      } else if (request.operation === 'move') {
        ensureMutationSucceeded(await options.moveEntry(sourcePath, finalPath));
      } else {
        throw new Error('UNSUPPORTED_LOCAL_FILE_CONFLICT_OPERATION');
      }
      return buildResult({
        sourcePath,
        finalPath,
        status,
        size: 0,
        type: entryType,
        error: null,
      });
    } catch (error) {
      return buildResult({
        sourcePath,
        finalPath: null,
        status: 'failed',
        size: 0,
        type: entryType,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  },
});

export const composeFileConflictTransports = <TPayload,>(
  remote: FileConflictWorkflowTransport<TPayload>,
  local: FileConflictWorkflowTransport<TPayload>,
): FileConflictWorkflowTransport<TPayload> => ({
  preflight: (request, options) => (
    request.operation === 'create' || request.operation === 'move'
      ? local.preflight(request, options)
      : remote.preflight(request, options)
  ),
  execute: (request, options) => (
    request.operation === 'create' || request.operation === 'move'
      ? local.execute(request, options)
      : remote.execute(request, options)
  ),
});
