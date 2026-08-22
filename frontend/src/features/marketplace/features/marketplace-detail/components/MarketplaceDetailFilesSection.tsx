import React from 'react';
import { FileArchive, FileText, RefreshCw, Sparkles } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { Button } from '@/shared/components/ui/button';
import {
  buildTree,
  FileManagementSidebarWorkflow,
  FileTreePanel,
  parseFileTree,
  useFileManagementWorkbenchWorkflow,
  type FileTreeNode,
} from '@/shared/components/file-workbench';
import { FileViewerWorkbench, useFileViewerTabs } from '@/shared/components/file-workbench/viewer-entry';
import type { FileViewerWorkbenchAdapter } from '@/shared/components/file-workbench/viewer-entry';
import type { MarketplaceTargetClient } from '@/features/marketplace/model/marketplaceTypes';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  listPackageFilesTree,
  listSkillTree,
  loadPackageFile,
  loadSkillFile,
} from '../../../api/marketplaceApi';
import { createReadonlyMarketplaceViewerAdapter } from '../adapters/marketplaceReadonlyViewerAdapter';
import { MarketplaceResourceLoadError } from '../../../components/MarketplaceResourceLoadError';
import { useMarketplaceResourceSession } from '../../../model/marketplaceResourceSession';
import {
  MarketplaceShellAdapter,
  type MarketplaceShellColumnSurface,
  type MarketplaceShellMainSurface,
} from '../../../components/MarketplaceShellAdapter';

export interface MarketplaceDetailFilesRenderSurface {
  kind: 'regions';
  navigator: MarketplaceShellColumnSurface;
  main: MarketplaceShellMainSurface;
}

interface MarketplaceDetailFilesSectionProps {
  mode: 'package' | 'skills';
  targetClient: MarketplaceTargetClient;
  packageId: string;
  rootLabel?: string;
  renderSurface?: (surface: MarketplaceDetailFilesRenderSurface) => React.ReactNode;
}

export const MarketplaceDetailFilesSection: React.FC<MarketplaceDetailFilesSectionProps> = ({
  mode,
  targetClient,
  packageId,
  rootLabel,
  renderSurface,
}) => {
  const [nodes, setNodes] = React.useState<FileTreeNode[] | null>(null);
  const [loadError, setLoadError] = React.useState(false);
  const {
    identityGeneration,
    identityKey,
    session,
  } = useMarketplaceResourceSession({
    targetClient,
    packageId,
    resourceType: `detail-${mode}`,
  }, '');

  React.useLayoutEffect(() => {
    setNodes(null);
    setLoadError(false);
  }, [identityGeneration]);

  const loadTree = React.useCallback(async () => {
    setNodes(null);
    setLoadError(false);
    await session.query(
      identityGeneration,
      'detail-tree',
      () => (
        mode === 'skills'
          ? listSkillTree(targetClient, packageId)
          : listPackageFilesTree(targetClient, packageId)
      ),
      {
        onSuccess: (nextNodes) => {
          setNodes(buildTree(parseFileTree(nextNodes)));
        },
        onError: () => {
          setLoadError(true);
        },
      },
    );
  }, [identityGeneration, mode, packageId, targetClient, session]);

  React.useEffect(() => {
    void loadTree();
  }, [loadTree]);

  const loadContent = React.useCallback(async (path: string) => {
    const resource = await session.run(
      identityGeneration,
      `detail-content:${path}`,
      () => (
        mode === 'skills'
          ? loadSkillFile(targetClient, packageId, path)
          : loadPackageFile(targetClient, packageId, path)
      ),
    );
    return resource.content;
  }, [identityGeneration, mode, packageId, targetClient, session]);

  if (loadError) {
    return <MarketplaceResourceLoadError onRetry={() => { void loadTree(); }} />;
  }
  if (!nodes) return <LoadingSpinner className="h-full" />;

  return (
    <MarketplaceReadOnlyFileTreeViewer
      key={identityKey}
      titleKey={mode === 'skills'
        ? 'marketplace.editor.fileManager.skills.title'
        : 'marketplace.editor.fileManager.packageFiles.title'}
      icon={mode === 'skills' ? Sparkles : FileArchive}
      initialNodes={nodes}
      rootLabel={rootLabel}
      loadContent={loadContent}
      renderSurface={renderSurface}
    />
  );
};

interface MarketplaceReadOnlyFileTreeViewerProps {
  titleKey: string;
  icon: React.ComponentType<{ className?: string }>;
  initialNodes: FileTreeNode[];
  rootLabel?: string;
  loadContent: (path: string) => Promise<string>;
  renderSurface?: (surface: MarketplaceDetailFilesRenderSurface) => React.ReactNode;
}

