import { Loader2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import type { ArchiveProgressState } from './archiveOperationModel';

export interface ExtractProgressState {
  operationId: string;
  archivePath: string;
  archiveName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  errorMessage?: string | null;
}

interface ArchiveDownloadRequest {
  downloadUrl: string;
  operationId: string;
  archiveName: string;
}

interface ArchiveProgressOverlaysProps {
  extractProgress: ExtractProgressState | null;
  archiveProgress: ArchiveProgressState | null;
  onArchiveDownload: (request: ArchiveDownloadRequest) => void;
}

const toProgressPercent = (progress: number): number => (
  Math.round(Math.min(1, Math.max(0, progress)) * 100)
);

export const ArchiveProgressOverlays = ({
  extractProgress,
  archiveProgress,
  onArchiveDownload,
}: ArchiveProgressOverlaysProps) => {
  const { t } = useI18n();
  const showExtractProgress = extractProgress
    && (extractProgress.status === 'pending' || extractProgress.status === 'running');

  return (
    <>
      {showExtractProgress && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-background/80 text-sm text-muted-foreground backdrop-blur-sm">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span>
            {t('shared.fileWorkbench.archive.extracting', {
              name: extractProgress.archiveName,
            })}
          </span>
          <span className="text-xs">
            {t('shared.fileWorkbench.archive.progress', {
              value: toProgressPercent(extractProgress.progress),
            })}
          </span>
          <span className="max-w-[320px] text-center text-xs text-muted-foreground">
            {extractProgress.message}
          </span>
        </div>
      )}

      {archiveProgress && (
        <div className="absolute bottom-3 left-3 right-3 z-10 rounded-md border border-border bg-background/95 p-3 text-sm shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 font-medium text-foreground">
                {(archiveProgress.status === 'pending' || archiveProgress.status === 'running') && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                )}
                <span className="truncate">
                  {archiveProgress.status === 'completed'
                    ? t('shared.fileWorkbench.archive.ready')
                    : t('shared.fileWorkbench.archive.preparing', { name: archiveProgress.archiveName })}
                </span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {t('shared.fileWorkbench.archive.progress', {
                  value: toProgressPercent(archiveProgress.progress),
                })}
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">
                {archiveProgress.errorMessage ?? archiveProgress.message}
              </div>
            </div>
            {archiveProgress.status === 'completed' && archiveProgress.downloadUrl && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => onArchiveDownload({
                  downloadUrl: archiveProgress.downloadUrl!,
                  operationId: archiveProgress.operationId,
                  archiveName: archiveProgress.archiveName,
                })}
              >
                {t('common.fileTree.contextMenu.download')}
              </Button>
            )}
          </div>
        </div>
      )}
    </>
  );
};
