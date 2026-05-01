import React from 'react';
import { BookOpen, ChevronDown, ChevronRight, GitBranch, Loader2, RefreshCw } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { WikiPagePreview, type WikiPagePreviewIssue } from '@/shared/components/wiki-page-preview';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  createKnowledgeBaseIngestJob,
  listKnowledgeBaseWikiPages,
} from '@/features/knowledge-base/api/knowledgeBaseApi';
import type {
  KnowledgeBaseWikiGroup,
  KnowledgeBaseWikiPagesResponse,
} from '@/shared/types/knowledgeBase';
import { IssuesSection, type WikiIssueSelection } from './wiki/IssuesSection';
import { DEFAULT_WIKI_PATH } from './graph/graphUtils';

interface KnowledgeBaseWikiTabProps {
  knowledgeBaseId: string;
}

export const KnowledgeBaseWikiTab: React.FC<KnowledgeBaseWikiTabProps> = ({ knowledgeBaseId }) => {
  const { t } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const [pages, setPages] = React.useState<KnowledgeBaseWikiPagesResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [collapsed, setCollapsed] = React.useState<Set<string>>(new Set());
  const [selectedIssue, setSelectedIssue] = React.useState<WikiIssueSelection | null>(null);

  const searchParams = React.useMemo(() => new URLSearchParams(location.search), [location.search]);
  const selectedPath = searchParams.get('path') || DEFAULT_WIKI_PATH;

  const setUrlState = React.useCallback((next: { path?: string }) => {
    const params = new URLSearchParams(location.search);
    params.set('path', next.path ?? selectedPath);
    navigate({ pathname: location.pathname, search: params.toString() }, { replace: false });
  }, [location.pathname, location.search, navigate, selectedPath]);

  React.useEffect(() => {
    if (!searchParams.get('path')) {
      const params = new URLSearchParams(location.search);
      params.set('path', searchParams.get('path') || DEFAULT_WIKI_PATH);
      navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
    }
  }, [location.pathname, location.search, navigate, searchParams]);

  const loadPages = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await listKnowledgeBaseWikiPages(knowledgeBaseId);
      setPages(result);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('knowledgeBase.wiki.loadFailed'));
    } finally {
      setIsLoading(false);
    }
  }, [knowledgeBaseId, t]);

  React.useEffect(() => {
    void loadPages();
  }, [loadPages]);

  const nonOverviewCount = React.useMemo(() => {
    return (pages?.groups ?? []).reduce((count, group) => (
      count + group.items.filter((item) => item.path !== DEFAULT_WIKI_PATH).length
    ), 0);
  }, [pages]);
  const isEmpty = pages !== null && nonOverviewCount === 0;

  const handleNavigate = React.useCallback((path: string) => {
    setUrlState({ path });
  }, [setUrlState]);

  const issueCard = React.useMemo<WikiPagePreviewIssue | null>(() => {
    if (!selectedIssue) return null;
    if (selectedIssue.kind === 'lint') {
      return {
        title: t('knowledgeBase.wiki.issues.lint.issueTitle', { type: selectedIssue.issue.issueType }),
        detail: selectedIssue.path,
        actions: (
          <Button type="button" size="sm" variant="outline" onClick={() => navigate(`${ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)}?file=${encodeURIComponent(selectedIssue.path)}`)}>
            {t('knowledgeBase.wiki.actions.editInFiles')}
          </Button>
        ),
      };
    }
    return {
      title: t(`knowledgeBase.review.types.${selectedIssue.item.type}`, { defaultValue: selectedIssue.item.type }),
      detail: selectedIssue.item.detail,
      actions: (
        <Button type="button" size="sm" variant="outline" onClick={() => navigate(`${ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)}?file=${encodeURIComponent(selectedIssue.path)}`)}>
          {t('knowledgeBase.wiki.actions.editInFiles')}
        </Button>
      ),
    };
  }, [knowledgeBaseId, navigate, selectedIssue, t]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {t('knowledgeBase.wiki.loading')}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-sm text-muted-foreground">
        <p className="text-destructive">{error}</p>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadPages()}>
          <RefreshCw className="mr-1.5 h-4 w-4" />
          {t('knowledgeBase.common.actions.refresh')}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <aside className="flex w-80 flex-shrink-0 flex-col border-r bg-muted/20">
        <div className="flex items-center justify-between gap-2 border-b bg-background px-3 py-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <BookOpen className="h-4 w-4 text-muted-foreground" />
            {t('knowledgeBase.detail.tabs.wiki')}
          </div>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <PageTree
            groups={pages?.groups ?? []}
            collapsed={collapsed}
            selectedPath={selectedPath}
            onToggle={(type) => setCollapsed((current) => {
              const next = new Set(current);
              if (next.has(type)) next.delete(type);
              else next.add(type);
              return next;
            })}
            onSelect={(path) => {
              setSelectedIssue(null);
              setUrlState({ path });
            }}
          />
        </ScrollArea>

        {!isEmpty ? (
          <IssuesSection
            kbId={knowledgeBaseId}
            selectedIssue={selectedIssue}
            onSelectIssue={(issue) => {
              setSelectedIssue(issue);
              setUrlState({ path: issue.path });
            }}
            onConverted={(path) => {
              setSelectedIssue(null);
              setUrlState({ path });
              void loadPages();
            }}
          />
        ) : null}
      </aside>

      <main className="min-w-0 flex-1 overflow-auto">
        {isEmpty ? (
          <EmptyWikiState
            kbId={knowledgeBaseId}
            onRefresh={() => void loadPages()}
          />
        ) : (
          <WikiPagePreview
            kbId={knowledgeBaseId}
            path={selectedPath}
            issue={issueCard}
            onNavigate={handleNavigate}
            onSourceOpen={(path) => navigate(`${ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)}?file=${encodeURIComponent(path)}`)}
          />
        )}
      </main>
    </div>
  );
};

