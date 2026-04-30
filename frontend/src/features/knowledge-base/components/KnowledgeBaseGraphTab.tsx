import React from 'react';
import Graph from 'graphology';
import { Maximize, Network, RefreshCw, Search, X, ZoomIn, ZoomOut } from 'lucide-react';
import { SigmaContainer, useLoadGraph, useRegisterEvents, useSigma } from '@react-sigma/core';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import '@react-sigma/core/lib/style.css';
import { apiClient } from '@/shared/api/apiClient';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { getKnowledgeBaseGraph } from '@/features/knowledge-base/api/knowledgeBaseApi';
import type { KnowledgeBaseGraphEdge, KnowledgeBaseGraphNode, KnowledgeBaseGraphResponse } from '@/shared/types/knowledgeBase';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';

interface KnowledgeBaseGraphTabProps {
  knowledgeBaseId: string;
}

const TYPE_COLORS: Record<string, string> = {
  overview: '#f59e0b',
  entity: '#2563eb',
  concept: '#7c3aed',
  source: '#ea580c',
  synthesis: '#dc2626',
  comparison: '#0d9488',
  decision: '#be123c',
  project: '#16a34a',
  query: '#059669',
  page: '#64748b',
};

const BASE_NODE_SIZE = 7;
const MAX_NODE_SIZE = 26;

const getNodeColor = (type: string): string => TYPE_COLORS[type] ?? TYPE_COLORS.page;

const getNodeSize = (degree: number, maxDegree: number): number => {
  if (maxDegree <= 0) {
    return BASE_NODE_SIZE;
  }
  return BASE_NODE_SIZE + Math.sqrt(degree / maxDegree) * (MAX_NODE_SIZE - BASE_NODE_SIZE);
};

const normalizePathForApi = (path: string): string => (path.startsWith('/') ? path : `/${path}`);

const reasonLabelKey = (type: string): string => `knowledgeBase.graph.reasons.${type}`;

const NODE_POSITION_CACHE = new Map<string, { x: number; y: number }>();
let lastLayoutKey = '';

const GraphLoader: React.FC<{
  nodes: KnowledgeBaseGraphNode[];
  edges: KnowledgeBaseGraphEdge[];
}> = ({ nodes, edges }) => {
  const loadGraph = useLoadGraph();

  React.useEffect(() => {
    const graph = new Graph({ type: 'undirected' });
    const maxDegree = Math.max(...nodes.map((node) => node.degree), 1);
    const layoutKey = `${nodes.map((node) => node.id).sort().join('|')}::${edges.length}`;
    const needsLayout = layoutKey !== lastLayoutKey;

    nodes.forEach((node) => {
      const cached = NODE_POSITION_CACHE.get(node.id);
      graph.addNode(node.id, {
        x: cached?.x ?? Math.random() * 100,
        y: cached?.y ?? Math.random() * 100,
        label: node.label,
        size: getNodeSize(node.degree, maxDegree),
        color: getNodeColor(node.type),
        nodeType: node.type,
        nodePath: node.path,
      });
    });

    const maxWeight = Math.max(...edges.map((edge) => edge.weight), 1);
    edges.forEach((edge) => {
      if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) {
        return;
      }
      const key = edge.id || `${edge.source}--${edge.target}`;
      if (graph.hasEdge(key)) {
        return;
      }
      const normalizedWeight = Math.max(edge.weight / maxWeight, 0.15);
      graph.addEdgeWithKey(key, edge.source, edge.target, {
        color: `rgba(71,85,105,${0.25 + normalizedWeight * 0.55})`,
        size: 0.7 + normalizedWeight * 3.8,
        weight: edge.weight,
      });
    });

    if (needsLayout && nodes.length > 1) {
      const settings = forceAtlas2.inferSettings(graph);
      forceAtlas2.assign(graph, {
        iterations: nodes.length > 80 ? 180 : 120,
        settings: {
          ...settings,
          gravity: 1,
          scalingRatio: 2,
          strongGravityMode: true,
          barnesHutOptimize: nodes.length > 50,
        },
      });
      lastLayoutKey = layoutKey;
      graph.forEachNode((nodeId, attributes) => {
        NODE_POSITION_CACHE.set(nodeId, { x: attributes.x, y: attributes.y });
      });
    }

    loadGraph(graph);
  }, [edges, loadGraph, nodes]);

  return null;
};

