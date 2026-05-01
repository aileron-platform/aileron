import React from 'react';
import { BookOpen } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { WikiPagePreview } from '@/shared/components/wiki-page-preview';
import { useI18n } from '@/shared/hooks/useI18n';

interface WikiGraphSelectionPanelProps {
  kbId: string;
  selectedPath: string | null;
  onNavigate: (path: string) => void;
  onOpenInWiki: () => void;
  onSourceOpen: (path: string) => void;
}

export const WikiGraphSelectionPanel: React.FC<WikiGraphSelectionPanelProps> = ({
  kbId,
  selectedPath,
  onNavigate,
  onOpenInWiki,
  onSourceOpen,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex min-h-12 items-center justify-between gap-2 border-b px-3 py-2">
        <div className="min-w-0 text-sm font-medium">{t('knowledgeBase.graph.preview.title')}</div>
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
      </div>
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
    </div>
  );
};
