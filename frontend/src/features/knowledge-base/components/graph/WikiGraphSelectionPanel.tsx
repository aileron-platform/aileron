import React from 'react';
import { BookOpen, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { WikiPagePreview } from '@/shared/components/wiki-page-preview';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';

interface WikiGraphSelectionPanelProps {
  kbId: string;
  selectedPath: string | null;
  collapsed?: boolean;
  onNavigate: (path: string) => void;
  onOpenInWiki: () => void;
  onSourceOpen: (path: string) => void;
  onToggleCollapse?: () => void;
}

export const WikiGraphSelectionPanel: React.FC<WikiGraphSelectionPanelProps> = ({
  kbId,
  selectedPath,
  collapsed = false,
  onNavigate,
  onOpenInWiki,
  onSourceOpen,
  onToggleCollapse,
}) => {
  const { t } = useI18n();
  const toggleLabel = collapsed ? t('knowledgeBase.graph.actions.showPreview') : t('knowledgeBase.graph.actions.hidePreview');

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div className={cn(
        'flex h-10 items-center border-b bg-card px-3',
        collapsed ? 'justify-center' : 'justify-between gap-2',
      )}>
        {!collapsed ? (
          <>
            <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
              <BookOpen className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <span className="truncate">{t('knowledgeBase.graph.preview.title')}</span>
            </div>
            <div className="flex items-center gap-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8"
                disabled={!selectedPath}
                onClick={onOpenInWiki}
              >
                <BookOpen className="mr-1.5 h-3.5 w-3.5" />
                {t('knowledgeBase.graph.actions.openInWiki')}
              </Button>
              {onToggleCollapse ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  title={toggleLabel}
                  aria-label={toggleLabel}
                  onClick={onToggleCollapse}
                >
                  <ChevronRight className="h-3.5 w-3.5 transition-transform" />
                </Button>
              ) : null}
            </div>
          </>
        ) : onToggleCollapse ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            title={toggleLabel}
            aria-label={toggleLabel}
            onClick={onToggleCollapse}
          >
            <ChevronRight className="h-3.5 w-3.5 rotate-180 transition-transform" />
          </Button>
        ) : null}
      </div>
      {collapsed ? (
        <div className="flex flex-1 items-start justify-center pt-3">
          <BookOpen className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          {selectedPath ? (
            <WikiPagePreview
              kbId={kbId}
              path={selectedPath}
              onNavigate={onNavigate}
              onSourceOpen={onSourceOpen}
            />
          ) : (
            <div className="p-5 text-sm text-muted-foreground">
              {t('knowledgeBase.graph.preview.empty')}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