const GraphInteractions: React.FC<{
  highlightedNodes: Set<string>;
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string) => void;
}> = ({ highlightedNodes, selectedNodeId, onNodeSelect }) => {
  const sigma = useSigma();
  const registerEvents = useRegisterEvents();

  React.useEffect(() => {
    registerEvents({
      clickNode: ({ node }) => onNodeSelect(node),
      enterNode: ({ node }) => {
        const graph = sigma.getGraph();
        const visible = new Set(graph.neighbors(node));
        visible.add(node);
        sigma.getContainer().style.cursor = 'pointer';
        graph.forEachNode((candidate) => {
          if (!visible.has(candidate)) {
            graph.setNodeAttribute(candidate, 'dimmed', true);
          }
        });
        graph.forEachEdge((edge, _attrs, source, target) => {
          if (source === node || target === node) {
            graph.setEdgeAttribute(edge, 'highlighted', true);
          } else {
            graph.setEdgeAttribute(edge, 'dimmed', true);
          }
        });
        sigma.refresh();
      },
      leaveNode: () => {
        const graph = sigma.getGraph();
        sigma.getContainer().style.cursor = 'default';
        graph.forEachNode((node) => {
          graph.removeNodeAttribute(node, 'dimmed');
        });
        graph.forEachEdge((edge) => {
          graph.removeEdgeAttribute(edge, 'highlighted');
          graph.removeEdgeAttribute(edge, 'dimmed');
        });
        sigma.refresh();
      },
    });
  }, [onNodeSelect, registerEvents, sigma]);

  React.useEffect(() => {
    const graph = sigma.getGraph();
    graph.forEachNode((node) => {
      const isHighlighted = highlightedNodes.has(node) || node === selectedNodeId;
      if (highlightedNodes.size > 0 || selectedNodeId) {
        if (isHighlighted) {
          graph.setNodeAttribute(node, 'focused', true);
          graph.removeNodeAttribute(node, 'searchDimmed');
        } else {
          graph.setNodeAttribute(node, 'searchDimmed', true);
          graph.removeNodeAttribute(node, 'focused');
        }
      } else {
        graph.removeNodeAttribute(node, 'focused');
        graph.removeNodeAttribute(node, 'searchDimmed');
      }
    });
    graph.forEachEdge((edge, _attrs, source, target) => {
      const bothVisible = highlightedNodes.has(source) && highlightedNodes.has(target);
      if (highlightedNodes.size > 0 && bothVisible) {
        graph.setEdgeAttribute(edge, 'highlighted', true);
        graph.removeEdgeAttribute(edge, 'searchDimmed');
      } else if (highlightedNodes.size > 0) {
        graph.setEdgeAttribute(edge, 'searchDimmed', true);
        graph.removeEdgeAttribute(edge, 'highlighted');
      } else {
        graph.removeEdgeAttribute(edge, 'highlighted');
        graph.removeEdgeAttribute(edge, 'searchDimmed');
      }
    });
    sigma.refresh();
  }, [highlightedNodes, selectedNodeId, sigma]);

  return null;
};

const ZoomControls: React.FC = () => {
  const sigma = useSigma();
  const { t } = useI18n();

  return (
    <TooltipProvider>
      <div className="absolute right-3 top-3 flex flex-col gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8 bg-background/90"
              aria-label={t('knowledgeBase.graph.actions.zoomIn')}
              onClick={() => sigma.getCamera().animatedZoom({ duration: 180 })}
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t('knowledgeBase.graph.actions.zoomIn')}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8 bg-background/90"
              aria-label={t('knowledgeBase.graph.actions.zoomOut')}
              onClick={() => sigma.getCamera().animatedUnzoom({ duration: 180 })}
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t('knowledgeBase.graph.actions.zoomOut')}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8 bg-background/90"
              aria-label={t('knowledgeBase.graph.actions.fit')}
              onClick={() => sigma.getCamera().animatedReset({ duration: 240 })}
            >
              <Maximize className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t('knowledgeBase.graph.actions.fit')}</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
};

