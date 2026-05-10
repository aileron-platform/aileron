import React from 'react';
import {
  Copy,
  Database,
  Download,
  Eye,
  EyeOff,
  FileArchive,
  FileText,
  Info,
  Network,
  Server,
  Sparkles,
  Terminal,
  Wand2,
  Zap,
  Bot,
  Command,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Separator } from '@/shared/components/ui/separator';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { getHookDefaults, getHookFieldSupport } from '@/shared/hooks/providerHookSpec';
import {
  SettingsWorkflowActionButton,
  SettingsWorkflowCountBadge,
  SettingsWorkflowShell,
} from '@/shared/components/settings-workflow';
import type {
  MarketplaceFeatureContentItem,
  MarketplacePackageDetail,
  MarketplaceProvider,
} from '@/shared/types/marketplace';
import { getMarketplaceFeatureItemCount } from '../utils/marketplaceFeatureCounts';
import { downloadBlob } from '../utils/downloadBlob';
import { getMarketplaceFeatureLabelKey } from '../utils/featureLabels';

export type MarketplaceDetailFeatureTab =
  | 'agents-md'
  | 'hooks'
  | 'mcp'
  | 'agent'
  | 'commands'
  | 'output-style'
  | 'skills'
  | 'files';

export interface MarketplaceDetailFeatureItem {
  id: MarketplaceDetailFeatureTab;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  count: number;
}

interface MarketplaceBasicInfoPanelProps {
  detail: MarketplacePackageDetail;
  onOpenVariant: (provider: MarketplaceProvider, packageId: string) => void;
}

interface MarketplaceAgentsMdPanelProps {
  title: string;
  content: string;
}

interface MarketplaceHooksWorkflowProps {
  provider: MarketplaceProvider;
  hooks: MarketplaceFeatureContentItem[];
}

interface MarketplaceMcpWorkflowProps {
  servers: MarketplaceFeatureContentItem[];
}

interface InfoGridRowProps {
  label: string;
  value: React.ReactNode;
  monospace?: boolean;
}

interface ValidationResultRowProps {
  severity: 'error' | 'warning' | 'info';
  severityLabel: string;
  message: string;
  code: string;
  filePath?: string;
}

