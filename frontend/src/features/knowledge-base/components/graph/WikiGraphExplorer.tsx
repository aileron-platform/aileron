import React from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';
import { Panel, PanelGroup, PanelResizeHandle, type ImperativePanelHandle } from 'react-resizable-panels';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { getKnowledgeBaseGraph } from '@/features/knowledge-base/api/knowledgeBaseApi';
import type { KnowledgeBaseGraphEdge, KnowledgeBaseGraphNode } from '@/shared/types/knowledgeBase';
import { DEFAULT_WIKI_PATH, graphNodeIdFromPath } from './graphUtils';
import { WikiGraphCanvas, type WikiGraphControls } from './WikiGraphCanvas';
import { WikiGraphNodeList } from './WikiGraphNodeList';
import { WikiGraphSelectionPanel } from './WikiGraphSelectionPanel';
import { WikiGraphToolbar } from './WikiGraphToolbar';

interface WikiGraphExplorerProps {
  knowledgeBaseId: string;
  selectedPath: string;
  onSelectedPathChange: (path: string) => void;
  onOpenInWiki: (path: string) => void;
  onSourceOpen: (path: string) => void;
}

interface StoredGraphLayout {
  sizes: number[];
  leftCollapsed: boolean;
  rightCollapsed: boolean;
}

const DEFAULT_LAYOUT = [22, 46, 32];
const STORAGE_PREFIX = 'knowledge-base-graph-layout';

const loadStoredLayout = (knowledgeBaseId: string): StoredGraphLayout => {
  if (typeof window === 'undefined') {
    return { sizes: DEFAULT_LAYOUT, leftCollapsed: false, rightCollapsed: false };
  }
  try {
    const stored = window.localStorage.getItem(`${STORAGE_PREFIX}:${knowledgeBaseId}`);
    if (!stored) {
      return { sizes: DEFAULT_LAYOUT, leftCollapsed: false, rightCollapsed: false };
    }
    const parsed = JSON.parse(stored) as Partial<StoredGraphLayout>;
    return {
      sizes: Array.isArray(parsed.sizes) && parsed.sizes.length === 3 ? parsed.sizes : DEFAULT_LAYOUT,
      leftCollapsed: Boolean(parsed.leftCollapsed),
      rightCollapsed: Boolean(parsed.rightCollapsed),
    };
  } catch {
    return { sizes: DEFAULT_LAYOUT, leftCollapsed: false, rightCollapsed: false };
  }
};

const saveStoredLayout = (knowledgeBaseId: string, layout: StoredGraphLayout) => {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(`${STORAGE_PREFIX}:${knowledgeBaseId}`, JSON.stringify(layout));
};

const useIsSmallGraphScreen = () => {
  const [isSmallScreen, setIsSmallScreen] = React.useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return false;
    }
    return window.matchMedia('(max-width: 1023px)').matches;
  });

  React.useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    const query = window.matchMedia('(max-width: 1023px)');
    const handleChange = () => setIsSmallScreen(query.matches);
    handleChange();
    query.addEventListener('change', handleChange);
    return () => query.removeEventListener('change', handleChange);
  }, []);

  return isSmallScreen;
};

