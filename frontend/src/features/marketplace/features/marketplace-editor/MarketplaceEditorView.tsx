import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Bot,
  ChevronRight,
  Command,
  FileArchive,
  FileText,
  FolderPlus,
  Info,
  Network,
  Wand2,
  Workflow,
  Zap,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Tabs, TabsContent } from '@/shared/components/ui/tabs';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageDetail, MarketplacePackageFile, MarketplaceProvider } from '@/shared/types/marketplace';
import {
  type FileTreeNode,
} from '@/shared/components/file-workbench';
import { MarketplaceEditorLeaveDialog } from '../../components/MarketplaceEditorLifecycleDialogs';
import { MarketplaceFilesSection, shouldUpdateMarketplaceEditorFileContent } from '../../components/MarketplaceFilesSection';
import { MarketplacePackageHeader } from '../../components/MarketplacePackageHeader';
import { MarketplaceTopTabs } from '../../components/MarketplaceTopTabs';
import { MarketplaceEditorBasicSection } from './MarketplaceEditorBasicSection';
import { MarketplaceAgentsMdEditor, MarketplaceMarkdownEditorViewer } from './MarketplaceEditorDocumentSection';
import { MarketplaceEditorHookSection } from './MarketplaceEditorHookSection';
import { MarketplaceEditorMcpSection, marketplaceApplyMcpItemsToPackageFiles } from './MarketplaceEditorMcpSection';
import {
  emptyMarketplaceFeatureItems,
  marketplaceApplyPackageFiles,
  marketplaceApplyResourceItemsToPackageFiles,
  marketplaceMarkdownManagedPrefixes,
  marketplacePackageFileFromResourceItem,
  marketplaceFeatureItemsFromDetail,
  marketplaceTextPackageFile,
  type MarketplaceEditorFeatureItems,
} from './marketplaceEditorFeatureItems';
import { type MarketplaceEditorResourceItem, type MarketplaceMarkdownEditorTab } from './marketplaceEditorResourceItems';
import { parseMarketplaceJsonObject, type MarketplaceRequiredDraft } from './marketplaceEditorRequiredDraft';
import { createPackage, getPackage, savePackage as saveMarketplacePackage } from '../../api/marketplaceApi';
import {
  createMarketplacePackageFileTree,
} from '../../adapters/marketplaceFileTreeAdapter';
import { getMarketplaceFeatureCountByDirectory } from '../../utils/marketplaceFeatureCounts';

export interface MarketplaceEditorViewProps {
  mode: 'create' | 'edit';
}

export { shouldUpdateMarketplaceEditorFileContent };

const marketplaceEditorTabs = ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'outputStyle', 'policies', 'skills', 'files'] as const;
type MarketplaceEditorTab = typeof marketplaceEditorTabs[number];

const providerEditorTabs: Record<MarketplaceProvider, MarketplaceEditorTab[]> = {
  'claude-code': ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'outputStyle', 'skills', 'files'],
  codex: ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'skills', 'files'],
  gemini: ['basic', 'agentsMd', 'hooks', 'agents', 'commands', 'policies', 'skills', 'files'],
};

const tabIcons: Record<MarketplaceEditorTab, React.ComponentType<{ className?: string }>> = {
  basic: Info,
  agentsMd: FileText,
  skills: Wand2,
  commands: Command,
  agents: Bot,
  hooks: Zap,
  mcp: Network,
  outputStyle: Wand2,
  policies: Workflow,
  files: FileArchive,
};

const getMarketplaceEditorTabLabelKey = (
  provider: MarketplaceProvider,
  tab: MarketplaceEditorTab,
): string => {
  if (provider === 'claude-code' && tab === 'agentsMd') {
    return 'marketplace.editor.tabs.claudeMd';
  }
  if (provider === 'gemini' && tab === 'agentsMd') {
    return 'marketplace.editor.tabs.geminiMd';
  }
  if (tab === 'agents') {
    return 'marketplace.editor.tabs.subagents';
  }
  if (tab === 'commands') {
    return 'marketplace.editor.tabs.slashCommand';
  }
  return `marketplace.editor.tabs.${tab}`;
};

