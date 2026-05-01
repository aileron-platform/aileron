import React from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';
import { WikiPageFrontmatter } from './WikiPageFrontmatter';
import { WikiPageReader } from './WikiPageReader';
import { useWikiPage } from './useWikiPage';
import { useI18n } from '@/shared/hooks/useI18n';

export interface WikiPagePreviewIssue {
  title: string;
  detail?: string;
  actions?: React.ReactNode;
}

interface WikiPagePreviewProps {
  kbId: string;
  path: string | null;
  compact?: boolean;
  issue?: WikiPagePreviewIssue | null;
  onNavigate?: (path: string) => void;
  onSourceOpen?: (path: string) => void;
}

export const WikiPagePreview: React.FC<WikiPagePreviewProps> = ({
  kbId,
  path,
  compact,
  issue,
  onNavigate,
  onSourceOpen,
}) => {
  const { t } = useI18n();
  const { data, isLoading, error } = useWikiPage(kbId, path);

  if (!path) {
    return <div className="p-5 text-sm text-muted-foreground">{t('knowledgeBase.wiki.preview.empty')}</div>;
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {t('knowledgeBase.wiki.preview.loading')}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-full items-center justify-center gap-2 p-5 text-sm text-destructive">
        <AlertCircle className="h-4 w-4" />
        {t('knowledgeBase.wiki.preview.loadFailed')}
      </div>
    );
  }

  return (
    <article className="min-h-full bg-background">
      {issue ? (
        <section className="border-b bg-muted/30 px-5 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-medium">{issue.title}</div>
              {issue.detail ? <div className="text-xs text-muted-foreground">{issue.detail}</div> : null}
            </div>
            {issue.actions ? <div className="flex flex-wrap gap-2">{issue.actions}</div> : null}
          </div>
        </section>
      ) : null}
      <WikiPageFrontmatter
        frontmatter={data.frontmatter}
        sources={data.resolved.sources}
        related={data.resolved.related}
        onNavigate={onNavigate}
        onSourceOpen={onSourceOpen}
      />
      <WikiPageReader
        body={data.body}
        related={data.resolved.related}
        compact={compact}
        onNavigate={onNavigate}
      />
    </article>
  );
};

export { WikiPageFrontmatter } from './WikiPageFrontmatter';
export { WikiPageReader } from './WikiPageReader';
export { useWikiPage } from './useWikiPage';