export const WikiGraphExplorer: React.FC<WikiGraphExplorerProps> = ({
  knowledgeBaseId,
  selectedPath,
  onSelectedPathChange,
  onOpenInWiki,
  onSourceOpen,
}) => {
  const { t } = useI18n();
  const [nodes, setNodes] = React.useState<KnowledgeBaseGraphNode[]>([]);
  const [edges, setEdges] = React.useState<KnowledgeBaseGraphEdge[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [searchTerm, setSearchTerm] = React.useState('');
  const [layoutVersion, setLayoutVersion] = React.useState(0);
  const [mobilePanel, setMobilePanel] = React.useState<'nodes' | 'preview' | null>(null);
  const [controls, setControls] = React.useState<WikiGraphControls | null>(null);
  const [layout, setLayout] = React.useState<StoredGraphLayout>(() => loadStoredLayout(knowledgeBaseId));
  const isSmallScreen = useIsSmallGraphScreen();
  const leftPanelRef = React.useRef<ImperativePanelHandle>(null);
  const rightPanelRef = React.useRef<ImperativePanelHandle>(null);

  const effectiveSelectedPath = React.useMemo(() => {
    if (selectedPath) return selectedPath;
    return nodes[0]?.path ?? DEFAULT_WIKI_PATH;
  }, [nodes, selectedPath]);

  const loadGraph = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const graph = await getKnowledgeBaseGraph(knowledgeBaseId);
      setNodes(graph.nodes);
      setEdges(graph.edges);
      if (!selectedPath && graph.nodes[0]?.path) {
        onSelectedPathChange(graph.nodes[0].path);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('knowledgeBase.graph.loadFailed'));
    } finally {
      setIsLoading(false);
    }
  }, [knowledgeBaseId, onSelectedPathChange, selectedPath, t]);

  React.useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  React.useEffect(() => {
    setLayout(loadStoredLayout(knowledgeBaseId));
  }, [knowledgeBaseId]);

  const persistLayout = React.useCallback((next: StoredGraphLayout) => {
    setLayout(next);
    saveStoredLayout(knowledgeBaseId, next);
  }, [knowledgeBaseId]);

  const handleLayout = React.useCallback((sizes: number[]) => {
    persistLayout({ ...layout, sizes });
  }, [layout, persistLayout]);

  const selectPath = React.useCallback((path: string) => {
    onSelectedPathChange(path);
    controls?.focusNode(graphNodeIdFromPath(path));
  }, [controls, onSelectedPathChange]);

  const toggleLeft = React.useCallback(() => {
    const nextCollapsed = !layout.leftCollapsed;
    if (nextCollapsed) leftPanelRef.current?.collapse();
    else leftPanelRef.current?.expand(16);
    persistLayout({ ...layout, leftCollapsed: nextCollapsed });
  }, [layout, persistLayout]);

  const toggleRight = React.useCallback(() => {
    const nextCollapsed = !layout.rightCollapsed;
    if (nextCollapsed) rightPanelRef.current?.collapse();
    else rightPanelRef.current?.expand(24);
    persistLayout({ ...layout, rightCollapsed: nextCollapsed });
  }, [layout, persistLayout]);

  const resetPanes = React.useCallback(() => {
    leftPanelRef.current?.resize(DEFAULT_LAYOUT[0]);
    rightPanelRef.current?.resize(DEFAULT_LAYOUT[2]);
    persistLayout({ sizes: DEFAULT_LAYOUT, leftCollapsed: false, rightCollapsed: false });
  }, [persistLayout]);

  const resetGraph = React.useCallback(() => {
    setLayoutVersion((current) => current + 1);
    controls?.reset();
  }, [controls]);

  const preview = (
    <WikiGraphSelectionPanel
      kbId={knowledgeBaseId}
      selectedPath={effectiveSelectedPath}
      onNavigate={selectPath}
      onOpenInWiki={() => onOpenInWiki(effectiveSelectedPath)}
      onSourceOpen={onSourceOpen}
    />
  );

  const nodeList = (
    <WikiGraphNodeList
      nodes={nodes}
      selectedPath={effectiveSelectedPath}
      searchTerm={searchTerm}
      onSelect={selectPath}
    />
  );

  if (isLoading && nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {t('knowledgeBase.graph.loading')}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-sm text-muted-foreground">
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadGraph()}>
          {t('knowledgeBase.common.actions.refresh')}
        </Button>
      </div>
    );
  }

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-background">
      <WikiGraphToolbar
        searchTerm={searchTerm}
        leftCollapsed={layout.leftCollapsed}
        rightCollapsed={layout.rightCollapsed}
        isLoading={isLoading}
        hasSelection={Boolean(effectiveSelectedPath)}
        onSearchTermChange={setSearchTerm}
        onFit={() => controls?.fit()}
        onZoomIn={() => controls?.zoomIn()}
        onZoomOut={() => controls?.zoomOut()}
        onReset={resetGraph}
        onRefresh={() => void loadGraph()}
        onOpenInWiki={() => onOpenInWiki(effectiveSelectedPath)}
        onToggleLeft={toggleLeft}
        onToggleRight={toggleRight}
      />

      {!isSmallScreen ? (
        <div className="min-h-0 flex-1">
          <PanelGroup direction="horizontal" onLayout={handleLayout}>
            <Panel
              id="kb-graph-nodes"
              ref={leftPanelRef}
              order={1}
              defaultSize={layout.sizes[0]}
              minSize={16}
              maxSize={35}
              collapsible
              collapsedSize={0}
              onCollapse={() => persistLayout({ ...layout, leftCollapsed: true })}
              onExpand={() => persistLayout({ ...layout, leftCollapsed: false })}
            >
              <aside className="h-full border-r bg-muted/20">{nodeList}</aside>
            </Panel>
            <GraphResizeHandle onReset={resetPanes} />
            <Panel id="kb-graph-canvas" order={2} defaultSize={layout.sizes[1]} minSize={30}>
              <main className="h-full min-h-0">
                <WikiGraphCanvas
                  nodes={nodes}
                  edges={edges}
                  selectedPath={effectiveSelectedPath}
                  layoutVersion={layoutVersion}
                  onSelect={selectPath}
                  onControlsReady={setControls}
                />
              </main>
            </Panel>
            <GraphResizeHandle onReset={resetPanes} />
            <Panel
              id="kb-graph-preview"
              ref={rightPanelRef}
              order={3}
              defaultSize={layout.sizes[2]}
              minSize={24}
              maxSize={45}
              collapsible
              collapsedSize={0}
              onCollapse={() => persistLayout({ ...layout, rightCollapsed: true })}
              onExpand={() => persistLayout({ ...layout, rightCollapsed: false })}
            >
              <aside className="h-full border-l">{preview}</aside>
            </Panel>
          </PanelGroup>
        </div>
      ) : (
        <div className="relative min-h-0 flex-1">
          <WikiGraphCanvas
            nodes={nodes}
            edges={edges}
            selectedPath={effectiveSelectedPath}
            layoutVersion={layoutVersion}
            onSelect={(path) => {
              selectPath(path);
              setMobilePanel('preview');
            }}
            onControlsReady={setControls}
          />
          <div className="absolute bottom-3 left-3 right-3 flex gap-2">
            <Button type="button" variant="secondary" className="flex-1" onClick={() => setMobilePanel('nodes')}>
              {t('knowledgeBase.graph.nodes.title')}
            </Button>
            <Button type="button" variant="secondary" className="flex-1" onClick={() => setMobilePanel('preview')}>
              {t('knowledgeBase.graph.preview.title')}
            </Button>
          </div>
          {mobilePanel ? (
            <div className="absolute inset-x-2 bottom-2 top-14 rounded-md border bg-background shadow-lg">
              <div className="flex h-full min-h-0 flex-col">
                <div className="flex justify-end border-b px-2 py-2">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setMobilePanel(null)}>
                    {t('knowledgeBase.graph.actions.closePanel')}
                  </Button>
                </div>
                <div className={cn('min-h-0 flex-1', mobilePanel === 'preview' && 'overflow-hidden')}>
                  {mobilePanel === 'nodes' ? nodeList : preview}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};

const GraphResizeHandle: React.FC<{ onReset: () => void }> = ({ onReset }) => (
  <PanelResizeHandle
    className="w-1 cursor-col-resize bg-border transition-colors hover:bg-primary/60 data-[resize-handle-active]:bg-primary"
    onDoubleClick={onReset}
  />
);
