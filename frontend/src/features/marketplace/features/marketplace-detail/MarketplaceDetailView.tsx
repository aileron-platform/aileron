import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Command,
  Copy,
  Database,
  Download,
  Eye,
  EyeOff,
  FileArchive,
  FileText,
  Info,
  MoreHorizontal,
  Network,
  PenSquare,
  Play,
  RefreshCw,
  Server,
  Sparkles,
  Terminal,
  Trash2,
  Wand2,
  Zap,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Separator } from '@/shared/components/ui/separator';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { ApiError } from '@/shared/api/apiClient';
import { fetchWorkspaceList } from '@/features/workspace/services/workspaceRuntimeApi';
import type { MarketplaceCliPreflight, MarketplaceFeatureContentItem, MarketplaceInstallResult, MarketplacePackageDetail, MarketplacePackageFile, MarketplaceProvider } from '@/shared/types/marketplace';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  FileTreePanel,
  isMarkdownFile,
  sortTreeNodes,
  useFileTreeState,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { cn } from '@/shared/utils/cn';
import {
  SettingsWorkflowActionButton,
  SettingsWorkflowCountBadge,
  SettingsWorkflowShell,
} from '@/shared/components/settings-workflow';
import { CodeTextEditor } from '@/shared/components/file-workbench/viewer-entry';
import { resolveMarketplacePermissions } from '../../permissions';
import { deletePackage, exportPackage, getInstallPreflight, getPackage, installPackage } from '../../api/marketplaceApi';
import { FALLBACK_WORKSPACE_ID, MARKETPLACE_STORAGE_USER_SCOPE } from '../../constants';
import { MarketplaceInstallOutput } from '../../components/MarketplaceInstallOutput';
import { MarketplaceSectionSidebarShell } from '../../components/MarketplaceSectionSidebarShell';
import { downloadBlob } from '../../utils/downloadBlob';
import { getMarketplaceFeatureLabelKey } from '../../utils/featureLabels';
import {
  resolveMarketplaceInstallWorkspaceId,
  saveMarketplaceInstallWorkspaceId,
  type MarketplaceWorkspaceOption,
} from '../../utils/marketplaceLocalStorage';

type MarketplaceDetailTab =
  | 'basic-info'
  | 'agents-md'
  | 'hooks'
  | 'mcp'
  | 'agent'
  | 'commands'
  | 'output-style'
  | 'skills'
  | 'files';

const LEFT_WIDTH = 280;

const isProvider = (value: string | undefined): value is MarketplaceProvider =>
  value === 'claude-code' || value === 'codex' || value === 'gemini';

const getMarketplaceInstallCommandName = (
  provider: MarketplaceProvider,
  t: (key: string) => string,
) => t(`marketplace.install.commandNames.${provider}`);

const toFileName = (item: MarketplaceFeatureContentItem, extension = 'md') =>
  item.path?.split('/').pop() ?? `${item.id}.${extension}`;

const toMarkdownContent = (item: MarketplaceFeatureContentItem) =>
  item.content ?? `# ${item.name}\n\n${item.description ?? ''}`;

const toFeatureData = <T extends Record<string, unknown>>(item: MarketplaceFeatureContentItem): T =>
  (item.data ?? {}) as T;

const resolveI18nText = (t: (key: string, params?: Record<string, unknown>) => string, key: string, fallbackKey: string) => {
  const value = t(key);
  return value === key ? t(fallbackKey) : value;
};

const getMarketplaceErrorCode = (err: unknown, fallback: string) => (
  err instanceof ApiError
    ? (err.errorCode ?? err.message ?? fallback)
    : err instanceof Error
      ? err.message
      : typeof err === 'string'
        ? err
        : fallback
);

type MarketplaceDetailFeatureTab = Exclude<MarketplaceDetailTab, 'basic-info'>;

interface MarketplaceDetailFeatureItem {
  id: MarketplaceDetailFeatureTab;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  count: number;
}

const getMarketplaceDetailFeatureItems = (
  detail: MarketplacePackageDetail,
  t: (key: string, params?: Record<string, unknown>) => string,
): MarketplaceDetailFeatureItem[] => {
  const items: MarketplaceDetailFeatureItem[] = [
    { id: 'agents-md', name: t(getMarketplaceFeatureLabelKey(detail.provider, 'agentsMd')), icon: FileText, count: detail.featureContent.agentsMd ? 1 : 0 },
    { id: 'hooks', name: t('marketplace.features.hooks'), icon: Zap, count: detail.featureContent.hooks.length },
    { id: 'mcp', name: t('marketplace.features.mcp'), icon: Network, count: detail.featureContent.mcpServers.length },
    { id: 'agent', name: t('marketplace.features.subagents'), icon: Bot, count: detail.featureContent.agents.length },
    { id: 'commands', name: t('marketplace.features.slashCommands'), icon: Command, count: detail.featureContent.commands.length },
    { id: 'output-style', name: t('marketplace.features.outputStyle'), icon: Wand2, count: detail.featureContent.outputStyles.length },
    { id: 'skills', name: t('marketplace.features.skills'), icon: Sparkles, count: detail.featureContent.skills.length },
    { id: 'files', name: t('marketplace.detail.tabs.files'), icon: FileArchive, count: detail.packageFiles.length },
  ];

  return items.filter(item => {
    if (item.id === 'mcp') return detail.provider !== 'gemini' || item.count > 0;
    if (item.id === 'output-style') return detail.provider === 'claude-code' || item.count > 0;
    return true;
  });
};

