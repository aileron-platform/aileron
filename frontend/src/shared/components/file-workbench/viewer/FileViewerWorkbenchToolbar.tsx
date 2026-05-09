import type React from 'react';
import type { ReactNode, RefObject } from 'react';
import { Maximize2, Minimize2, MoreHorizontal, Save } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { FileViewerWorkbenchTab } from './types';

interface FileViewerWorkbenchToolbarProps {
  headerActions?: ReactNode;
  formatActions: ReactNode | null;
  canSave: boolean;
  activeTab: FileViewerWorkbenchTab | null;
  isExpanded: boolean;
  onSave: () => void;
  onToggleExpanded: () => void;
  onOpenMoreMenu: () => void;
  moreButtonRef: RefObject<HTMLButtonElement>;
}

export const FileViewerWorkbenchToolbar: React.FC<FileViewerWorkbenchToolbarProps> = ({
  headerActions,
  formatActions,
  canSave,
  activeTab,
  isExpanded,
  onSave,
  onToggleExpanded,
  onOpenMoreMenu,
  moreButtonRef,
}) => {
  const { t } = useI18n();
  const expandedLabel = isExpanded
    ? t('shared.fileViewer.toolbar.collapse')
    : t('shared.fileViewer.toolbar.expand');
  const showSave = canSave && Boolean(activeTab) && (activeTab?.isModified === true || !formatActions);

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
        <button
          type="button"
          className="flex h-8 items-center justify-center rounded px-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onToggleExpanded}
          title={expandedLabel}
          aria-label={expandedLabel}
          disabled={!activeTab}
        >
          {isExpanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
        </button>
        <button
          ref={moreButtonRef}
          type="button"
          className="flex h-8 items-center justify-center rounded px-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          onClick={onOpenMoreMenu}
          title={t('shared.fileViewer.toolbar.more')}
          aria-label={t('shared.fileViewer.toolbar.more')}
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
};