const countMarketplaceFileNodes = (nodes: FileTreeNode[]): number => (
  nodes.reduce((count, node) => (
    count + (node.type === 'file' ? 1 : 0) + (node.children ? countMarketplaceFileNodes(node.children) : 0)
  ), 0)
);

const getMarketplacePackageRoot = (provider: MarketplaceProvider, packageId: string): string => (
  provider === 'gemini'
    ? `gemini/extensions/${packageId}`
    : `${provider}/plugins/${packageId}`
);

export const MarketplaceEditorView: React.FC<MarketplaceEditorViewProps> = ({ mode }) => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const params = useParams();
  const routeProvider = params.provider === 'codex' || params.provider === 'gemini' || params.provider === 'claude-code'
    ? params.provider
    : null;
  const [provider, setProvider] = React.useState<MarketplaceProvider | null>(
    routeProvider ?? (mode === 'edit' ? 'claude-code' : null),
  );
  const [packageId, setPackageId] = React.useState(params.packageId ?? '');
  const [displayName, setDisplayName] = React.useState(params.packageId ?? '');
  const [description, setDescription] = React.useState('');
  const [isDirty, setIsDirty] = React.useState(false);
  const [resourceCommitVersion, setResourceCommitVersion] = React.useState(0);
  const [resourceDiscardVersion, setResourceDiscardVersion] = React.useState(0);
  const [activeTab, setActiveTab] = React.useState<MarketplaceEditorTab>('basic');
  const [saveStatus, setSaveStatus] = React.useState<'idle' | 'success' | 'error' | 'conflict'>('idle');
  const [showLeaveDialog, setShowLeaveDialog] = React.useState(false);
  const [revision, setRevision] = React.useState('');
  const [loadedDetail, setLoadedDetail] = React.useState<MarketplacePackageDetail | null>(null);
  const [packageFiles, setPackageFiles] = React.useState<MarketplacePackageFile[]>([]);
  const [requiredDraft, setRequiredDraft] = React.useState<MarketplaceRequiredDraft | null>(null);
  const visibleEditorTabs = provider ? providerEditorTabs[provider] : [];
  const resolvedPackageId = packageId || t('marketplace.editor.fields.packageIdPreviewFallback');
  const resolvedDisplayName = displayName || packageId || t('marketplace.editor.fields.displayNamePlaceholder');
  const packageRoot = provider ? getMarketplacePackageRoot(provider, resolvedPackageId) : '';
  const featureItems = React.useMemo<MarketplaceEditorFeatureItems | null>(
    () => {
      if (!provider) return null;
      return marketplaceFeatureItemsFromDetail(loadedDetail) ?? emptyMarketplaceFeatureItems();
    },
    [loadedDetail, provider],
  );
  const skillsFileManagerKey = React.useMemo(
    () => `${provider ?? 'none'}-skills-${featureItems?.skills.map(item => item.path).join('|') ?? 'empty'}`,
    [featureItems?.skills, provider],
  );
  const packageFileTree = React.useMemo(
    () => {
      if (!provider) return [];
      const tree = createMarketplacePackageFileTree({
        provider,
        packageRoot,
        displayName: resolvedDisplayName,
        packageFiles,
      });
      return packageFiles.length > 0 && tree[0]?.path === `/${packageRoot}`
        ? tree[0].children ?? []
        : tree;
    },
    [packageFiles, packageRoot, provider, resolvedDisplayName],
  );

  const markDirty = () => {
    setIsDirty(true);
    setSaveStatus('idle');
  };
  const handleMcpItemsChange = React.useCallback((items: MarketplaceEditorResourceItem[]) => {
    setPackageFiles(prev => marketplaceApplyMcpItemsToPackageFiles(prev, items));
  }, []);
  const handleMarkdownItemsChange = React.useCallback((tab: MarketplaceMarkdownEditorTab, items: MarketplaceEditorResourceItem[]) => {
    setPackageFiles(prev => marketplaceApplyResourceItemsToPackageFiles(prev, items, marketplaceMarkdownManagedPrefixes[tab]));
  }, []);
  const handlePackageFilesChange = React.useCallback((files: MarketplacePackageFile[], managedPrefixes: string[]) => {
    setPackageFiles(prev => marketplaceApplyPackageFiles(prev, files, managedPrefixes));
  }, []);
  const handleRootTextFileChange = React.useCallback((path: string, content: string) => {
    handlePackageFilesChange([marketplaceTextPackageFile(path, content)], [path]);
  }, [handlePackageFilesChange]);
  const handleSkillsPackageFilesChange = React.useCallback((files: MarketplacePackageFile[]) => {
    handlePackageFilesChange(files, ['skills/']);
  }, [handlePackageFilesChange]);
  const handleHooksItemsChange = React.useCallback((items: MarketplaceEditorResourceItem[]) => {
    handlePackageFilesChange(items.map(marketplacePackageFileFromResourceItem), ['hooks/']);
  }, [handlePackageFilesChange]);
  const savePackage = async (): Promise<boolean> => {
    if (!provider) {
      setSaveStatus('error');
      return false;
    }
    if (!packageId.trim()) {
      setSaveStatus('error');
      return false;
    }
    if (requiredDraft?.listingJsonError || requiredDraft?.manifestJsonError) {
      setSaveStatus('error');
      return false;
    }
    try {
      if (mode === 'create') {
        const created = await createPackage({
          provider,
          packageId: packageId.trim(),
          displayName: displayName.trim() || packageId.trim(),
          description: description.trim(),
        });
        setRevision(created.revision);
      } else {
        const listing = provider === 'gemini' ? undefined : parseMarketplaceJsonObject(requiredDraft?.listingJson ?? '');
        const manifest = parseMarketplaceJsonObject(requiredDraft?.manifestJson ?? '');
        const result = await saveMarketplacePackage({
          provider,
          packageId: packageId.trim(),
          revision,
          ...(listing ? { listing } : {}),
          ...(manifest ? { manifest } : {}),
          packageFiles,
        });
        setLoadedDetail(result.package);
        setPackageFiles(result.package.packageFiles);
        setRevision(result.revision);
        setDisplayName(result.package.displayName);
        setDescription(result.package.description ?? '');
      }
      setResourceCommitVersion(version => version + 1);
      setIsDirty(false);
      setSaveStatus('success');
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setSaveStatus(message.includes('revision_conflict') ? 'conflict' : 'error');
      return false;
    }
  };
  const discardPackageDrafts = () => {
    setResourceDiscardVersion(version => version + 1);
    setIsDirty(false);
    setSaveStatus('idle');
  };
  const navigateBack = () => {
    if (isDirty) {
      setShowLeaveDialog(true);
      return;
    }
    navigate('/marketplace/packages');
  };

  React.useEffect(() => {
    if (!provider) return;
    if (!providerEditorTabs[provider].includes(activeTab)) {
      setActiveTab('basic');
    }
  }, [activeTab, provider]);

  React.useEffect(() => {
    if (mode !== 'edit' || !provider || !params.packageId) return;
    let isActive = true;
    void getPackage(provider, params.packageId)
      .then(detail => {
        if (!isActive) return;
        setLoadedDetail(detail);
        setPackageId(detail.packageId);
        setDisplayName(detail.displayName);
        setDescription(detail.description ?? '');
        setRevision(detail.revision);
        setPackageFiles(detail.packageFiles);
      })
      .catch(() => {
        if (isActive) setSaveStatus('error');
      });
    return () => { isActive = false; };
  }, [mode, params.packageId, provider]);

  React.useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!isDirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  if (mode === 'create' && !provider) {
    return (
      <MarketplaceProviderSelectionStep
        onBack={() => navigate('/marketplace/packages')}
        onSelect={(nextProvider) => {
          setProvider(nextProvider);
          setActiveTab('basic');
        }}
      />
    );
  }

  if (!provider || !featureItems) {
    return null;
  }

  return (
    <div className="flex h-full flex-col">
      <MarketplacePackageHeader
        mode={mode}
        isDirty={isDirty}
        saveStatus={saveStatus}
        onDiscard={discardPackageDrafts}
        onSave={savePackage}
        onBack={navigateBack}
      />

      <div className="h-[calc(100%-3rem)] overflow-auto">
        <Tabs value={activeTab} onValueChange={value => setActiveTab(value as MarketplaceEditorTab)} className="flex h-full flex-col">
          <MarketplaceTopTabs
            provider={provider}
            tabs={visibleEditorTabs}
            icons={tabIcons}
            counts={Object.fromEntries(visibleEditorTabs.map(tab => [
              tab,
              tab === 'basic' || tab === 'agentsMd'
                ? 0
                : tab === 'files'
                  ? countMarketplaceFileNodes(packageFileTree)
                  : getMarketplaceFeatureCountByDirectory[tab === 'outputStyle' ? 'outputStyles' : tab](featureItems[tab]),
            ])) as Partial<Record<MarketplaceEditorTab, number>>}
            getLabelKey={getMarketplaceEditorTabLabelKey}
          />

          <TabsContent value="basic" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceEditorBasicSection
              mode={mode}
              provider={provider}
              packageId={packageId}
              displayName={displayName}
              description={description}
              detail={loadedDetail}
              onPackageIdChange={(value) => { setPackageId(value); markDirty(); }}
              onDisplayNameChange={(value) => { setDisplayName(value); markDirty(); }}
              onDescriptionChange={(value) => { setDescription(value); markDirty(); }}
              onRequiredDraftChange={setRequiredDraft}
              onReadmeChange={content => handleRootTextFileChange('README.md', content)}
              onProviderGuidanceChange={content => handleRootTextFileChange('GEMINI.md', content)}
              onDirty={markDirty}
            />
          </TabsContent>

          <TabsContent value="agentsMd" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceAgentsMdEditor
              provider={provider}
              onDirty={markDirty}
              onContentChange={(path, content) => handleRootTextFileChange(path, content)}
            />
          </TabsContent>

          <TabsContent value="skills" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceFilesSection
              key={skillsFileManagerKey}
              mode="editor-skills"
              items={featureItems.skills}
              onDirty={markDirty}
              onPackageFilesChange={handleSkillsPackageFilesChange}
            />
          </TabsContent>

          <TabsContent value="agents" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceMarkdownEditorViewer
              key={`${provider}-agents`}
              tab="agents"
              icon={Bot}
              items={featureItems.agents}
              commitVersion={resourceCommitVersion}
              discardVersion={resourceDiscardVersion}
              onDirty={markDirty}
              onItemsChange={items => handleMarkdownItemsChange('agents', items)}
            />
          </TabsContent>

          <TabsContent value="commands" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceMarkdownEditorViewer
              key={`${provider}-commands`}
              tab="commands"
              icon={Command}
              items={featureItems.commands}
              format={provider === 'gemini' ? 'toml' : 'markdown'}
              commitVersion={resourceCommitVersion}
              discardVersion={resourceDiscardVersion}
              onDirty={markDirty}
              onItemsChange={items => handleMarkdownItemsChange('commands', items)}
            />
          </TabsContent>

          <TabsContent value="mcp" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceEditorMcpSection
              key={`${provider}-mcp`}
              icon={Network}
              items={featureItems.mcp}
              onDirty={markDirty}
              onItemsChange={handleMcpItemsChange}
            />
          </TabsContent>

          <TabsContent value="hooks" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceEditorHookSection
              key={`${provider}-hooks`}
              provider={provider}
              icon={Zap}
              items={featureItems.hooks}
              onDirty={markDirty}
              onItemsChange={handleHooksItemsChange}
            />
          </TabsContent>

          <TabsContent value="outputStyle" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceMarkdownEditorViewer
              key={`${provider}-output-style`}
              tab="outputStyle"
              icon={Wand2}
              items={featureItems.outputStyle}
              commitVersion={resourceCommitVersion}
              discardVersion={resourceDiscardVersion}
              onDirty={markDirty}
              onItemsChange={items => handleMarkdownItemsChange('outputStyle', items)}
            />
          </TabsContent>

          <TabsContent value="policies" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceMarkdownEditorViewer
              key={`${provider}-policies`}
              tab="policies"
              icon={Workflow}
              items={featureItems.policies}
              format="toml"
              commitVersion={resourceCommitVersion}
              discardVersion={resourceDiscardVersion}
              onDirty={markDirty}
              onItemsChange={items => handleMarkdownItemsChange('policies', items)}
            />
          </TabsContent>

          <TabsContent value="files" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceFilesSection
              key={packageRoot}
              mode="editor-package"
              provider={provider}
              packageId={packageId}
              packageRoot={packageRoot}
              displayName={resolvedDisplayName}
              packageFiles={packageFiles}
              initialNodes={packageFileTree}
              onDirty={markDirty}
              onPackageFilesChange={setPackageFiles}
            />
          </TabsContent>
        </Tabs>
      </div>
      <MarketplaceEditorLeaveDialog
        open={showLeaveDialog}
        onOpenChange={setShowLeaveDialog}
        onSave={() => {
          void savePackage().then(saved => {
            if (saved) navigate('/marketplace/packages');
          });
        }}
        onDiscard={() => navigate('/marketplace/packages')}
      />
    </div>
  );
};

