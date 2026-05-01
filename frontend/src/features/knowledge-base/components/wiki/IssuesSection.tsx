import React from 'react';
import { AlertTriangle, CheckCircle2, Loader2, ShieldCheck } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  convertKnowledgeBaseReview,
  dismissKnowledgeBaseReview,
  listKnowledgeBaseReviews,
  resolveKnowledgeBaseReview,
  runKnowledgeBaseLint,
} from '@/features/knowledge-base/api/knowledgeBaseApi';
import type { KnowledgeBaseLintIssue, KnowledgeBaseReviewItem } from '@/shared/types/knowledgeBase';
import { useI18n } from '@/shared/hooks/useI18n';

export type WikiIssueSelection =
  | { kind: 'lint'; path: string; issue: KnowledgeBaseLintIssue }
  | { kind: 'review'; path: string; item: KnowledgeBaseReviewItem };

interface IssuesSectionProps {
  kbId: string;
  selectedIssue: WikiIssueSelection | null;
  onSelectIssue: (issue: WikiIssueSelection) => void;
  onConverted: (path: string) => void;
}

export const IssuesSection: React.FC<IssuesSectionProps> = ({ kbId, selectedIssue, onSelectIssue, onConverted }) => {
  const { t } = useI18n();
  const [lintIssues, setLintIssues] = React.useState<KnowledgeBaseLintIssue[] | null>(null);
  const [lastRun, setLastRun] = React.useState<string | null>(null);
  const [isLinting, setIsLinting] = React.useState(false);
  const [reviews, setReviews] = React.useState<KnowledgeBaseReviewItem[]>([]);
  const [isReviewsLoading, setIsReviewsLoading] = React.useState(false);

  const loadReviews = React.useCallback(async () => {
    setIsReviewsLoading(true);
    try {
      const response = await listKnowledgeBaseReviews(kbId, 'open');
      setReviews(response.items ?? []);
    } finally {
      setIsReviewsLoading(false);
    }
  }, [kbId]);

  React.useEffect(() => {
    setLintIssues(null);
    setLastRun(null);
    void loadReviews();
  }, [kbId, loadReviews]);

  const handleRunLint = React.useCallback(async () => {
    setIsLinting(true);
    try {
      const report = await runKnowledgeBaseLint(kbId);
      setLintIssues(report.issues ?? []);
      setLastRun(new Date(report.generatedAt).toLocaleString());
    } finally {
      setIsLinting(false);
    }
  }, [kbId]);

  const handleResolve = React.useCallback(async (item: KnowledgeBaseReviewItem) => {
    await resolveKnowledgeBaseReview(kbId, item.id);
    await loadReviews();
  }, [kbId, loadReviews]);

  const handleDismiss = React.useCallback(async (item: KnowledgeBaseReviewItem) => {
    await dismissKnowledgeBaseReview(kbId, item.id);
    await loadReviews();
  }, [kbId, loadReviews]);

  const handleConvert = React.useCallback(async (item: KnowledgeBaseReviewItem) => {
    const title = window.prompt(t('knowledgeBase.wiki.issues.reviews.convertPrompt'));
    if (!title) {
      return;
    }
    const updated = await convertKnowledgeBaseReview(kbId, item.id, { title });
    await loadReviews();
    if (updated.queryPage) {
      onConverted(updated.queryPage);
    }
  }, [kbId, loadReviews, onConverted, t]);

  const total = (lintIssues?.length ?? 0) + reviews.length;
  const healthy = lintIssues !== null && lintIssues.length === 0 && reviews.length === 0;

  return (
    <section className="border-t bg-background">
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          {t('knowledgeBase.wiki.issues.title')}
        </div>
        <Badge variant={total > 0 ? 'destructive' : 'outline'}>{total}</Badge>
      </div>

      <div className="space-y-3 px-3 pb-3">
        {healthy ? (
          <div className="flex items-center gap-2 rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            {t('knowledgeBase.wiki.issues.healthy')}
          </div>
        ) : null}

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-medium uppercase text-muted-foreground">
              {t('knowledgeBase.wiki.issues.lint.title')}
              {lastRun ? <span className="ml-1 normal-case">({t('knowledgeBase.wiki.issues.lint.lastRun', { time: lastRun })})</span> : null}
            </div>
            <Button type="button" size="sm" variant="outline" className="h-7 px-2 text-xs" disabled={isLinting} onClick={() => void handleRunLint()}>
              {isLinting ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="mr-1.5 h-3.5 w-3.5" />}
              {t('knowledgeBase.wiki.issues.lint.runButton')}
            </Button>
          </div>
          {lintIssues === null ? (
            <div className="text-xs text-muted-foreground">{t('knowledgeBase.wiki.issues.lint.initial')}</div>
          ) : lintIssues.length === 0 ? null : (
            <div className="max-h-36 space-y-1 overflow-auto">
              {lintIssues.map((issue, index) => (
                <button
                  key={`${issue.issueType}-${issue.path}-${index}`}
                  type="button"
                  className="w-full rounded-md border px-2 py-1.5 text-left text-xs hover:bg-muted"
                  onClick={() => onSelectIssue({ kind: 'lint', path: issue.path, issue })}
                  aria-pressed={selectedIssue?.kind === 'lint' && selectedIssue.issue === issue}
                >
                  <div className="font-medium">{issue.issueType}</div>
                  <div className="truncate text-muted-foreground">{issue.path}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-medium uppercase text-muted-foreground">{t('knowledgeBase.wiki.issues.reviews.title')}</div>
            {isReviewsLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" /> : <Badge variant="outline">{reviews.length}</Badge>}
          </div>
          {reviews.length === 0 ? (
            <div className="text-xs text-muted-foreground">{t('knowledgeBase.wiki.issues.reviews.empty')}</div>
          ) : (
            <div className="max-h-44 space-y-1 overflow-auto">
              {reviews.map((item) => (
                <div key={item.id} className="rounded-md border p-2 text-xs">
                  <button
                    type="button"
                    className="block w-full text-left"
                    onClick={() => onSelectIssue({ kind: 'review', path: item.pagePath, item })}
                  >
                    <div className="font-medium">{t(`knowledgeBase.review.types.${item.type}`, { defaultValue: item.type })}</div>
                    <div className="truncate text-muted-foreground">{item.pagePath}</div>
                    <div className="mt-1 line-clamp-2">{item.detail}</div>
                  </button>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <Button type="button" size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => void handleResolve(item)}>
                      {t('knowledgeBase.review.actions.resolve')}
                    </Button>
                    <Button type="button" size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => void handleDismiss(item)}>
                      {t('knowledgeBase.review.actions.dismiss')}
                    </Button>
                    <Button type="button" size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => void handleConvert(item)}>
                      {t('knowledgeBase.review.actions.convertToQuery')}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