export const MarketplaceDetailView: React.FC = () => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { provider, packageId } = useParams();
  const [activeTab, setActiveTab] = React.useState<MarketplaceDetailTab>('basic-info');
  const [detail, setDetail] = React.useState<MarketplacePackageDetail | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [activeAction, setActiveAction] = React.useState<'install' | 'export' | 'delete' | null>(null);
  const permissions = React.useMemo(() => resolveMarketplacePermissions(), []);

  React.useEffect(() => {
    let isActive = true;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      if (!isProvider(provider) || !packageId) {
        setError('marketplace.errors.packageNotFound');
        setIsLoading(false);
        return;
      }
      try {
        const data = await getPackage(provider, packageId);
        if (isActive) setDetail(data);
      } catch (err) {
        if (isActive) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (isActive) setIsLoading(false);
      }
    };
    void load();
    return () => { isActive = false; };
  }, [packageId, provider]);

  const tabs = React.useMemo(
    () => detail ? [
      { id: 'basic-info' as const, name: t('marketplace.detail.tabs.basicInfo'), icon: Info, count: 0 },
      ...getMarketplaceDetailFeatureItems(detail, t),
    ] : [{ id: 'basic-info' as const, name: t('marketplace.detail.tabs.basicInfo'), icon: Info, count: 0 }],
    [
      detail?.featureContent.agents.length,
      detail?.featureContent.agentsMd,
      detail?.featureContent.commands.length,
      detail?.featureContent.hooks.length,
      detail?.featureContent.mcpServers.length,
      detail?.featureContent.outputStyles.length,
      detail?.featureContent.skills.length,
      detail?.packageFiles.length,
      detail?.provider,
      t,
    ],
  );

  if (isLoading) {
    return (
      <LoadingSpinner text={t('marketplace.common.loading')} className="h-full" />
    );
  }

  if (error || !detail) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 text-sm text-muted-foreground">
        <p>{t('marketplace.errors.packageNotFound')}</p>
        <Button onClick={() => navigate(ROUTES.MARKETPLACE_PACKAGES)}>
          {t('marketplace.detail.actions.backToCenter')}
        </Button>
      </div>
    );
  }

  const renderContent = () => {
    switch (activeTab) {
      case 'basic-info':
        return (
          <MarketplaceBasicInfoPanel
            detail={detail}
            onOpenVariant={(variantProvider, variantPackageId) => {
              navigate(ROUTES.MARKETPLACE_PACKAGE_DETAIL(variantProvider, variantPackageId));
            }}
          />
        );
      case 'agents-md':
        return (
          <MarketplaceAgentsMdPanel title={t(getMarketplaceFeatureLabelKey(detail.provider, 'agentsMd'))} content={detail.featureContent.agentsMd ?? ''} />
        );
      case 'hooks':
        return <MarketplaceHooksWorkflow provider={detail.provider} hooks={detail.featureContent.hooks} />;
      case 'mcp':
        return <MarketplaceMcpWorkflow servers={detail.featureContent.mcpServers} />;
      case 'agent':
        return <MarketplaceFeatureViewer title={t('marketplace.features.subagents')} items={detail.featureContent.agents} icon={Bot} />;
      case 'commands':
        return <MarketplaceFeatureViewer title={t('marketplace.features.slashCommands')} items={detail.featureContent.commands} icon={Command} />;
      case 'output-style':
        return <MarketplaceFeatureViewer title={t('marketplace.features.outputStyle')} items={detail.featureContent.outputStyles} icon={Wand2} />;
      case 'skills':
        return <MarketplaceSkillsFileViewer items={detail.featureContent.skills} />;
      case 'files':
        return <MarketplacePackageFilesViewer detail={detail} />;
      default:
        return null;
    }
  };

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={detail.displayName}
        icon={FileText}
        info={(
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{t('marketplace.detail.header.version', { version: detail.version ?? t('marketplace.common.noVersion') })}</span>
            <span>{t('marketplace.detail.header.provider', { provider: t(`marketplace.providers.${detail.provider}`) })}</span>
            <span>{t('marketplace.detail.header.category', { category: detail.category || t('marketplace.common.uncategorized') })}</span>
          </div>
        )}
        actions={(
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => navigate(ROUTES.MARKETPLACE_PACKAGES)}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.back')}
            </Button>
            {permissions.canEdit ? (
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => navigate(ROUTES.MARKETPLACE_PACKAGE_EDIT(detail.provider, detail.packageId))}
              >
                <PenSquare className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.edit')}
              </Button>
            ) : null}
            {permissions.canExport ? (
              <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => setActiveAction('export')}>
                <Download className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.export')}
              </Button>
            ) : null}
            {permissions.canInstall ? (
              <Button size="sm" className="h-7 px-2 text-xs" onClick={() => setActiveAction('install')}>
                <Play className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.install')}
              </Button>
            ) : null}
            {permissions.canDelete ? (
              <Button variant="destructive" size="sm" className="h-7 px-2 text-xs" onClick={() => setActiveAction('delete')}>
                <Trash2 className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.delete')}
              </Button>
            ) : null}
          </div>
        )}
      />

      <div className="flex-1 overflow-hidden">
        <div className="flex h-full">
          <div className="h-full border-r border-border bg-background" style={{ width: LEFT_WIDTH }}>
            <div className="flex h-full flex-col">
              <div className="flex-1 overflow-y-auto p-4">
                <div className="space-y-4">
                  <section>
                    <h3 className="mb-3 font-semibold text-foreground">{t('marketplace.detail.sidebar.info.title')}</h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between gap-3">
                        <span className="text-muted-foreground">{t('marketplace.detail.sidebar.info.categoryLabel')}</span>
                        <Badge variant="secondary">{detail.category || t('marketplace.common.uncategorized')}</Badge>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="text-muted-foreground">{t('marketplace.detail.sidebar.info.versionLabel')}</span>
                        <span className="font-medium">{detail.version ?? t('marketplace.common.noVersion')}</span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="text-muted-foreground">{t('marketplace.detail.sidebar.info.providerLabel')}</span>
                        <span className="font-medium">{t(`marketplace.providers.${detail.provider}`)}</span>
                      </div>
                    </div>
                  </section>

                  <section>
                    <h4 className="mb-3 font-medium text-foreground">{t('marketplace.detail.sidebar.features.title')}</h4>
                    <div className="space-y-1">
                      {tabs.map(tab => {
                        const Icon = tab.icon;
                        const isActive = activeTab === tab.id;
                        return (
                          <Button
                            key={tab.id}
                            variant={isActive ? 'default' : 'ghost'}
                            className="h-8 w-full justify-start px-2 text-xs"
                            onClick={() => setActiveTab(tab.id)}
                          >
                            <Icon className="mr-2 h-4 w-4" />
                            <span className="flex-1 text-left">{tab.name}</span>
                            {tab.count > 0 && (
                              <Badge
                                variant="outline"
                                className={`ml-auto text-xs ${isActive ? 'bg-background text-foreground border-transparent' : ''}`}
                              >
                                {tab.count}
                              </Badge>
                            )}
                          </Button>
                        );
                      })}
                    </div>
                  </section>

                </div>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-hidden bg-background">
            {renderContent()}
          </div>
        </div>
      </div>
      <MarketplaceInstallDialog
        open={activeAction === 'install'}
        detail={detail}
        onOpenChange={open => setActiveAction(open ? 'install' : null)}
      />
      <MarketplaceExportDialog
        open={activeAction === 'export'}
        detail={detail}
        onOpenChange={open => setActiveAction(open ? 'export' : null)}
      />
      <MarketplaceDeleteDialog
        open={activeAction === 'delete'}
        detail={detail}
        onOpenChange={open => setActiveAction(open ? 'delete' : null)}
        onDeleted={() => navigate(ROUTES.MARKETPLACE_PACKAGES)}
      />
    </div>
  );
};

interface MarketplaceBasicInfoPanelProps {
  detail: MarketplacePackageDetail;
  onOpenVariant: (provider: MarketplaceProvider, packageId: string) => void;
}

