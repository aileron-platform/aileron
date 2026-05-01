import React from 'react';
import { ChevronLeft, Network } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type { KnowledgeBaseGraphNode } from '@/shared/types/knowledgeBase';

interface WikiGraphNodeListProps {
  nodes: KnowledgeBaseGraphNode[];
  selectedPath: string;
  searchTerm: string;
  collapsed?: boolean;
  onSelect: (path: string) => void;
  onToggleCollapse?: () => void;
}

export const WikiGraphNodeList: React.FC<WikiGraphNodeListProps> = ({
  nodes,
  selectedPath,
  searchTerm,
  collapsed = false,
  onSelect,
  onToggleCollapse,
}) => {
  const { t } = useI18n();
  const toggleLabel = collapsed ? t('knowledgeBase.graph.actions.showNodes') : t('knowledgeBase.graph.actions.hideNodes');
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredNodes = React.useMemo(() => {
    if (!normalizedSearch) return nodes;
    return nodes.filter((node) => (
      node.label.toLowerCase().includes(normalizedSearch)
      || node.path.toLowerCase().includes(normalizedSearch)
      || node.type.toLowerCase().includes(normalizedSearch)
    ));
  }, [nodes, normalizedSearch]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className={cn(
        'flex h-10 items-center border-b bg-card px-3 text-sm font-medium',
        collapsed ? 'justify-center' : 'gap-2',
      )}>
        {!collapsed ? (
          <>
            <Network className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
            <span className="min-w-0 flex-1 truncate">{t('knowledgeBase.graph.nodes.title')}</span>
            <Badge variant="outline">{filteredNodes.length}</Badge>
          </>
        ) : null}
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
            <ChevronLeft className={cn('h-3.5 w-3.5 transition-transform', collapsed && 'rotate-180')} />
          </Button>
        ) : null}
      </div>
      {collapsed ? (
        <div className="flex flex-1 items-start justify-center pt-3">
          <Network className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
        </div>
      ) : (
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-1 p-2">
            {filteredNodes.map((node) => (
              <button
                key={node.id}
                type="button"
                className={cn(
                  'w-full rounded-md px-3 py-2 text-left text-sm hover:bg-muted',
                  selectedPath === node.path && 'bg-muted font-medium',
                )}
                onClick={() => onSelect(node.path)}
              >
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <span className="truncate">{node.label}</span>
                  <Badge variant="secondary" className="shrink-0">{node.degree}</Badge>
                </div>
                <div className="truncate text-xs text-muted-foreground">{node.path}</div>
              </button>
            ))}
            {filteredNodes.length === 0 ? (
              <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                {t('knowledgeBase.graph.nodes.empty')}
              </div>
            ) : null}
          </div>
        </ScrollArea>
      )}
    </div>
  );
};
