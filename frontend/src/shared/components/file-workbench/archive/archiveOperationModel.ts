export interface ArchiveProgressState {
  operationId: string;
  archiveName: string;
  paths: string[];
  status: 'pending' | 'running' | 'completed' | 'failed' | 'expired';
  progress: number;
  message: string;
  downloadUrl?: string | null;
  errorMessage?: string | null;
}

export interface ArchiveDownloadStatusResult {
  archiveName: string;
  downloadUrl: string;
}

export interface ArchiveDownloadStatusLike {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'expired';
  progress: number;
  message: string;
  error?: string | null;
  result?: ArchiveDownloadStatusResult | null;
}

interface BuildArchiveProgressFromStatusOptions {
  current: ArchiveProgressState;
  status: ArchiveDownloadStatusLike;
}

export const buildArchiveProgressFromStatus = ({
  current,
  status,
}: BuildArchiveProgressFromStatusOptions): ArchiveProgressState => {
  if (status.status === 'completed' && status.result) {
    return {
      ...current,
      status: 'completed',
      progress: 1,
      message: status.message,
      archiveName: status.result.archiveName,
      downloadUrl: status.result.downloadUrl,
      errorMessage: null,
    };
  }

  if (status.status === 'failed' || status.status === 'expired') {
    const message = status.error ?? status.message;
    return {
      ...current,
      status: status.status,
      progress: status.progress,
      message,
      downloadUrl: status.result?.downloadUrl ?? current.downloadUrl ?? null,
      errorMessage: message,
    };
  }

  return {
    ...current,
    status: status.status,
    progress: status.progress,
    message: status.message,
    downloadUrl: status.result?.downloadUrl ?? current.downloadUrl ?? null,
    errorMessage: status.error ?? null,
  };
};
