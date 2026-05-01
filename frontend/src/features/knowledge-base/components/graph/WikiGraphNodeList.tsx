import React from 'react';
import { Network } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type { KnowledgeBaseGraphNode } from '@/shared/types/knowledgeBase';

interface WikiGraphNodeListProps {
  nodes: KnowledgeBaseGraphNode[];
  selectedPath: string;
  searchTerm: string;
  onSelect: (path: string) => void;
}

export const WikiGraphNodeList: React.FC<WikiGraphNodeListProps> = ({
  nodes,
  selectedPath,
  searchTerm,
  onSelect,
}) => {
  const { t } = useI18n();
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
      <div className="flex items-center gap-2 border-b px-3 py-2 text-sm font-medium">
        <Network className="h-4 w-4 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate">{t('knowledgeBase.graph.nodes.title')}</span>
        <Badge variant="outline">{filteredNodes.length}</Badge>
      </div>
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
    </div>
  );
};