interface MarketplaceHookAction {
  type?: string;
  name?: string;
  description?: string;
  command?: string;
  url?: string;
  headers?: Record<string, string>;
  allowedEnvVars?: string[];
  server?: string;
  tool?: string;
  input?: Record<string, unknown>;
  prompt?: string;
  model?: string;
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

interface MarketplaceHookCardProps {
  provider: MarketplaceProvider;
  hook: MarketplaceFeatureContentItem;
}

interface MarketplaceMcpData {
  transport?: string;
  type?: string;
  url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
}

interface MarketplaceMcpServerCardProps {
  server: MarketplaceFeatureContentItem;
}

const toFeatureData = <T extends Record<string, unknown>>(item: MarketplaceFeatureContentItem): T =>
  (item.data ?? {}) as T;

export const getMarketplaceDetailFeatureItems = (
  detail: MarketplacePackageDetail,
  t: (key: string, params?: Record<string, unknown>) => string,
): MarketplaceDetailFeatureItem[] => {
  const items: MarketplaceDetailFeatureItem[] = [
    { id: 'agents-md', name: t(getMarketplaceFeatureLabelKey(detail.provider, 'agentsMd')), icon: FileText, count: detail.featureContent.agentsMd ? 1 : 0 },
    { id: 'hooks', name: t('marketplace.features.hooks'), icon: Zap, count: getMarketplaceFeatureItemCount(detail.featureContent.hooks, 'hooks') },
    { id: 'mcp', name: t('marketplace.features.mcp'), icon: Network, count: getMarketplaceFeatureItemCount(detail.featureContent.mcpServers, 'mcp') },
    { id: 'agent', name: t('marketplace.features.subagents'), icon: Bot, count: getMarketplaceFeatureItemCount(detail.featureContent.agents, 'agents') },
    { id: 'commands', name: t('marketplace.features.slashCommands'), icon: Command, count: getMarketplaceFeatureItemCount(detail.featureContent.commands, 'commands') },
    { id: 'output-style', name: t('marketplace.features.outputStyle'), icon: Wand2, count: getMarketplaceFeatureItemCount(detail.featureContent.outputStyles, 'output-styles') },
    { id: 'skills', name: t('marketplace.features.skills'), icon: Sparkles, count: getMarketplaceFeatureItemCount(detail.featureContent.skills, 'skills') },
    { id: 'files', name: t('marketplace.detail.tabs.files'), icon: FileArchive, count: detail.packageFiles.length },
  ];

  return items.filter(item => {
    if (item.id === 'mcp') return detail.provider !== 'gemini' || item.count > 0;
    if (item.id === 'output-style') return detail.provider === 'claude-code' || item.count > 0;
    return true;
  });
};

const InfoGridRow: React.FC<InfoGridRowProps> = ({ label, value, monospace = false }) => (
  <div className="grid grid-cols-3 gap-4">
    <div className="text-sm font-medium text-muted-foreground">{label}</div>
    <div className={`col-span-2 break-words text-sm text-foreground ${monospace ? 'font-mono' : ''}`}>{value}</div>
  </div>
);

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

export const MarketplaceBasicInfoPanel: React.FC<MarketplaceBasicInfoPanelProps> = ({ detail, onOpenVariant }) => {
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

export const MarketplaceAgentsMdPanel: React.FC<MarketplaceAgentsMdPanelProps> = ({ title, content }) => {
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

export const MarketplaceHooksWorkflow: React.FC<MarketplaceHooksWorkflowProps> = ({ provider, hooks }) => {
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

const MarketplaceHookCard: React.FC<MarketplaceHookCardProps> = ({ provider, hook }) => {
  const { t } = useI18n();
  const fieldSupport = getHookFieldSupport(provider);
  const defaults = getHookDefaults(provider);
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
                        {fieldSupport.sequential && matcher.sequential ? (
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
                          {fieldSupport.actionMetadata && action.name ? (
                            <span className="text-muted-foreground">{action.name}</span>
                          ) : null}
                          {action.timeout ? (
                            <span className="text-muted-foreground">
                              {defaults.timeoutUnit === 'ms'
                                ? t('marketplace.detail.hooks.card.timeoutMilliseconds', { count: action.timeout })
                                : t('marketplace.detail.hooks.card.timeoutSeconds', { count: action.timeout })}
                            </span>
                          ) : null}
                          {fieldSupport.statusMessage && action.statusMessage ? (
                            <span className="text-muted-foreground">
                              {t('marketplace.detail.hooks.card.statusMessage', { value: action.statusMessage })}
                            </span>
                          ) : null}
                          {fieldSupport.shell && action.shell ? (
                            <span className="text-muted-foreground">
                              {t('marketplace.detail.hooks.card.shell', { value: action.shell })}
                            </span>
                          ) : null}
                          {action.type === 'http' && action.headers ? (
                            <span className="text-muted-foreground">
                              {t('marketplace.detail.hooks.card.headersCount', { count: Object.keys(action.headers).length })}
                            </span>
                          ) : null}
                          {action.type === 'http' && action.allowedEnvVars ? (
                            <span className="text-muted-foreground">
                              {t('marketplace.detail.hooks.card.envVarsCount', { count: action.allowedEnvVars.length })}
                            </span>
                          ) : null}
                          {(action.type === 'prompt' || action.type === 'agent') && action.model ? (
                            <span className="text-muted-foreground">{action.model}</span>
                          ) : null}
                          {fieldSupport.async && action.async ? (
                            <Badge variant="outline" className="px-1 py-0 text-xs">
                              {t('marketplace.detail.hooks.card.async')}
                            </Badge>
                          ) : null}
                          {fieldSupport.async && action.asyncRewake ? (
                            <Badge variant="outline" className="px-1 py-0 text-xs">
                              {t('marketplace.detail.hooks.card.asyncRewake')}
                            </Badge>
                          ) : null}
                        </div>
                        <p className="truncate font-mono text-muted-foreground">{marketplaceDetailHookActionSummary(action, t)}</p>
                        {fieldSupport.condition && action.if ? (
                          <div className="mt-1 flex min-w-0 items-center gap-2 text-muted-foreground">
                            <span>{t('marketplace.detail.hooks.card.ifLabel')}</span>
                            <code className="truncate rounded bg-background px-1 py-0.5 font-mono">
                              {action.if}
                            </code>
                          </div>
                        ) : null}
                        {fieldSupport.actionMetadata && action.description ? (
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

const marketplaceDetailHookActionSummary = (
  action: MarketplaceHookAction,
  t: (key: string, params?: Record<string, unknown>) => string,
): string => {
  if (action.type === 'http') return action.url?.trim() || t('marketplace.detail.hooks.card.emptyUrl');
  if (action.type === 'mcp_tool') return [action.server, action.tool].filter(Boolean).join('.') || t('marketplace.detail.hooks.card.emptyCommand');
  if (action.type === 'prompt' || action.type === 'agent') {
    const prompt = action.prompt?.trim() || t('marketplace.detail.hooks.card.emptyCommand');
    return prompt.length > 80 ? `${prompt.slice(0, 80)}...` : prompt;
  }
  return action.command?.trim() || t('marketplace.detail.hooks.card.emptyCommand');
};

export const MarketplaceMcpWorkflow: React.FC<MarketplaceMcpWorkflowProps> = ({ servers }) => {
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