export const KnowledgeBaseGraphTab: React.FC<KnowledgeBaseGraphTabProps> = ({ knowledgeBaseId }) => {
  const { t } = useI18n();
  const [graph, setGraph] = React.useState<KnowledgeBaseGraphResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [query, setQuery] = React.useState('');
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null);
  const [previewContent, setPreviewContent] = React.useState('');
  const [isPreviewLoading, setIsPreviewLoading] = React.useState(false);

  const loadGraph = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await getKnowledgeBaseGraph(knowledgeBaseId);
      setGraph(result);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('knowledgeBase.graph.loadFailed'));
    } finally {
      setIsLoading(false);
    }
  }, [knowledgeBaseId, t]);

  React.useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];
  const nodeById = React.useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) ?? null : null;

  const highlightedNodes = React.useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return new Set<string>();
    }
    return new Set(
      nodes
        .filter((node) => (
          node.label.toLowerCase().includes(normalized) ||
          node.path.toLowerCase().includes(normalized) ||
          node.type.toLowerCase().includes(normalized)
        ))
        .map((node) => node.id),
    );
  }, [nodes, query]);

  const typeCounts = React.useMemo(() => {
    return nodes.reduce<Record<string, number>>((acc, node) => {
      acc[node.type] = (acc[node.type] ?? 0) + 1;
      return acc;
    }, {});
  }, [nodes]);

  const handleNodeSelect = React.useCallback(async (nodeId: string) => {
    const node = nodeById.get(nodeId);
    if (!node) {
      return;
    }
    setSelectedNodeId(nodeId);
    setIsPreviewLoading(true);
    setPreviewContent('');
    try {
      const response = await apiClient.get<{ content: string }>(
        `/knowledge-bases/${knowledgeBaseId}/files/content?path=${encodeURIComponent(normalizePathForApi(node.path))}`,
      );
      setPreviewContent(response.content ?? '');
    } catch {
      setPreviewContent(t('knowledgeBase.graph.previewLoadFailed'));
    } finally {
      setIsPreviewLoading(false);
    }
  }, [knowledgeBaseId, nodeById, t]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        {t('knowledgeBase.graph.loading')}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        <Network className="h-10 w-10 opacity-30" />
        <p className="max-w-md text-center text-destructive">{error}</p>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadGraph()}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          {t('knowledgeBase.common.actions.refresh')}
        </Button>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
        <Network className="h-10 w-10 opacity-30" />
        <p>{t('knowledgeBase.graph.emptyTitle')}</p>
        <p className="text-xs">{t('knowledgeBase.graph.emptyDescription')}</p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-shrink-0 items-center justify-between gap-3 border-b px-4 py-2">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Network className="h-4 w-4 text-muted-foreground" />
            {t('knowledgeBase.graph.title')}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Badge variant="outline">{t('knowledgeBase.graph.stats.pages', { count: nodes.length })}</Badge>
            <Badge variant="outline">{t('knowledgeBase.graph.stats.relationships', { count: edges.length })}</Badge>
          </div>
        </div>
        <div className="flex min-w-[220px] max-w-sm flex-1 items-center gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('knowledgeBase.graph.searchPlaceholder')}
              className="h-9 pl-8 pr-8"
              aria-label={t('knowledgeBase.graph.searchLabel')}
            />
            {query && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1 h-7 w-7"
                aria-label={t('knowledgeBase.graph.actions.clearSearch')}
                onClick={() => setQuery('')}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
          <Button type="button" variant="outline" size="sm" className="h-9 px-2" onClick={() => void loadGraph()}>
            <RefreshCw className="h-4 w-4" />
            <span className="sr-only">{t('knowledgeBase.common.actions.refresh')}</span>
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1 overflow-hidden bg-slate-50 dark:bg-slate-950">
          <SigmaContainer
            style={{ height: '100%', width: '100%', background: 'transparent' }}
            settings={{
              defaultNodeColor: '#64748b',
              defaultEdgeColor: '#94a3b8',
              labelSize: 12,
              labelWeight: 'bold',
              labelDensity: 0.35,
              labelRenderedSizeThreshold: 7,
              stagePadding: 36,
              nodeReducer: (_node, attributes) => {
                const next = { ...attributes };
                if (attributes.focused) {
                  next.size = (attributes.size ?? BASE_NODE_SIZE) * 1.45;
                  next.forceLabel = true;
                  next.zIndex = 10;
                }
                if (attributes.dimmed || attributes.searchDimmed) {
                  next.color = '#cbd5e1';
                  next.label = '';
                  next.size = (attributes.size ?? BASE_NODE_SIZE) * 0.6;
                }
                return next;
              },
              edgeReducer: (_edge, attributes) => {
                const next = { ...attributes };
                if (attributes.highlighted) {
                  next.color = '#0f172a';
                  next.size = Math.max(2, (attributes.size ?? 1) * 1.5);
                }
                if (attributes.dimmed || attributes.searchDimmed) {
                  next.color = '#e2e8f0';
                  next.size = 0.3;
                }
                return next;
              },
            }}
          >
            <GraphLoader nodes={nodes} edges={edges} />
            <GraphInteractions highlightedNodes={highlightedNodes} selectedNodeId={selectedNodeId} onNodeSelect={handleNodeSelect} />
            <ZoomControls />
          </SigmaContainer>

          <div className="absolute bottom-3 left-3 max-w-[280px] rounded-md border bg-background/95 px-3 py-2 text-xs shadow-sm">
            <div className="mb-1.5 font-medium">{t('knowledgeBase.graph.legend.title')}</div>
            <div className="grid max-h-36 gap-1 overflow-auto">
              {Object.entries(typeCounts).sort(([left], [right]) => left.localeCompare(right)).map(([type, count]) => (
                <div key={type} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: getNodeColor(type) }} />
                  <span className="min-w-0 flex-1 truncate">{t(`knowledgeBase.graph.types.${type}`, { defaultValue: type })}</span>
                  <span className="text-muted-foreground">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <aside className="flex w-96 flex-shrink-0 flex-col border-l bg-background">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <div className="min-w-0">
              <div className="text-sm font-medium">{selectedNode ? selectedNode.label : t('knowledgeBase.graph.preview.emptyTitle')}</div>
              <div className="truncate text-xs text-muted-foreground">
                {selectedNode ? selectedNode.path : t('knowledgeBase.graph.preview.emptyDescription')}
              </div>
            </div>
            {selectedNode && (
              <Button type="button" variant="ghost" size="icon" className="h-8 w-8" onClick={() => setSelectedNodeId(null)}>
                <X className="h-4 w-4" />
                <span className="sr-only">{t('knowledgeBase.graph.actions.closePreview')}</span>
              </Button>
            )}
          </div>
          {selectedNode ? (
            <>
              <div className="flex flex-wrap gap-2 border-b px-4 py-3 text-xs">
                <Badge variant="secondary">{t(`knowledgeBase.graph.types.${selectedNode.type}`, { defaultValue: selectedNode.type })}</Badge>
                <Badge variant="outline">{t('knowledgeBase.graph.stats.degree', { count: selectedNode.degree })}</Badge>
                <Badge variant="outline">{t('knowledgeBase.graph.stats.sources', { count: selectedNode.sources.length })}</Badge>
              </div>
              <ScrollArea className="min-h-0 flex-1">
                <div className="space-y-4 p-4">
                  <RelatedEdges
                    edges={edges}
                    selectedNodeId={selectedNode.id}
                    nodeById={nodeById}
                  />
                  {isPreviewLoading ? (
                    <div className="flex items-center text-sm text-muted-foreground">
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      {t('knowledgeBase.graph.preview.loading')}
                    </div>
                  ) : (
                    <MarkdownContent content={previewContent} variant="compact" />
                  )}
                </div>
              </ScrollArea>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
              {t('knowledgeBase.graph.preview.selectHint')}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
};

const RelatedEdges: React.FC<{
  edges: KnowledgeBaseGraphEdge[];
  selectedNodeId: string;
  nodeById: Map<string, KnowledgeBaseGraphNode>;
}> = ({ edges, selectedNodeId, nodeById }) => {
  const { t } = useI18n();
  const relatedEdges = edges
    .filter((edge) => edge.source === selectedNodeId || edge.target === selectedNodeId)
    .sort((left, right) => right.weight - left.weight)
    .slice(0, 8);

  if (relatedEdges.length === 0) {
    return null;
  }

  return (
    <section className="space-y-2">
      <div className="text-xs font-medium uppercase text-muted-foreground">{t('knowledgeBase.graph.preview.relationships')}</div>
      <div className="space-y-2">
        {relatedEdges.map((edge) => {
          const relatedId = edge.source === selectedNodeId ? edge.target : edge.source;
          const relatedNode = nodeById.get(relatedId);
          return (
            <div key={edge.id} className="rounded-md border bg-muted/20 p-2">
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="min-w-0 truncate font-medium">{relatedNode?.label ?? relatedId}</span>
                <Badge variant="outline">{edge.weight.toFixed(2)}</Badge>
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {edge.reasons.map((reason) => (
                  <Badge key={`${edge.id}-${reason.type}`} variant="secondary" className={cn('text-[10px] font-normal')}>
                    {t(reasonLabelKey(reason.type), { defaultValue: reason.type })}
                  </Badge>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default KnowledgeBaseGraphTab;
