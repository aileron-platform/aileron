export type FileConflictOperation = 'upload' | 'paste' | 'extract' | 'create' | 'move';

export type FileConflictEntryType = 'file' | 'directory';

export type FileConflictStrategy = 'keep-both' | 'replace' | 'skip' | 'cancel';

export type ResolvableFileConflictStrategy = Exclude<FileConflictStrategy, 'cancel'>;

export interface FileConflictSource {
  sourcePath: string;
  entryType: FileConflictEntryType;
}

export interface FileConflictPreflightRequest {
  operation: FileConflictOperation;
  targetPath: string;
  sources: FileConflictSource[] | null;
  archivePath: string | null;
}

export interface FileConflictItem {
  sourcePath: string;
  targetPath: string;
  sourceType: FileConflictEntryType;
  targetType: FileConflictEntryType;
  canReplace: boolean;
}

export interface FileConflictPreflightResponse {
  conflicts: FileConflictItem[];
  total: number;
}

export interface FileConflictResolution {
  sourcePath: string;
  strategy: FileConflictStrategy;
}

export interface FileConflictExecutionFields {
  defaultStrategy: FileConflictStrategy;
  resolutions: FileConflictResolution[];
}

export type FileConflictResultStatus =
  | 'created'
  | 'kept-both'
  | 'replaced'
  | 'merged'
  | 'skipped'
  | 'cancelled'
  | 'failed';

export interface FileConflictResultItem {
  sourcePath: string;
  finalPath: string | null;
  status: FileConflictResultStatus;
  size: number;
  type: FileConflictEntryType;
  error: string | null;
}

export interface FileConflictBatchResult {
  items: FileConflictResultItem[];
  total: number;
  succeeded: number;
  skipped: number;
  failed: number;
}

export interface FileConflictExecutionRequest<TPayload>
  extends FileConflictPreflightRequest, FileConflictExecutionFields {
  payload: TPayload;
}

export interface FileConflictTransportOptions {
  signal: AbortSignal;
}

export interface FileConflictWorkflowTransport<TPayload> {
  preflight: (
    request: FileConflictPreflightRequest,
    options: FileConflictTransportOptions,
  ) => Promise<FileConflictPreflightResponse>;
  execute: (
    request: FileConflictExecutionRequest<TPayload>,
    options: FileConflictTransportOptions,
  ) => Promise<FileConflictBatchResult>;
}

export type FileConflictControllerPhase =
  | 'idle'
  | 'preflighting'
  | 'resolving'
  | 'executing'
  | 'completed'
  | 'cancelled'
  | 'preflight-error';
