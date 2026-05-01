import React from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';
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
import {
  KNOWLEDGE_BASE_COLLAPSED_COLUMN_WIDTH,
  KNOWLEDGE_BASE_DEFAULT_COLUMN_WIDTH,
  KNOWLEDGE_BASE_PREVIEW_COLUMN_WIDTH,
  ResizableSidebarHandle,
  useResizableSidebar,
} from '../knowledgeBasePanelLayout';

interface WikiGraphExplorerProps {
  knowledgeBaseId: string;
  selectedPath: string;
  onSelectedPathChange: (path: string) => void;
  onOpenInWiki: (path: string) => void;
  onSourceOpen: (path: string) => void;
}

interface StoredGraphLayout {
  leftWidth: number;
  rightWidth: number;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
}

const STORAGE_PREFIX = 'knowledge-base-graph-layout';

const loadStoredLayout = (knowledgeBaseId: string): StoredGraphLayout | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const stored = window.localStorage.getItem(`${STORAGE_PREFIX}:${knowledgeBaseId}`);
    if (!stored) {
      return null;
    }
    const parsed = JSON.parse(stored) as Partial<StoredGraphLayout>;
    if (typeof parsed.leftWidth !== 'number' || typeof parsed.rightWidth !== 'number') {
      return null;
    }

    return {
      leftWidth: parsed.leftWidth,
      rightWidth: parsed.rightWidth,
      leftCollapsed: Boolean(parsed.leftCollapsed),
      rightCollapsed: Boolean(parsed.rightCollapsed),
    };
  } catch {
    return null;
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
  const [mobilePanel, setMobilePanel] = React.useState<'nodes' | 'preview' | null>(null);
  const [controls, setControls] = React.useState<WikiGraphControls | null>(null);
  const isSmallScreen = useIsSmallGraphScreen();
  const initialLayoutRef = React.useRef(loadStoredLayout(knowledgeBaseId));

  const leftSidebar = useResizableSidebar({
    initialWidth: initialLayoutRef.current?.leftWidth ?? KNOWLEDGE_BASE_DEFAULT_COLUMN_WIDTH,
    initialCollapsed: initialLayoutRef.current?.leftCollapsed ?? false,
  });
  const rightSidebar = useResizableSidebar({
    initialWidth: initialLayoutRef.current?.rightWidth ?? KNOWLEDGE_BASE_PREVIEW_COLUMN_WIDTH,
    initialCollapsed: initialLayoutRef.current?.rightCollapsed ?? false,
    resizeFrom: 'left',
  });

  React.useEffect(() => {
    saveStoredLayout(knowledgeBaseId, {
      leftWidth: leftSidebar.width,
      rightWidth: rightSidebar.width,
      leftCollapsed: leftSidebar.collapsed,
      rightCollapsed: rightSidebar.collapsed,
    });
  }, [knowledgeBaseId, leftSidebar.collapsed, leftSidebar.width, rightSidebar.collapsed, rightSidebar.width]);

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

  const selectPath = React.useCallback((path: string) => {
    onSelectedPathChange(path);
    controls?.focusNode(graphNodeIdFromPath(path));
  }, [controls, onSelectedPathChange]);

  const toggleLeft = React.useCallback(() => {
    leftSidebar.setCollapsed(!leftSidebar.collapsed);
  }, [leftSidebar]);

  const toggleRight = React.useCallback(() => {
    rightSidebar.setCollapsed(!rightSidebar.collapsed);
  }, [rightSidebar]);

  const resetPanes = React.useCallback(() => {
    leftSidebar.setCollapsed(false);
    leftSidebar.setWidth(KNOWLEDGE_BASE_DEFAULT_COLUMN_WIDTH);
    rightSidebar.setCollapsed(false);
    rightSidebar.setWidth(KNOWLEDGE_BASE_PREVIEW_COLUMN_WIDTH);
  }, [leftSidebar, rightSidebar]);

  const renderPreview = (collapsed = false, onToggleCollapse?: () => void) => (
    <WikiGraphSelectionPanel
      kbId={knowledgeBaseId}
      selectedPath={effectiveSelectedPath}
      collapsed={collapsed}
      onNavigate={selectPath}
      onOpenInWiki={() => onOpenInWiki(effectiveSelectedPath)}
      onSourceOpen={onSourceOpen}
      onToggleCollapse={onToggleCollapse}
    />
  );

  const renderNodeList = (collapsed = false, onToggleCollapse?: () => void) => (
    <WikiGraphNodeList
      nodes={nodes}
      selectedPath={effectiveSelectedPath}
      searchTerm={searchTerm}
      collapsed={collapsed}
      onSelect={selectPath}
      onToggleCollapse={onToggleCollapse}
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
      {!isSmallScreen ? (
        <div data-testid="panel-group" className="flex min-h-0 flex-1">
          <aside
            data-testid="kb-graph-nodes"
            className="relative h-full shrink-0 border-r bg-muted/20"
            style={{ width: leftSidebar.collapsed ? KNOWLEDGE_BASE_COLLAPSED_COLUMN_WIDTH : leftSidebar.width }}
          >
            {renderNodeList(leftSidebar.collapsed, toggleLeft)}
            {!leftSidebar.collapsed ? (
              <ResizableSidebarHandle
                isResizing={leftSidebar.isResizing}
                onResizeStart={leftSidebar.startResize}
              />
            ) : null}
          </aside>
          <main data-testid="kb-graph-canvas" className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
            <WikiGraphToolbar
              searchTerm={searchTerm}
              isLoading={isLoading}
              onSearchTermChange={setSearchTerm}
              onFit={() => controls?.fit()}
              onZoomIn={() => controls?.zoomIn()}
              onZoomOut={() => controls?.zoomOut()}
              onResetLayout={resetPanes}
              onRefresh={() => void loadGraph()}
            />
            <div className="min-h-0 flex-1">
              <WikiGraphCanvas
                nodes={nodes}
                edges={edges}
                selectedPath={effectiveSelectedPath}
                onSelect={selectPath}
                onControlsReady={setControls}
              />
            </div>
          </main>
          <aside
            data-testid="kb-graph-preview"
            className="relative h-full shrink-0 border-l"
            style={{ width: rightSidebar.collapsed ? KNOWLEDGE_BASE_COLLAPSED_COLUMN_WIDTH : rightSidebar.width }}
          >
            {!rightSidebar.collapsed ? (
              <ResizableSidebarHandle
                side="left"
                isResizing={rightSidebar.isResizing}
                onResizeStart={rightSidebar.startResize}
              />
            ) : null}
            {renderPreview(rightSidebar.collapsed, toggleRight)}
          </aside>
        </div>
      ) : (
        <div className="relative flex min-h-0 flex-1 flex-col">
          <WikiGraphToolbar
            searchTerm={searchTerm}
            isLoading={isLoading}
            onSearchTermChange={setSearchTerm}
            onFit={() => controls?.fit()}
            onZoomIn={() => controls?.zoomIn()}
            onZoomOut={() => controls?.zoomOut()}
            onResetLayout={resetPanes}
            onRefresh={() => void loadGraph()}
          />
          <div className="relative min-h-0 flex-1">
            <WikiGraphCanvas
              nodes={nodes}
              edges={edges}
              selectedPath={effectiveSelectedPath}
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
              <div className="absolute inset-x-2 bottom-2 top-2 rounded-md border bg-background shadow-lg">
                <div className="flex h-full min-h-0 flex-col">
                  <div className="flex justify-end border-b px-2 py-2">
                    <Button type="button" variant="ghost" size="sm" onClick={() => setMobilePanel(null)}>
                      {t('knowledgeBase.graph.actions.closePanel')}
                    </Button>
                  </div>
                  <div className={cn('min-h-0 flex-1', mobilePanel === 'preview' && 'overflow-hidden')}>
                    {mobilePanel === 'nodes' ? renderNodeList() : renderPreview()}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};