const MarketplaceBasicInfoPanel: React.FC<MarketplaceBasicInfoPanelProps> = ({ detail, onOpenVariant }) => {
  const { t } = useI18n();

  const featureCounts = getMarketplaceDetailFeatureItems(detail, t);
  const siblingVariants = detail.variants.filter(variant => (
    variant.provider !== detail.provider || variant.packageId !== detail.packageId
  ));

  return (
    <div className="h-full overflow-y-auto">
      <div className="space-y-6 p-6">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Info className="h-5 w-5 text-primary" />
            <h2 className="text-2xl font-bold text-foreground">{t('marketplace.detail.basicInfo.title')}</h2>
          </div>
          <p className="text-sm text-muted-foreground">{detail.description}</p>
        </div>

        <Separator />

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {t('marketplace.detail.basicInfo.sections.general.title')}
            </CardTitle>
            <CardDescription>{t('marketplace.detail.basicInfo.sections.general.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <InfoGridRow label={t('marketplace.detail.basicInfo.packageId')} value={detail.packageId} monospace />
            <InfoGridRow label={t('marketplace.detail.basicInfo.registryPath')} value={detail.registryPath} monospace />
            <InfoGridRow label={t('marketplace.detail.basicInfo.provider')} value={<Badge variant="outline">{t(`marketplace.providers.${detail.provider}`)}</Badge>} />
            <InfoGridRow label={t('marketplace.detail.basicInfo.version')} value={<Badge variant="secondary">{detail.version ?? t('marketplace.common.noVersion')}</Badge>} />
            {detail.familyDisplayName || detail.sourceIdentity ? (
              <InfoGridRow
                label={t('marketplace.detail.basicInfo.family')}
                value={(
                  <div className="space-y-1">
                    {detail.familyDisplayName ? <div>{detail.familyDisplayName}</div> : null}
                    {detail.sourceIdentity ? <div className="font-mono text-xs text-muted-foreground">{detail.sourceIdentity}</div> : null}
                  </div>
                )}
              />
            ) : null}
            {siblingVariants.length > 0 ? (
              <InfoGridRow
                label={t('marketplace.detail.basicInfo.variants')}
                value={(
                  <div className="flex flex-wrap gap-2">
                    {detail.variants.map(variant => {
                      const isCurrent = variant.provider === detail.provider && variant.packageId === detail.packageId;
                      return (
                        <Button
                          key={`${variant.provider}:${variant.packageId}`}
                          type="button"
                          variant={isCurrent ? 'secondary' : 'outline'}
                          size="sm"
                          className="h-7 px-2 text-xs"
                          disabled={isCurrent}
                          onClick={() => onOpenVariant(variant.provider, variant.packageId)}
                        >
                          {t(`marketplace.providers.${variant.provider}`)}
                        </Button>
                      );
                    })}
                  </div>
                )}
              />
            ) : null}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-sm font-medium text-muted-foreground">
                {t('marketplace.detail.basicInfo.sections.features.title')}
              </div>
              <div className="col-span-2 flex flex-wrap gap-2">
                {featureCounts.map(item => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={item.id}
                      className="inline-flex h-7 items-center gap-1.5 rounded-md border border-border bg-muted/20 px-2 text-xs"
                    >
                      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-muted-foreground">{item.name}</span>
                      <span className="rounded bg-primary/10 px-1.5 py-0.5 font-medium text-primary">{item.count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {t('marketplace.detail.readme.title')}
            </CardTitle>
            <CardDescription>{t('marketplace.detail.readme.description')}</CardDescription>
          </CardHeader>
          <CardContent>
            {detail.readmeMarkdown ? (
              <MarkdownContent content={detail.readmeMarkdown} variant="detailed" />
            ) : (
              <p className="text-sm text-muted-foreground">{t('marketplace.detail.readme.empty')}</p>
            )}
          </CardContent>
        </Card>

        {detail.validationResults.length > 0 || detail.metadataConflict ? (
          <Card>
            <CardHeader>
              <CardTitle>{t('marketplace.detail.validation.title')}</CardTitle>
              <CardDescription>{t('marketplace.detail.validation.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {detail.metadataConflict ? (
                <ValidationResultRow
                  severity="warning"
                  severityLabel={t('marketplace.validation.severity.warning')}
                  message={t('marketplace.detail.validation.metadataConflict')}
                  code="marketplace.metadata.conflict"
                  filePath="marketplace.json"
                />
              ) : null}
              {detail.validationResults.map(result => (
                <ValidationResultRow
                  key={`${result.code}:${result.filePath ?? ''}`}
                  severity={result.severity}
                  severityLabel={t(`marketplace.validation.severity.${result.severity}`)}
                  message={t(result.messageKey)}
                  code={result.code}
                  filePath={result.filePath}
                />
              ))}
            </CardContent>
          </Card>
        ) : null}

      </div>
    </div>
  );
};

interface InfoGridRowProps {
  label: string;
  value: React.ReactNode;
  monospace?: boolean;
}

const InfoGridRow: React.FC<InfoGridRowProps> = ({ label, value, monospace = false }) => (
  <div className="grid grid-cols-3 gap-4">
    <div className="text-sm font-medium text-muted-foreground">{label}</div>
    <div className={`col-span-2 break-words text-sm text-foreground ${monospace ? 'font-mono' : ''}`}>{value}</div>
  </div>
);

interface ValidationResultRowProps {
  severity: 'error' | 'warning' | 'info';
  severityLabel: string;
  message: string;
  code: string;
  filePath?: string;
}

const ValidationResultRow: React.FC<ValidationResultRowProps> = ({ severity, severityLabel, message, code, filePath }) => (
  <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={severity === 'error' ? 'destructive' : severity === 'warning' ? 'secondary' : 'outline'}>
          {severityLabel}
        </Badge>
        <span className="text-foreground">{message}</span>
      </div>
      {filePath ? <div className="mt-1 font-mono text-xs text-muted-foreground">{filePath}</div> : null}
    </div>
    <code className="rounded bg-muted px-2 py-1 text-xs text-muted-foreground">{code}</code>
  </div>
);

interface MarketplacePackageActionDialogProps {
  open: boolean;
  detail: MarketplacePackageDetail;
  onOpenChange: (open: boolean) => void;
}

const MarketplaceInstallDialog: React.FC<MarketplacePackageActionDialogProps> = ({ open, detail, onOpenChange }) => {
  const { t } = useI18n();
  const [workspaceId, setWorkspaceId] = React.useState(FALLBACK_WORKSPACE_ID);
  const [workspaceOptions, setWorkspaceOptions] = React.useState<MarketplaceWorkspaceOption[]>([]);
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = React.useState(false);
  const [status, setStatus] = React.useState<'idle' | 'running' | MarketplaceInstallResult['status']>('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);
  const [installResult, setInstallResult] = React.useState<MarketplaceInstallResult | null>(null);
  const [preflight, setPreflight] = React.useState<MarketplaceCliPreflight | null>(null);
  const [isLoadingPreflight, setIsLoadingPreflight] = React.useState(false);
  const commandName = getMarketplaceInstallCommandName(detail.provider, t);

  React.useEffect(() => {
    if (open) {
      setStatus('idle');
      setErrorCode(null);
      setInstallResult(null);
      setPreflight(null);
    }
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    let isActive = true;
    setIsLoadingWorkspaces(true);
    void fetchWorkspaceList()
      .then(result => {
        if (!isActive) return;
        const options = result.items.map(workspace => ({
          id: workspace.id,
          label: workspace.name || workspace.id,
        }));
        setWorkspaceOptions(options);
        setWorkspaceId(resolveMarketplaceInstallWorkspaceId(
          options,
          FALLBACK_WORKSPACE_ID,
          MARKETPLACE_STORAGE_USER_SCOPE,
        ));
      })
      .catch(() => {
        if (!isActive) return;
        setWorkspaceOptions([]);
        setWorkspaceId(resolveMarketplaceInstallWorkspaceId(
          [],
          FALLBACK_WORKSPACE_ID,
          MARKETPLACE_STORAGE_USER_SCOPE,
        ));
      })
      .finally(() => {
        if (isActive) setIsLoadingWorkspaces(false);
      });
    return () => { isActive = false; };
  }, [open]);

  React.useEffect(() => {
    if (!open || !workspaceId) return;
    let isActive = true;
    setIsLoadingPreflight(true);
    void getInstallPreflight(detail.provider, workspaceId)
      .then(result => {
        if (isActive) setPreflight(result);
      })
      .catch(err => {
        if (!isActive) return;
        setPreflight({
          provider: detail.provider,
          available: false,
          capabilities: {
            supportsUserScope: false,
            supportsMarketplaceAdd: false,
            supportsExtensionInstall: false,
          },
          errorCode: err instanceof Error ? err.message : 'marketplace.install.preflight.failed',
        });
      })
      .finally(() => {
        if (isActive) setIsLoadingPreflight(false);
      });
    return () => { isActive = false; };
  }, [detail.provider, open, workspaceId]);

  const runInstall = async () => {
    setStatus('running');
    saveMarketplaceInstallWorkspaceId(MARKETPLACE_STORAGE_USER_SCOPE, workspaceId);
    const result = await installPackage({
      provider: detail.provider,
      packageId: detail.packageId,
      revision: detail.revision,
      workspaceId,
    });
    setStatus(result.status);
    setErrorCode(result.errorCode ?? null);
    setInstallResult(result);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('marketplace.install.title')}</DialogTitle>
          <DialogDescription>{t('marketplace.install.description', { commandName })}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <InfoGridRow label={t('marketplace.install.fields.provider')} value={t(`marketplace.providers.${detail.provider}`)} />
            <InfoGridRow label={t('marketplace.install.fields.package')} value={detail.packageId} monospace />
          </div>
          <div className="space-y-2">
            <Label htmlFor="marketplace-install-workspace">{t('marketplace.install.fields.workspace')}</Label>
            <Select
              value={workspaceId}
              onValueChange={(value) => {
                setWorkspaceId(value);
                saveMarketplaceInstallWorkspaceId(MARKETPLACE_STORAGE_USER_SCOPE, value);
              }}
              disabled={isLoadingWorkspaces}
            >
              <SelectTrigger id="marketplace-install-workspace">
                <SelectValue placeholder={t('marketplace.install.workspaceSelect.placeholder')} />
              </SelectTrigger>
              <SelectContent>
                {workspaceOptions.length > 0 ? (
                  workspaceOptions.map(workspace => (
                    <SelectItem key={workspace.id} value={workspace.id}>
                      {workspace.label}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value={FALLBACK_WORKSPACE_ID}>
                    {isLoadingWorkspaces
                      ? t('marketplace.install.workspaceSelect.loading')
                      : t('marketplace.install.workspaceSelect.currentWorkspace')}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
          <Alert variant={preflight && !preflight.available ? 'destructive' : 'default'}>
            <Terminal className="h-4 w-4" />
            <AlertDescription>
              {isLoadingPreflight
                ? t('marketplace.install.preflight.loading', { commandName })
                : preflight?.available
                  ? t('marketplace.install.preflight.ready', { commandName, version: preflight.version ?? t('marketplace.install.preflight.unknownVersion') })
                  : t('marketplace.install.preflight.unavailable', { commandName, code: preflight?.errorCode ?? 'unknown' })}
            </AlertDescription>
          </Alert>
          <div className="rounded-md border border-border bg-muted/30 p-3">
            <div className="text-xs font-medium text-muted-foreground">{t('marketplace.install.commandPreview')}</div>
            <code className="mt-2 block break-all text-xs">
              {detail.provider === 'gemini'
                ? `gemini extensions install ${detail.registryPath}`
                : `${detail.provider === 'claude-code' ? 'claude' : 'codex'} plugin install ${detail.packageId} --scope user`}
            </code>
          </div>
          {installResult && status !== 'success' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>{t(`marketplace.install.result.${installResult.status}`, { commandName, code: errorCode ?? 'unknown' })}</AlertDescription>
            </Alert>
          ) : null}
          {status === 'success' ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{t('marketplace.install.result.success')}</AlertDescription>
            </Alert>
          ) : null}
          {installResult?.stdout || installResult?.stderr ? (
            <MarketplaceInstallOutput result={installResult} />
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</Button>
          <Button onClick={runInstall} disabled={status === 'running'}>
            {status === 'running' ? <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" /> : <Play className="mr-1.5 h-4 w-4" />}
            {t('marketplace.install.actions.install')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const MarketplaceExportDialog: React.FC<MarketplacePackageActionDialogProps> = ({ open, detail, onOpenChange }) => {
  const { t } = useI18n();
  const [status, setStatus] = React.useState<'idle' | 'running' | 'success' | 'failed'>('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setStatus('idle');
      setErrorCode(null);
    }
  }, [open]);

  const runExport = async () => {
    setStatus('running');
    setErrorCode(null);
    try {
      const archive = await exportPackage({ provider: detail.provider, packageId: detail.packageId, revision: detail.revision });
      downloadBlob(archive, `${detail.provider}-${detail.packageId}.zip`);
      setStatus('success');
    } catch (err) {
      setErrorCode(getMarketplaceErrorCode(err, 'marketplace.export.result.failed'));
      setStatus('failed');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('marketplace.export.title')}</DialogTitle>
          <DialogDescription>{t('marketplace.export.description')}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <InfoGridRow label={t('marketplace.export.fields.archive')} value={`${detail.packageId}.zip`} monospace />
          <InfoGridRow label={t('marketplace.export.fields.root')} value={detail.registryPath} monospace />
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>{t('marketplace.export.compatibilityNotice')}</AlertDescription>
          </Alert>
          {status === 'success' ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{t('marketplace.export.result.ready')}</AlertDescription>
            </Alert>
          ) : null}
          {status === 'failed' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>{t('marketplace.export.result.failed', { code: errorCode ?? 'unknown' })}</AlertDescription>
            </Alert>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</Button>
          <Button onClick={runExport} disabled={status === 'running'}>
            {status === 'running' ? <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" /> : <Download className="mr-1.5 h-4 w-4" />}
            {t('marketplace.export.actions.export')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

interface MarketplaceDeleteDialogProps extends MarketplacePackageActionDialogProps {
  onDeleted: () => void;
}

const MarketplaceDeleteDialog: React.FC<MarketplaceDeleteDialogProps> = ({ open, detail, onOpenChange, onDeleted }) => {
  const { t } = useI18n();
  const [confirmText, setConfirmText] = React.useState('');
  const [status, setStatus] = React.useState<'idle' | 'running' | 'failed'>('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setConfirmText('');
      setStatus('idle');
      setErrorCode(null);
    }
  }, [open]);

  const runDelete = async () => {
    setStatus('running');
    const result = await deletePackage({
      provider: detail.provider,
      packageId: detail.packageId,
      revision: detail.revision,
    });
    if (result.deleted) {
      onOpenChange(false);
      onDeleted();
      return;
    }
    setStatus('failed');
    setErrorCode(result.errorCode ?? 'marketplace.package.delete_failed');
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>{t('marketplace.delete.title')}</AlertDialogTitle>
          <AlertDialogDescription>{t('marketplace.delete.description')}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-4">
          <Alert variant="destructive">
            <Trash2 className="h-4 w-4" />
            <AlertDescription>{t('marketplace.delete.warning')}</AlertDescription>
          </Alert>
          <InfoGridRow label={t('marketplace.delete.fields.package')} value={detail.packageId} monospace />
          <InfoGridRow label={t('marketplace.delete.fields.revision')} value={detail.revision} monospace />
          <div className="space-y-2">
            <Label htmlFor="marketplace-delete-confirm">{t('marketplace.delete.fields.confirm', { id: detail.packageId })}</Label>
            <Input id="marketplace-delete-confirm" value={confirmText} onChange={event => setConfirmText(event.target.value)} />
          </div>
          {status === 'failed' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>{t('marketplace.delete.result.failed', { code: errorCode ?? 'unknown' })}</AlertDescription>
            </Alert>
          ) : null}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={(event) => {
              event.preventDefault();
              void runDelete();
            }}
            disabled={confirmText !== detail.packageId || status === 'running'}
          >
            {status === 'running' ? <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" /> : <Trash2 className="mr-1.5 h-4 w-4" />}
            {t('marketplace.delete.actions.delete')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

interface MarketplaceAgentsMdPanelProps {
  title: string;
  content: string;
}

const MarketplaceAgentsMdPanel: React.FC<MarketplaceAgentsMdPanelProps> = ({ title, content }) => {
  const { t } = useI18n();
  const { toast } = useToast();

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      toast({ title: t('marketplace.detail.agentsMd.actions.copySuccess') });
    } catch {
      toast({ title: t('marketplace.detail.agentsMd.actions.copyFailed'), variant: 'destructive' });
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    downloadBlob(blob, t('marketplace.detail.agentsMd.downloadFileName'));
    toast({ title: t('marketplace.detail.agentsMd.actions.downloadSuccess') });
  };

  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={title}
        icon={FileText}
        actions={(
          <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleCopy}>
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.detail.agentsMd.actions.copy')}
          </Button>
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleDownload}>
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.detail.agentsMd.actions.download')}
          </Button>
          </div>
        )}
      />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl">
          {content.trim() ? (
            <MarkdownContent content={content} variant="detailed" />
          ) : (
            <p className="text-sm text-muted-foreground">{t('marketplace.detail.agentsMd.placeholder')}</p>
          )}
        </div>
      </div>
    </div>
  );
};

interface MarketplaceHookAction {
  type?: string;
  name?: string;
  description?: string;
  command?: string;
  url?: string;
  timeout?: number;
  statusMessage?: string;
  if?: string;
  shell?: string;
  async?: boolean;
  asyncRewake?: boolean;
}

interface MarketplaceHookMatcher {
  event?: string;
  matcher?: string;
  sequential?: boolean;
  hooks?: MarketplaceHookAction[];
}

interface MarketplaceHookData {
  description?: string;
  event?: string;
  matchers?: MarketplaceHookMatcher[];
  hooks?: Record<string, MarketplaceHookMatcher[]>;
}

interface MarketplaceHooksWorkflowProps {
  provider: MarketplaceProvider;
  hooks: MarketplaceFeatureContentItem[];
}

const MarketplaceHooksWorkflow: React.FC<MarketplaceHooksWorkflowProps> = ({ provider, hooks }) => {
  const { t } = useI18n();
  const { toast } = useToast();

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(hooks, null, 2)], { type: 'application/json' });
    downloadBlob(blob, t('marketplace.detail.hooks.downloadFileName'));
    toast({ title: t('marketplace.detail.hooks.toasts.downloadSuccess') });
  };

  return (
    <SettingsWorkflowShell
      title={t('marketplace.detail.hooks.header.title')}
      icon={Zap}
      headerActions={(
        <SettingsWorkflowActionButton variant="outline" onClick={handleDownload}>
          <Download className="mr-1 h-3.5 w-3.5" />
          {t('marketplace.detail.hooks.actions.download')}
        </SettingsWorkflowActionButton>
      )}
      summary={<SettingsWorkflowCountBadge label={t('marketplace.detail.hooks.badge', { count: hooks.length })} />}
      singleHeader
      hasItems={hooks.length > 0}
      emptyIcon={<Zap className="h-6 w-6 text-muted-foreground" />}
      emptyTitle={t('marketplace.detail.hooks.empty.title')}
      emptyDescription={t('marketplace.detail.hooks.empty.description')}
      contentClassName="space-y-4 p-4"
    >
      {hooks.map(hook => (
        <MarketplaceHookCard key={hook.id} provider={provider} hook={hook} />
      ))}
    </SettingsWorkflowShell>
  );
};

interface MarketplaceHookCardProps {
  provider: MarketplaceProvider;
  hook: MarketplaceFeatureContentItem;
}

const MarketplaceHookCard: React.FC<MarketplaceHookCardProps> = ({ provider, hook }) => {
  const { t } = useI18n();
  const data = toFeatureData<MarketplaceHookData>(hook);
  const matchers = data.matchers ?? Object.entries(data.hooks ?? {}).flatMap(([event, eventMatchers]) => (
    Array.isArray(eventMatchers)
      ? eventMatchers.map(matcher => ({ ...matcher, event: matcher.event ?? event }))
      : []
  ));
  const totalMatchers = matchers.length;
  const totalCommands = matchers.reduce((acc, matcher) => acc + (matcher.hooks?.length ?? 0), 0);
  const description = hook.description ?? data.description;

  return (
    <div className="relative rounded-lg border border-border bg-background p-6">
      <div className="flex items-start">
        <div className="min-w-0 flex-1">
          <div className="mb-3">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold text-foreground">{data.event ?? hook.name}</h3>
              {hook.path ? <Badge variant="outline" className="text-xs">{hook.path}</Badge> : null}
            </div>
          </div>

          {description ? (
            <p className="mb-4 text-sm text-muted-foreground">{description}</p>
          ) : null}

          <div className="mb-4">
            <div className="mb-3 flex items-center gap-2">
              <Terminal className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-muted-foreground">
                {t('marketplace.detail.hooks.card.matchersTitle')}
              </span>
            </div>
            <div className="space-y-2">
              {matchers.map((matcher, matcherIndex) => {
                const matcherHooks = matcher.hooks ?? [];
                return (
                  <div key={`${hook.id}-${matcherIndex}`} className="rounded-lg bg-muted/50 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {matcher.event ? (
                          <Badge variant="outline" className="px-1 py-0 text-xs">
                            {matcher.event}
                          </Badge>
                        ) : null}
                        <span className="text-xs text-muted-foreground">
                          {t('marketplace.detail.hooks.card.matcherLabel')}
                        </span>
                        <code className="rounded bg-muted px-1 text-xs">{matcher.matcher ?? '*'}</code>
                        {provider === 'gemini' && matcher.sequential ? (
                          <Badge variant="outline" className="px-1 py-0 text-xs">
                            {t('marketplace.detail.hooks.card.sequential')}
                          </Badge>
                        ) : null}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {t('marketplace.detail.hooks.card.actionsCount', { count: matcherHooks.length })}
                      </span>
                    </div>
                    {matcherHooks.slice(0, 2).map((action, actionIndex) => (
                      <div key={`${hook.id}-${matcherIndex}-${actionIndex}`} className="mb-1 rounded bg-muted px-2 py-1 text-xs">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <Badge variant="outline" className="px-1 py-0 text-xs">
                            {t(`marketplace.detail.hooks.card.executionTypes.${action.type ?? 'command'}`)}
                          </Badge>
                          {provider === 'gemini' && action.name ? (
                            <span className="text-muted-foreground">{action.name}</span>
                          ) : null}
                          {action.timeout ? (
                            <span className="text-muted-foreground">
                              {provider === 'gemini'
                                ? t('marketplace.detail.hooks.card.timeoutMilliseconds', { count: action.timeout })
                                : t('marketplace.detail.hooks.card.timeoutSeconds', { count: action.timeout })}
                            </span>
                          ) : null}
                          {(provider === 'codex' || provider === 'claude-code') && action.statusMessage ? (
                            <span className="text-muted-foreground">
                              {t('marketplace.detail.hooks.card.statusMessage', { value: action.statusMessage })}
                            </span>
                          ) : null}
                          {provider === 'claude-code' && action.shell ? (
                            <span className="text-muted-foreground">
                              {t('marketplace.detail.hooks.card.shell', { value: action.shell })}
                            </span>
                          ) : null}
                          {provider === 'claude-code' && action.async ? (
                            <Badge variant="outline" className="px-1 py-0 text-xs">
                              {t('marketplace.detail.hooks.card.async')}
                            </Badge>
                          ) : null}
                          {provider === 'claude-code' && action.asyncRewake ? (
                            <Badge variant="outline" className="px-1 py-0 text-xs">
                              {t('marketplace.detail.hooks.card.asyncRewake')}
                            </Badge>
                          ) : null}
                        </div>
                        <p className="truncate font-mono text-muted-foreground">
                          {action.type === 'http'
                            ? (action.url?.trim() ? action.url : t('marketplace.detail.hooks.card.emptyUrl'))
                            : (action.command?.trim() ? action.command : t('marketplace.detail.hooks.card.emptyCommand'))}
                        </p>
                        {provider === 'claude-code' && action.if ? (
                          <div className="mt-1 flex min-w-0 items-center gap-2 text-muted-foreground">
                            <span>{t('marketplace.detail.hooks.card.ifLabel')}</span>
                            <code className="truncate rounded bg-background px-1 py-0.5 font-mono">
                              {action.if}
                            </code>
                          </div>
                        ) : null}
                        {provider === 'gemini' && action.description ? (
                          <p className="mt-1 truncate text-muted-foreground">{action.description}</p>
                        ) : null}
                      </div>
                    ))}
                    {matcherHooks.length > 2 ? (
                      <div className="text-xs italic text-muted-foreground">
                        {t('marketplace.detail.hooks.card.moreActions', { count: matcherHooks.length - 2 })}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex gap-4 rounded bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <span>{t('marketplace.detail.hooks.card.summary.matchers', { count: totalMatchers })}</span>
            <span>{t('marketplace.detail.hooks.card.summary.commands', { count: totalCommands })}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

interface MarketplaceMcpData {
  transport?: string;
  type?: string;
  url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
}

interface MarketplaceMcpWorkflowProps {
  servers: MarketplaceFeatureContentItem[];
}

const MarketplaceMcpWorkflow: React.FC<MarketplaceMcpWorkflowProps> = ({ servers }) => {
  const { t } = useI18n();
  const { toast } = useToast();

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(servers, null, 2)], { type: 'application/json' });
    downloadBlob(blob, t('marketplace.detail.mcp.downloadFileName'));
    toast({ title: t('marketplace.detail.mcp.toasts.downloadSuccess') });
  };

  return (
    <SettingsWorkflowShell
      title={t('marketplace.detail.mcp.header.title')}
      icon={Server}
      headerActions={(
        <SettingsWorkflowActionButton variant="outline" onClick={handleDownload}>
          <Download className="mr-1 h-3.5 w-3.5" />
          {t('marketplace.detail.mcp.actions.download')}
        </SettingsWorkflowActionButton>
      )}
      summary={<SettingsWorkflowCountBadge label={t('marketplace.detail.mcp.badge', { count: servers.length })} />}
      singleHeader
      hasItems={servers.length > 0}
      emptyIcon={<Server className="h-6 w-6 text-muted-foreground" />}
      emptyTitle={t('marketplace.detail.mcp.empty.title')}
      emptyDescription={t('marketplace.detail.mcp.empty.description')}
      contentClassName="space-y-4 p-4"
    >
      {servers.map(server => (
        <MarketplaceMcpServerCard key={server.id} server={server} />
      ))}
    </SettingsWorkflowShell>
  );
};

interface MarketplaceMcpServerCardProps {
  server: MarketplaceFeatureContentItem;
}

const MarketplaceMcpServerCard: React.FC<MarketplaceMcpServerCardProps> = ({ server }) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [showEnvValues, setShowEnvValues] = React.useState(false);
  const data = toFeatureData<MarketplaceMcpData>(server);
  const serverType = data.type ?? data.transport ?? 'stdio';
  const envEntries = Object.entries(data.env ?? {});
  const headerEntries = Object.entries(data.headers ?? {});

  const handleCopyConfig = async () => {
    const config: Record<string, unknown> = {
      [server.name]: {
        type: serverType,
        ...(data.url ? { url: data.url } : {}),
        ...(data.command ? { command: data.command } : {}),
        ...(data.args?.length ? { args: data.args } : {}),
        ...(envEntries.length ? { env: data.env } : {}),
        ...(headerEntries.length ? { headers: data.headers } : {}),
      },
    };
    await navigator.clipboard.writeText(JSON.stringify(config, null, 2));
    toast({ title: t('marketplace.detail.mcp.toasts.copySuccess') });
  };

  const typeClassName = (() => {
    switch (serverType) {
      case 'http':
        return 'bg-primary/10 text-primary border-primary/20';
      case 'sse':
        return 'bg-orange-50 text-orange-700 border-orange-200';
      default:
        return 'bg-gray-50 text-gray-600 border-gray-200';
    }
  })();

  return (
    <div className="rounded-lg border border-border bg-background p-4 transition-shadow hover:shadow-sm">
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Database className="h-5 w-5 text-primary" />
          </div>
          <div>
            <div className="mb-1 flex items-center gap-2">
              <h3 className="font-semibold text-foreground">{server.name}</h3>
              <Badge variant="outline" className={`text-xs ${typeClassName}`}>
                {serverType.toUpperCase()}
              </Badge>
            </div>
            {server.path ? <p className="text-xs text-muted-foreground">{server.path}</p> : null}
          </div>
        </div>
        <Button variant="ghost" size="sm" type="button" onClick={handleCopyConfig} title={t('marketplace.detail.mcp.card.copyTooltip')}>
          <Copy className="h-4 w-4" />
        </Button>
      </div>

      {server.description ? (
        <p className="mb-4 text-sm text-muted-foreground">{server.description}</p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {serverType === 'http' || serverType === 'sse'
              ? t('marketplace.detail.mcp.card.sections.url')
              : t('marketplace.detail.mcp.card.sections.command')}
          </h4>
          <div className="rounded-md bg-muted/50 p-3">
            {serverType === 'http' || serverType === 'sse' ? (
              <code className="break-all font-mono text-sm text-foreground">{data.url}</code>
            ) : (
              <>
                <code className="break-all font-mono text-sm text-foreground">{data.command}</code>
                {data.args?.length ? (
                  <div className="mt-2 break-all text-xs text-muted-foreground">{data.args.join(' ')}</div>
                ) : null}
              </>
            )}
          </div>
        </div>

        {envEntries.length > 0 ? (
          <div>
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t('marketplace.detail.mcp.card.sections.env')}
              </h4>
              <Button
                variant="ghost"
                size="sm"
                type="button"
                onClick={() => setShowEnvValues(value => !value)}
                className="h-6 px-2"
                title={showEnvValues
                  ? t('marketplace.detail.mcp.card.hideEnvValues')
                  : t('marketplace.detail.mcp.card.showEnvValues')}
              >
                {showEnvValues ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
              </Button>
            </div>
            <div className="space-y-1 rounded-md bg-muted/50 p-3">
              {envEntries.map(([key, value]) => (
                <div key={key} className="rounded bg-muted/30 px-2 py-1">
                  <span className="break-all font-mono text-xs">
                    <span className="font-semibold text-primary">{key}</span>
                    <span className="mx-1 text-muted-foreground">=</span>
                    <span className="text-foreground">{showEnvValues ? value : '***'}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {headerEntries.length > 0 ? (
        <div className="mt-4">
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t('marketplace.detail.mcp.card.sections.headers')}
          </h4>
          <div className="space-y-1 rounded-md bg-muted/50 p-3">
            {headerEntries.map(([key, value]) => (
              <div key={key} className="rounded bg-muted/30 px-2 py-1">
                <span className="break-all font-mono text-xs">
                  <span className="font-semibold text-primary">{key}</span>
                  <span className="mx-1 text-muted-foreground">:</span>
                  <span className="text-foreground">{value}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
};

interface MarketplaceFeatureViewerProps {
  title: string;
  items: MarketplaceFeatureContentItem[];
  icon: React.ComponentType<{ className?: string }>;
}

const MARKETPLACE_DETAIL_SIDEBAR_DEFAULT_WIDTH = 320;
const MARKETPLACE_DETAIL_SIDEBAR_MIN_WIDTH = 240;
const MARKETPLACE_DETAIL_SIDEBAR_MAX_WIDTH = 520;
const MARKETPLACE_DETAIL_SIDEBAR_COLLAPSED_WIDTH = 44;

interface MarketplaceSkillsFileViewerProps {
  items: MarketplaceFeatureContentItem[];
}

interface MarketplacePackageFilesViewerProps {
  detail: MarketplacePackageDetail;
}

const MarketplacePackageFilesViewer: React.FC<MarketplacePackageFilesViewerProps> = ({ detail }) => {
  const packageRoot = detail.registryPath || getMarketplaceDetailPackageRoot(detail.provider, detail.packageId);
  const initialNodes = React.useMemo(
    () => marketplaceDetailPackageFilesToFileTree(
      detail.packageFiles,
      `/${packageRoot}`,
      detail.provider === 'gemini' ? 'extension' : 'plugin',
    ),
    [detail.packageFiles, detail.provider, packageRoot],
  );

  return (
    <MarketplaceReadOnlyFileTreeViewer
      titleKey="marketplace.editor.fileManager.packageFiles.title"
      icon={FileArchive}
      initialNodes={initialNodes}
      rootLabel={packageRoot}
    />
  );
};

const MarketplaceSkillsFileViewer: React.FC<MarketplaceSkillsFileViewerProps> = ({ items }) => {
  const initialNodes = React.useMemo(() => marketplaceDetailFeatureItemsToFileTree(items, 'skills'), [items]);

  return (
    <MarketplaceReadOnlyFileTreeViewer
      titleKey="marketplace.editor.fileManager.skills.title"
      icon={Sparkles}
      initialNodes={initialNodes}
    />
  );
};

interface MarketplaceReadOnlyFileTreeViewerProps {
  titleKey: string;
  icon: React.ComponentType<{ className?: string }>;
  initialNodes: FileTreeNode[];
  rootLabel?: string;
}

const MarketplaceReadOnlyFileTreeViewer: React.FC<MarketplaceReadOnlyFileTreeViewerProps> = ({
  titleKey,
  icon: Icon,
  initialNodes,
  rootLabel,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [sidebarWidth, setSidebarWidth] = React.useState(MARKETPLACE_DETAIL_SIDEBAR_DEFAULT_WIDTH);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false);
  const [isSidebarResizing, setIsSidebarResizing] = React.useState(false);
  const sidebarResizeRef = React.useRef<{ startX: number; startWidth: number } | null>(null);
  const firstFilePath = React.useMemo(() => marketplaceDetailFindFirstFilePath(initialNodes), [initialNodes]);
  const treeState = useFileTreeState({
    initialNodes,
    initialExpandedIds: [],
    initialSelectedId: firstFilePath,
    enableMultiSelect: false,
  });
  const [activePath, setActivePath] = React.useState(firstFilePath ?? '');
  const contents = React.useMemo(() => marketplaceDetailFileContentsFromTree(initialNodes), [initialNodes]);

  const activeNode = React.useMemo(
    () => treeState.flatNodes.find(node => node.path === activePath && node.type === 'file') ?? null,
    [activePath, treeState.flatNodes],
  );

  React.useEffect(() => {
    if (activeNode) return;
    const nextFile = treeState.flatNodes.find(node => node.type === 'file');
    setActivePath(nextFile?.path ?? '');
  }, [activeNode, treeState.flatNodes]);

  const handleNodeClick = React.useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    treeState.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file') {
      setActivePath(node.path);
    }
  }, [treeState]);

  const handleNodeDoubleClick = React.useCallback((node: FileTreeNode) => {
    if (node.type === 'file') {
      setActivePath(node.path);
    } else {
      treeState.toggleNode(node.path);
    }
  }, [treeState]);

  const handleCopy = async () => {
    if (!activeNode) return;
    try {
      await navigator.clipboard.writeText(contents[activeNode.path] ?? '');
      toast({ title: t('marketplace.detail.viewer.copySuccess') });
    } catch {
      toast({ title: t('marketplace.detail.viewer.copyFailed'), variant: 'destructive' });
    }
  };

  const handleDownload = () => {
    if (!activeNode) return;
    const blob = new Blob([contents[activeNode.path] ?? ''], { type: 'text/markdown' });
    downloadBlob(blob, activeNode.name);
  };

  const handleSidebarResizeStart = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsSidebarCollapsed(false);
    setIsSidebarResizing(true);
    sidebarResizeRef.current = {
      startX: event.clientX,
      startWidth: isSidebarCollapsed ? MARKETPLACE_DETAIL_SIDEBAR_MIN_WIDTH : sidebarWidth,
    };
    document.body.classList.add('select-none', 'cursor-col-resize');
  };

  React.useEffect(() => {
    if (!isSidebarResizing) return undefined;

    const handleMouseMove = (event: MouseEvent) => {
      const dragState = sidebarResizeRef.current;
      if (!dragState) return;
      const nextWidth = Math.min(
        Math.max(dragState.startWidth + event.clientX - dragState.startX, MARKETPLACE_DETAIL_SIDEBAR_MIN_WIDTH),
        MARKETPLACE_DETAIL_SIDEBAR_MAX_WIDTH,
      );
      setSidebarWidth(nextWidth);
    };

    const handleMouseUp = () => {
      sidebarResizeRef.current = null;
      setIsSidebarResizing(false);
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };
  }, [isSidebarResizing]);

  return (
    <div className="flex h-full overflow-hidden border-x border-b bg-background">
      <div
        className="relative flex-shrink-0"
        style={{ width: isSidebarCollapsed ? MARKETPLACE_DETAIL_SIDEBAR_COLLAPSED_WIDTH : sidebarWidth }}
      >
        {isSidebarCollapsed ? (
          <div className="flex h-full flex-col items-center gap-2 border-r border-border bg-background px-1 py-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              aria-label={t('marketplace.detail.viewer.expandSidebar')}
              title={t('marketplace.detail.viewer.expandSidebar')}
              onClick={() => setIsSidebarCollapsed(false)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Icon className="h-4 w-4 text-primary" />
          </div>
        ) : (
          <MarketplaceSectionSidebarShell
            title={t(titleKey)}
            icon={<Icon className="h-4 w-4" />}
            actions={(
              <>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  title={t('marketplace.detail.viewer.refresh')}
                  aria-label={t('marketplace.detail.viewer.refresh')}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  title={t('marketplace.detail.viewer.collapseSidebar')}
                  aria-label={t('marketplace.detail.viewer.collapseSidebar')}
                  onClick={() => setIsSidebarCollapsed(true)}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </>
            )}
            searchValue={treeState.searchQuery}
            onSearchChange={treeState.setSearchQuery}
            onSearchClear={treeState.clearSearch}
            searchPlaceholder={t('marketplace.editor.fileManager.search.placeholder')}
            body={(
              <div className="flex h-full min-h-0 flex-col">
                {rootLabel ? (
                  <div className="border-b border-border bg-muted/20 px-3 py-2">
                    <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                      {t('marketplace.editor.fileManager.packageFiles.rootLabel')}
                    </div>
                    <div className="mt-1 truncate font-mono text-xs text-foreground" title={rootLabel}>
                      {rootLabel}
                    </div>
                  </div>
                ) : null}
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
              </div>
            )}
          />
        )}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label={t('marketplace.detail.viewer.resizeSidebar')}
          className={cn(
            'absolute right-0 top-0 z-20 h-full w-1 cursor-col-resize transition-colors',
            isSidebarResizing ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
          )}
          onMouseDown={handleSidebarResizeStart}
        />
      </div>

      <div className="min-w-0 flex-1 overflow-hidden">
        {!activeNode ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t('marketplace.editor.fileManager.viewer.noFile')}
          </div>
        ) : (
          <div className="flex h-full flex-col bg-background">
            <div className="flex h-12 items-center justify-between border-b border-border px-4">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-foreground">{activeNode.name}</div>
                <div className="truncate font-mono text-xs text-muted-foreground">{activeNode.path}</div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleCopy}>
                  <Copy className="mr-1.5 h-3.5 w-3.5" />
                  {t('marketplace.detail.viewer.copy')}
                </Button>
                <Button variant="outline" size="sm" onClick={handleDownload}>
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  {t('marketplace.detail.viewer.download')}
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <div className="mx-auto max-w-4xl">
                <MarketplaceFileContentPreview
                  fileName={activeNode.name}
                  content={contents[activeNode.path] ?? ''}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const MarketplaceFeatureViewer: React.FC<MarketplaceFeatureViewerProps> = ({ title, items, icon: Icon }) => {
  const { t } = useI18n();
  const normalizedItems = React.useMemo(
    () => items.map(item => ({
      ...item,
      fileName: toFileName(item),
      content: toMarkdownContent(item),
    })),
    [items],
  );
  const [selectedId, setSelectedId] = React.useState(normalizedItems[0]?.id ?? '');
  const [searchTerm, setSearchTerm] = React.useState('');

  React.useEffect(() => {
    setSelectedId(normalizedItems[0]?.id ?? '');
    setSearchTerm('');
  }, [normalizedItems]);

  const filteredItems = React.useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) return normalizedItems;
    return normalizedItems.filter(item =>
      [item.name, item.description, item.path, item.content].filter(Boolean).join(' ').toLowerCase().includes(query),
    );
  }, [normalizedItems, searchTerm]);

  React.useEffect(() => {
    if (!filteredItems.some(item => item.id === selectedId)) {
      setSelectedId(filteredItems[0]?.id ?? '');
    }
  }, [filteredItems, selectedId]);

  const selectedItem = filteredItems.find(item => item.id === selectedId) ?? filteredItems[0];

  return (
    <MarketplaceDocumentShell
      title={title}
      items={filteredItems}
      allItemsCount={normalizedItems.length}
      selectedItem={selectedItem}
      searchTerm={searchTerm}
      onSearchTermChange={setSearchTerm}
      onSelectItem={item => setSelectedId(item.id)}
      icon={Icon}
      emptyLabel={t('marketplace.detail.featureEmpty')}
    />
  );
};

interface MarketplaceDocumentShellItem extends MarketplaceFeatureContentItem {
  fileName: string;
  content: string;
}

interface MarketplaceDocumentShellProps {
  title: string;
  items: MarketplaceDocumentShellItem[];
  allItemsCount: number;
  selectedItem?: MarketplaceDocumentShellItem;
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  onSelectItem: (item: MarketplaceDocumentShellItem) => void;
  icon: React.ComponentType<{ className?: string }>;
  emptyLabel: string;
  hideSearch?: boolean;
}

const MarketplaceDocumentShell: React.FC<MarketplaceDocumentShellProps> = ({
  title,
  items,
  allItemsCount,
  selectedItem,
  searchTerm,
  onSearchTermChange,
  onSelectItem,
  icon: Icon,
  emptyLabel,
  hideSearch = false,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [sidebarWidth, setSidebarWidth] = React.useState(MARKETPLACE_DETAIL_SIDEBAR_DEFAULT_WIDTH);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false);
  const [isSidebarResizing, setIsSidebarResizing] = React.useState(false);
  const sidebarResizeRef = React.useRef<{ startX: number; startWidth: number } | null>(null);
  const selectedIndex = selectedItem ? items.findIndex(item => item.id === selectedItem.id) : -1;
  const canNavigatePrevious = selectedIndex > 0;
  const canNavigateNext = selectedIndex >= 0 && selectedIndex < items.length - 1;
  const searchPlaceholder = resolveI18nText(
    t,
    'marketplace.detail.viewer.searchPlaceholder',
    'marketplace.center.filters.searchPlaceholder',
  );
  const itemNameFallback = resolveI18nText(
    t,
    'marketplace.detail.viewer.fileNameFallback',
    'marketplace.common.unknown',
  );
  const descriptionFallback = resolveI18nText(
    t,
    'marketplace.detail.viewer.descriptionFallback',
    'marketplace.common.unknown',
  );

  const navigateToPrevious = () => {
    if (canNavigatePrevious) onSelectItem(items[selectedIndex - 1]);
  };

  const navigateToNext = () => {
    if (canNavigateNext) onSelectItem(items[selectedIndex + 1]);
  };

  const handleCopy = async () => {
    if (!selectedItem) return;
    try {
      await navigator.clipboard.writeText(selectedItem.content);
      toast({ title: t('marketplace.detail.viewer.copySuccess') });
    } catch {
      toast({ title: t('marketplace.detail.viewer.copyFailed'), variant: 'destructive' });
    }
  };

  const handleDownload = () => {
    if (!selectedItem) return;
    const blob = new Blob([selectedItem.content], { type: 'text/markdown' });
    downloadBlob(blob, selectedItem.fileName);
  };

  const handleSidebarResizeStart = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsSidebarCollapsed(false);
    setIsSidebarResizing(true);
    sidebarResizeRef.current = {
      startX: event.clientX,
      startWidth: isSidebarCollapsed ? MARKETPLACE_DETAIL_SIDEBAR_MIN_WIDTH : sidebarWidth,
    };
    document.body.classList.add('select-none', 'cursor-col-resize');
  };

  React.useEffect(() => {
    if (!isSidebarResizing) return undefined;

    const handleMouseMove = (event: MouseEvent) => {
      const dragState = sidebarResizeRef.current;
      if (!dragState) return;
      const nextWidth = Math.min(
        Math.max(dragState.startWidth + event.clientX - dragState.startX, MARKETPLACE_DETAIL_SIDEBAR_MIN_WIDTH),
        MARKETPLACE_DETAIL_SIDEBAR_MAX_WIDTH,
      );
      setSidebarWidth(nextWidth);
    };

    const handleMouseUp = () => {
      sidebarResizeRef.current = null;
      setIsSidebarResizing(false);
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };
  }, [isSidebarResizing]);

  const sidebarActions = (
    <>
      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" aria-label={t('marketplace.detail.viewer.refresh')}>
        <RefreshCw className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        aria-label={t('marketplace.detail.viewer.collapseSidebar')}
        title={t('marketplace.detail.viewer.collapseSidebar')}
        onClick={() => setIsSidebarCollapsed(true)}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>
    </>
  );

  const sidebarBody = (
    <div className="flex-1 space-y-2 overflow-y-auto p-3">
      {items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-xs text-muted-foreground">
          {emptyLabel}
        </div>
      ) : (
        items.map(item => {
          const isActive = selectedItem?.id === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectItem(item)}
              className={cn(
                'w-full rounded-lg border px-3 py-3 text-left transition-colors',
                isActive
                  ? 'border-primary/60 bg-primary/10 shadow-sm'
                  : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40',
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {item.fileName || item.name || itemNameFallback}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {item.description || item.path || descriptionFallback}
                  </div>
                </div>
                <div className="text-right text-[11px] text-muted-foreground">
                  {t('common.markdownFileViewer.units.bytes', { count: item.content.length })}
                </div>
              </div>
            </button>
          );
        })
      )}
    </div>
  );

  return (
    <div className="flex h-full overflow-hidden">
      <div
        className="relative flex-shrink-0"
        style={{ width: isSidebarCollapsed ? MARKETPLACE_DETAIL_SIDEBAR_COLLAPSED_WIDTH : sidebarWidth }}
      >
        {isSidebarCollapsed ? (
          <div className="flex h-full flex-col items-center gap-2 border-r border-border bg-background px-1 py-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              aria-label={t('marketplace.detail.viewer.expandSidebar')}
              title={t('marketplace.detail.viewer.expandSidebar')}
              onClick={() => setIsSidebarCollapsed(false)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Icon className="h-4 w-4 text-primary" />
          </div>
        ) : (
          <MarketplaceSectionSidebarShell
            title={title}
            icon={<Icon className="h-4 w-4" />}
            actions={sidebarActions}
            searchValue={hideSearch ? undefined : searchTerm}
            onSearchChange={hideSearch ? undefined : onSearchTermChange}
            onSearchClear={hideSearch ? undefined : () => onSearchTermChange('')}
            searchPlaceholder={searchPlaceholder}
            body={sidebarBody}
          />
        )}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label={t('marketplace.detail.viewer.resizeSidebar')}
          className={cn(
            'absolute right-0 top-0 z-20 h-full w-1 cursor-col-resize transition-colors',
            isSidebarResizing ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
          )}
          onMouseDown={handleSidebarResizeStart}
        />
      </div>

      <main className="min-w-0 flex-1 bg-background">
        {selectedItem ? (
          <div className="flex h-full flex-col">
            <div className="sticky top-0 z-10 border-b border-border bg-background">
              <div className="border-b border-border bg-background p-4">
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <div className="flex min-w-0 shrink-0 items-center gap-2">
                      <Icon className="h-5 w-5 shrink-0 text-primary" />
                      <h3 className="max-w-64 truncate font-semibold text-foreground">
                        {selectedItem.fileName || selectedItem.name || itemNameFallback}
                      </h3>
                    </div>
                    <p className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
                      {selectedItem.description || selectedItem.path || descriptionFallback}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <Button variant="outline" size="sm" onClick={navigateToPrevious} disabled={!canNavigatePrevious}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={navigateToNext} disabled={!canNavigateNext}>
                      <ChevronRight className="h-4 w-4" />
                    </Button>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={handleCopy}>
                          <Copy className="mr-2 h-3 w-3" />
                          {t('marketplace.detail.viewer.copy')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={handleDownload}>
                          <Download className="mr-2 h-3 w-3" />
                          {t('marketplace.detail.viewer.download')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>

              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <div className="mx-auto max-w-4xl">
                <MarketplaceFileContentPreview
                  fileName={selectedItem.fileName}
                  content={selectedItem.content}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <Icon className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{emptyLabel}</p>
          </div>
        )}
      </main>
    </div>
  );
};

interface MarketplaceFileContentPreviewProps {
  fileName: string;
  content: string;
}

const MarketplaceFileContentPreview: React.FC<MarketplaceFileContentPreviewProps> = ({ fileName, content }) => {
  if (marketplaceDetailIsMarkdownFile(fileName)) {
    return <MarkdownContent content={content} />;
  }

  return (
    <div className="h-[32rem] min-h-64 overflow-hidden rounded-md border border-border">
      <CodeTextEditor
        fileName={fileName}
        content={content}
        originalContent={content}
        readOnly
        onContentChange={() => undefined}
        onModifiedChange={() => undefined}
      />
    </div>
  );
};

const marketplaceDetailJoinPath = (parentPath: string | null | undefined, name: string) => (
  parentPath ? `${parentPath.replace(/\/$/, '')}/${name}` : name
);

const getMarketplaceDetailPackageRoot = (provider: MarketplaceProvider, packageId: string): string => (
  provider === 'gemini'
    ? `gemini/extensions/${packageId}`
    : `${provider}/plugins/${packageId}`
);

const marketplaceDetailIsMarkdownFile = (fileName: string): boolean => {
  const extension = fileName.split('.').pop()?.toLowerCase();
  return isMarkdownFile(fileName) || extension === 'mdx';
};

const marketplaceDetailFileContentsFromTree = (nodes: FileTreeNode[]): Record<string, string> => {
  const contents: Record<string, string> = {};
  const walk = (items: FileTreeNode[]) => {
    items.forEach(node => {
      if (node.type === 'file') {
        contents[node.path] = typeof node.metadata?.content === 'string' ? node.metadata.content : '';
      }
      if (node.children) {
        walk(node.children);
      }
    });
  };
  walk(nodes);
  return contents;
};

const marketplaceDetailFeatureItemsToFileTree = (
  items: MarketplaceFeatureContentItem[],
  basePath: string,
): FileTreeNode[] => {
  const roots: FileTreeNode[] = [];
  const directories = new Map<string, FileTreeNode>();

  const ensureDirectory = (path: string, name: string, parent: FileTreeNode[]) => {
    const existing = directories.get(path);
    if (existing) return existing;
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: 'directory',
      children: [],
    };
    directories.set(path, node);
    parent.push(node);
    return node;
  };

  items.forEach(item => {
    const sourcePath = item.path?.trim() || `${basePath}/${item.id}/SKILL.md`;
    const relativePath = sourcePath.replace(new RegExp(`^${basePath}/?`), '');
    const parts = relativePath.split('/').filter(Boolean);
    let parentChildren = roots;
    let currentPath = '';

    parts.slice(0, -1).forEach(part => {
      currentPath = marketplaceDetailJoinPath(currentPath || null, part);
      const directory = ensureDirectory(currentPath, part, parentChildren);
      parentChildren = directory.children ?? [];
    });

    const fileName = parts.at(-1) ?? toFileName(item);
    const filePath = marketplaceDetailJoinPath(currentPath || null, fileName);
    const content = toMarkdownContent(item);
    parentChildren.push({
      id: filePath,
      name: fileName,
      path: filePath,
      type: 'file',
      extension: fileName.split('.').pop(),
      size: content.length,
      metadata: { content },
    });
  });

  return sortTreeNodes(roots);
};

const marketplaceDetailPackageFilesToFileTree = (
  files: MarketplacePackageFile[],
  rootPath: string,
  scope: 'plugin' | 'extension',
): FileTreeNode[] => {
  const packageName = rootPath.split('/').at(-1) ?? rootPath;
  const root: FileTreeNode = {
    id: rootPath,
    name: packageName,
    path: rootPath,
    type: 'directory',
    scope,
    children: [],
  };
  const directories = new Map<string, FileTreeNode>([[rootPath, root]]);

  const ensureDirectory = (path: string, name: string, parentChildren: FileTreeNode[]) => {
    const existing = directories.get(path);
    if (existing) return existing;
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: 'directory',
      scope,
      children: [],
    };
    directories.set(path, node);
    parentChildren.push(node);
    return node;
  };

  files.forEach(file => {
    const parts = file.path.split('/').filter(Boolean);
    if (parts.length === 0) return;

    let currentPath = rootPath;
    let parentChildren = root.children ?? [];

    parts.slice(0, -1).forEach(part => {
      currentPath = marketplaceDetailJoinPath(currentPath, part);
      const directory = ensureDirectory(currentPath, part, parentChildren);
      parentChildren = directory.children ?? [];
    });

    const fileName = parts.at(-1);
    if (!fileName) return;
    const path = marketplaceDetailJoinPath(currentPath, fileName);
    parentChildren.push({
      id: path,
      name: fileName,
      path,
      type: 'file',
      extension: fileName.split('.').pop(),
      scope,
      size: file.size,
      metadata: {
        content: file.content,
        binary: file.binary,
        mimeType: file.mimeType,
      },
    });
  });

  return sortTreeNodes(root.children ?? []);
};

const marketplaceDetailFindFirstFilePath = (nodes: FileTreeNode[]): string | undefined => {
  for (const node of nodes) {
    if (node.type === 'file') return node.path;
    const childPath = node.children ? marketplaceDetailFindFirstFilePath(node.children) : undefined;
    if (childPath) return childPath;
  }
  return undefined;
};

export default MarketplaceDetailView;