const PageTree: React.FC<{
  groups: KnowledgeBaseWikiGroup[];
  collapsed: Set<string>;
  selectedPath: string;
  onToggle: (type: string) => void;
  onSelect: (path: string) => void;
}> = ({ groups, collapsed, selectedPath, onToggle, onSelect }) => {
  const { t } = useI18n();
  return (
    <div className="space-y-2 p-3">
      {groups.map((group) => {
        const isCollapsed = collapsed.has(group.type);
        return (
          <section key={group.type} className="space-y-1">
            <button type="button" className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs font-medium uppercase text-muted-foreground hover:bg-muted" onClick={() => onToggle(group.type)}>
              {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              <span className="min-w-0 flex-1 truncate">{t(group.labelKey, { defaultValue: group.type })}</span>
              <Badge variant="outline">{group.items.length}</Badge>
            </button>
            {!isCollapsed ? (
              <div className="space-y-1">
                {group.items.map((item) => (
                  <button
                    key={item.path}
                    type="button"
                    className={cn('w-full rounded-md px-3 py-2 text-left text-sm hover:bg-muted', selectedPath === item.path && 'bg-muted font-medium')}
                    onClick={() => onSelect(item.path)}
                  >
                    <div className="truncate">{item.title}</div>
                    <div className="truncate text-xs text-muted-foreground">{item.path}</div>
                  </button>
                ))}
              </div>
            ) : null}
          </section>
        );
      })}
    </div>
  );
};

const EmptyWikiState: React.FC<{
  kbId: string;
  onRefresh: () => void;
}> = ({ kbId, onRefresh }) => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [isRunning, setIsRunning] = React.useState(false);
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-md space-y-4 text-center">
        <BookOpen className="mx-auto h-10 w-10 text-muted-foreground" />
        <div className="text-sm text-muted-foreground">{t('knowledgeBase.wiki.empty.title')}</div>
        <div className="flex justify-center gap-2">
          <Button
            type="button"
            disabled={isRunning}
            onClick={async () => {
              setIsRunning(true);
              try {
                await createKnowledgeBaseIngestJob(kbId);
                onRefresh();
              } finally {
                setIsRunning(false);
              }
            }}
          >
            {isRunning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitBranch className="mr-2 h-4 w-4" />}
            {t('knowledgeBase.wiki.empty.runIngest')}
          </Button>
          <Button type="button" variant="outline" onClick={() => navigate(ROUTES.KNOWLEDGE_BASE_DETAIL_SCHEDULES(kbId))}>
            {t('knowledgeBase.wiki.empty.viewSchedules')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseWikiTab;