const MarketplaceReadOnlyFileTreeViewer: React.FC<MarketplaceReadOnlyFileTreeViewerProps> = ({
  titleKey,
  icon: Icon,
  initialNodes,
  rootLabel,
  loadContent,
  renderSurface,
}) => {
  const { t } = useI18n();
  const [contents, setContents] = React.useState<Record<string, string>>({});
  const [contentErrorPath, setContentErrorPath] = React.useState<string | null>(null);
  const [isContentLoading, setIsContentLoading] = React.useState(false);
  const contentsRef = React.useRef(contents);
  const contentRequestsRef = React.useRef(new Map<string, Promise<string>>());
  contentsRef.current = contents;
  const fileTabs = useFileViewerTabs();
  const loadAndOpenFile = React.useCallback(async (node: FileTreeNode) => {
    if (node.type !== 'file') return;
    setContentErrorPath(null);
    setIsContentLoading(true);
    try {
      let content = contentsRef.current[node.path];
      if (content === undefined) {
        let request = contentRequestsRef.current.get(node.path);
        if (!request) {
          request = loadContent(node.path);
          contentRequestsRef.current.set(node.path, request);
        }
        try {
          content = await request;
        } finally {
          if (contentRequestsRef.current.get(node.path) === request) {
            contentRequestsRef.current.delete(node.path);
          }
        }
      }
      setContents(current => ({ ...current, [node.path]: content }));
      fileTabs.openFile(node, content);
    } catch {
      setContentErrorPath(node.path);
    } finally {
      setIsContentLoading(false);
    }
  }, [fileTabs, loadContent]);
  const workflow = useFileManagementWorkbenchWorkflow({
    initialNodes,
    initialExpandedIds: [],
    initialSelectedId: null,
    enableMultiSelect: false,
    onOpenFile: (node) => {
      void loadAndOpenFile(node);
    },
  });
  const { treeState, handleNodeClick, handleNodeDoubleClick } = workflow;
  const viewerAdapter = React.useMemo<FileViewerWorkbenchAdapter>(() => createReadonlyMarketplaceViewerAdapter({
    getNode: path => treeState.flatNodes.find(item => item.path === path),
    getContent: path => contentsRef.current[path] ?? '',
  }), [treeState.flatNodes]);
  const sidebarManager = React.useMemo(() => ({
    state: treeState,
    loadTree: async () => undefined,
  }), [treeState]);

  const navigator = {
    content: ({ collapsed }: { collapsed: boolean }) => collapsed ? null : (
      <div className="flex h-full min-h-0 flex-col">
        <FileManagementSidebarWorkflow
          manager={sidebarManager}
          title={t(titleKey)}
          searchPlaceholder={t('marketplace.editor.fileManager.search.placeholder')}
          headerIcon={Icon}
          capabilities={{}}
          showHeader={false}
          showToolbar={false}
          isCollapsed={false}
          onToggleCollapse={() => undefined}
          renderBody={() => (
            <div className="flex h-full min-h-0 flex-col">
              <FileTreePanel
                state={treeState}
                onNodeClick={handleNodeClick}
                onNodeDoubleClick={handleNodeDoubleClick}
                enableSearch={false}
                enableToolbar={false}
                enableMultiSelectBar={false}
                enableBottomStatusBar={false}
                enableDragDrop={false}
                className="flex-1"
              />
              {rootLabel ? (
                <div className="flex items-center gap-2 border-t border-border bg-muted/30 px-3 py-1.5">
                  <span className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    {t('marketplace.editor.fileManager.packageFiles.rootLabel')}
                  </span>
                  <span className="truncate font-mono text-xs text-foreground" title={rootLabel}>
                    {rootLabel}
                  </span>
                </div>
              ) : null}
            </div>
          )}
        />
      </div>
    ),
    accessibleLabel: t(titleKey),
    preset: 'navigator',
    header: {
      leading: <Icon className="h-4 w-4 shrink-0 text-sidebar-primary" />,
      title: t(titleKey),
      actions: (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => { void sidebarManager.loadTree(); }}
            disabled={treeState.isLoading}
            aria-label={t('marketplace.detail.viewer.refresh')}
            title={t('marketplace.detail.viewer.refresh')}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${treeState.isLoading ? 'animate-spin' : ''}`} />
          </Button>
        ),
    },
  } satisfies MarketplaceDetailFilesRenderSurface['navigator'];

  const main = {
    content: (
      <div className="h-full min-w-0 flex-1 overflow-hidden">
          {contentErrorPath ? (
            <MarketplaceResourceLoadError
              onRetry={() => {
                const node = treeState.flatNodes.find(item => item.path === contentErrorPath);
                if (node) void loadAndOpenFile(node);
              }}
            />
          ) : isContentLoading ? (
            <LoadingSpinner className="h-full" />
          ) : fileTabs.tabs.length === 0 ? (
            <EmptyState icon={FileText} title={t('marketplace.editor.fileManager.viewer.noFile')} />
          ) : (
            <FileViewerWorkbench
              tabs={fileTabs.tabs}
              activeTabId={fileTabs.activeTabId}
              adapter={viewerAdapter}
              readOnly
              capabilities={{
                canEdit: false,
                canSave: false,
                canReadBlob: true,
                canCopyPath: true,
                canCloseTabs: true,
              }}
              onTabsChange={fileTabs.applyTabsChange}
              onActiveTabChange={fileTabs.setActiveTabId}
              className="h-full"
            />
          )}
      </div>
    ),
    accessibleLabel: t('marketplace.detail.viewer.contentRegion'),
  } satisfies MarketplaceDetailFilesRenderSurface['main'];

  const surface: MarketplaceDetailFilesRenderSurface = {
    kind: 'regions',
    navigator,
    main,
  };

  return renderSurface
    ? renderSurface(surface)
    : <MarketplaceShellAdapter surface={surface} />;
};