interface MarketplaceProviderSelectionStepProps {
  onBack: () => void;
  onSelect: (provider: MarketplaceProvider) => void;
}

const marketplaceProviderOptions: Array<{
  provider: MarketplaceProvider;
  iconSrc: string;
}> = [
  {
    provider: 'claude-code',
    iconSrc: '/marketplace/providers/claude-code.png',
  },
  {
    provider: 'codex',
    iconSrc: '/marketplace/providers/codex.png',
  },
  {
    provider: 'gemini',
    iconSrc: '/marketplace/providers/gemini.svg',
  },
];

const MarketplaceProviderSelectionStep: React.FC<MarketplaceProviderSelectionStepProps> = ({
  onBack,
  onSelect,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('marketplace.editor.providerStep.title')}
        icon={FolderPlus}
        info={(
          <span className="text-xs text-muted-foreground">
            {t('marketplace.editor.providerStep.description')}
          </span>
        )}
        actions={(
          <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onBack}>
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.common.actions.back')}
          </Button>
        )}
      />

      <div className="h-[calc(100%-3rem)] overflow-auto p-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-foreground">
              {t('marketplace.editor.providerStep.heading')}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t('marketplace.editor.providerStep.help')}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {marketplaceProviderOptions.map(({ provider: optionProvider, iconSrc }) => {
              const editorTabs = providerEditorTabs[optionProvider].filter(tab => tab !== 'basic' && tab !== 'files');

              return (
              <button
                key={optionProvider}
                type="button"
                className="group flex h-full flex-col rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary/60 hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => onSelect(optionProvider)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-md border border-border bg-background">
                      <img src={iconSrc} alt="" className="h-7 w-7 object-contain" />
                    </span>
                    <div>
                      <div className="text-sm font-semibold text-foreground">
                        {t(`marketplace.providers.${optionProvider}`)}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {t(`marketplace.editor.providerStep.options.${optionProvider}.description`)}
                      </div>
                    </div>
                  </div>
                  <ChevronRight className="mt-1 h-4 w-4 text-muted-foreground group-hover:text-primary" />
                </div>

                <div className="mt-4 space-y-2">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t('marketplace.editor.providerStep.sectionsLabel')}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {editorTabs.map(tab => (
                      <Badge key={tab} variant="secondary" className="rounded-md px-2 py-0.5 text-[11px]">
                        {t(getMarketplaceEditorTabLabelKey(optionProvider, tab))}
                      </Badge>
                    ))}
                  </div>
                </div>
              </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};




export default MarketplaceEditorView;
