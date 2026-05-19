import type React from 'react';
import type { ReactNode } from 'react';
import { Save } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { FileViewerWorkbenchTab } from './types';

interface FileViewerWorkbenchToolbarProps {
  headerActions?: ReactNode;
  formatActions: ReactNode | null;
  canSave: boolean;
  activeTab: FileViewerWorkbenchTab | null;
  onSave: () => void;
}

export const FileViewerWorkbenchToolbar: React.FC<FileViewerWorkbenchToolbarProps> = ({
  headerActions,
  formatActions,
  canSave,
  activeTab,
  onSave,
}) => {
  const { t } = useI18n();
  const showSave = canSave && Boolean(activeTab) && !formatActions;

  return (
    <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border bg-card px-2">
      <div className="flex min-w-0 items-center gap-1" data-testid="file-viewer-toolbar-left">
        {headerActions}
        {formatActions}
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1" data-testid="file-viewer-toolbar-right">
        {showSave ? (
          <button
            type="button"
            className="flex h-8 items-center justify-center rounded px-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            onClick={onSave}
            title={t('shared.fileViewer.toolbar.save')}
            aria-label={t('shared.fileViewer.toolbar.save')}
            disabled={!activeTab?.isModified}
          >
            <Save className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
    </div>
  );
};
