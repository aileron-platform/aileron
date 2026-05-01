import React from 'react';
import { FileText, Link2, Tags } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import type { KnowledgeBaseWikiPageRef } from '@/shared/types/knowledgeBase';
import { useI18n } from '@/shared/hooks/useI18n';

interface WikiPageFrontmatterProps {
  frontmatter: Record<string, unknown>;
  sources: KnowledgeBaseWikiPageRef[];
  related: KnowledgeBaseWikiPageRef[];
  onNavigate?: (path: string) => void;
  onSourceOpen?: (path: string) => void;
}

const asString = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value : null);
const asStringList = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string');
  if (typeof value === 'string') return [value];
  return [];
};

export const WikiPageFrontmatter: React.FC<WikiPageFrontmatterProps> = ({
  frontmatter,
  sources,
  related,
  onNavigate,
  onSourceOpen,
}) => {
  const { t } = useI18n();
  const title = asString(frontmatter.title);
  const pageType = asString(frontmatter.type);
  const description = asString(frontmatter.description);
  const tags = asStringList(frontmatter.tags);

  return (
    <section className="space-y-3 border-b bg-background px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          {title ? <h2 className="truncate text-lg font-semibold">{title}</h2> : null}
          {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
        </div>
        {pageType ? (
          <Badge variant="secondary">{t(`knowledgeBase.wiki.types.${pageType}`, { defaultValue: pageType })}</Badge>
        ) : null}
      </div>

      {tags.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <Tags className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="sr-only">{t('knowledgeBase.wiki.frontmatter.tags')}</span>
          {tags.map((tag) => <Badge key={tag} variant="outline">{tag}</Badge>)}
        </div>
      ) : null}

      {sources.length > 0 ? (
        <div className="space-y-1.5">
          <div className="text-xs font-medium uppercase text-muted-foreground">{t('knowledgeBase.wiki.frontmatter.sources')}</div>
          <div className="grid gap-2 sm:grid-cols-2">
            {sources.map((source) => (
              <Button
                key={`${source.name}-${source.path}`}
                type="button"
                variant="outline"
                className="h-auto justify-start gap-2 px-3 py-2 text-left"
                disabled={!source.path}
                onClick={() => source.path && onSourceOpen?.(source.path)}
              >
                <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate text-xs">{source.name ?? source.path}</span>
                <Badge variant={source.exists ? 'secondary' : 'outline'}>
                  {source.exists
                    ? t('knowledgeBase.wiki.frontmatter.sourceExists')
                    : t('knowledgeBase.wiki.frontmatter.sourceMissing')}
                </Badge>
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      {related.length > 0 ? (
        <div className="space-y-1.5">
          <div className="text-xs font-medium uppercase text-muted-foreground">{t('knowledgeBase.wiki.frontmatter.related')}</div>
          <div className="flex flex-wrap gap-1.5">
            {related.map((item) => (
              <Button
                key={`${item.slug}-${item.path}`}
                type="button"
                variant="outline"
                size="sm"
                className="h-7 gap-1.5 px-2 text-xs"
                disabled={!item.exists || !item.path}
                onClick={() => item.path && onNavigate?.(item.path)}
              >
                <Link2 className="h-3.5 w-3.5" />
                {item.title ?? item.slug ?? item.path}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
};
