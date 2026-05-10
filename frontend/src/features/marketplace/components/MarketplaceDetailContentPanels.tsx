import React from 'react';
import {
  Copy,
  Download,
  FileArchive,
  FileText,
  Info,
  Network,
  Server,
  Sparkles,
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
import { HookCard } from '@/shared/components/hook-workflow/HookCard';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { MCPServerCard, type MCPServerCardLabels } from '@/shared/components/mcp-workflow';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  SettingsWorkflowActionButton,
  SettingsWorkflowCountBadge,
  SettingsWorkflowShell,
} from '@/shared/components/settings-workflow';
import type { HookActionConfig, HookCardMatcher } from '@/shared/components/hook-workflow';
import type {
  MarketplaceFeatureContentItem,
  MarketplacePackageDetail,
  MarketplaceProvider,
} from '@/shared/types/marketplace';
import { getMarketplaceFeatureItemCount } from '../utils/marketplaceFeatureCounts';
import { downloadBlob } from '../utils/downloadBlob';
import { getMarketplaceFeatureLabelKey } from '../utils/featureLabels';
import { getHookEventI18nKey } from '@/shared/hooks/providerHookSpec';

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
  entry: MarketplaceHookCardEntry;
}

interface MarketplaceHookCardEntry {
  id: string;
  hook: MarketplaceFeatureContentItem;
  eventName: string;
  matchers: HookCardMatcher[];
  sourceDescription?: string;
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

interface MarketplaceDetailMCPCardProps {
  server: MarketplaceFeatureContentItem;
}

const toFeatureData = <T extends Record<string, unknown>>(item: MarketplaceFeatureContentItem): T =>
  (item.data ?? {}) as T;

const commonHookEventLabelKey = (eventName: string) => getHookEventI18nKey(eventName, 'label');
const commonHookEventDescriptionKey = (eventName: string) => getHookEventI18nKey(eventName, 'description');

const marketplaceHookCardEntriesFromItem = (hook: MarketplaceFeatureContentItem): MarketplaceHookCardEntry[] => {
  const data = toFeatureData<MarketplaceHookData>(hook);

  if (Array.isArray(data.matchers)) {
    const eventName = data.event ?? hook.name;
    return [
      {
        id: `${hook.id}:${eventName}`,
        hook,
        eventName,
        sourceDescription: hook.description ?? data.description,
        matchers: data.matchers.map((matcher) => ({
          event: matcher.event ?? eventName,
          matcher: matcher.matcher ?? '*',
          sequential: matcher.sequential,
          hooks: (matcher.hooks ?? []).map(normalizeMarketplaceHookAction),
        })),
      },
    ];
  }

  const nativeHookEntries = Object.entries(data.hooks ?? {}).flatMap(([eventName, eventMatchers], index) => (
    Array.isArray(eventMatchers)
      ? [{
        id: `${hook.id}:${eventName}`,
        hook,
        eventName,
        sourceDescription: index === 0 ? hook.description ?? data.description : undefined,
        matchers: eventMatchers.map((matcher) => ({
          event: matcher.event ?? eventName,
          matcher: matcher.matcher ?? '*',
          sequential: matcher.sequential,
          hooks: (matcher.hooks ?? []).map(normalizeMarketplaceHookAction),
        })),
      }]
      : []
  ));

  if (nativeHookEntries.length > 0) {
    return nativeHookEntries;
  }

  const eventName = data.event ?? hook.name;
  return [{
    id: `${hook.id}:${eventName}`,
    hook,
    eventName,
    sourceDescription: hook.description ?? data.description,
    matchers: [],
  }];
};

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
  const hookCardEntries = React.useMemo(
    () => hooks.flatMap(marketplaceHookCardEntriesFromItem),
    [hooks],
  );

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
      summary={<SettingsWorkflowCountBadge label={t('marketplace.detail.hooks.badge', { count: hookCardEntries.length })} />}
      singleHeader
      hasItems={hookCardEntries.length > 0}
      emptyIcon={<Zap className="h-6 w-6 text-muted-foreground" />}
      emptyTitle={t('marketplace.detail.hooks.empty.title')}
      emptyDescription={t('marketplace.detail.hooks.empty.description')}
      contentClassName="space-y-4 p-4"
    >
      {hookCardEntries.map(entry => (
        <MarketplaceHookCard key={entry.id} provider={provider} entry={entry} />
      ))}
    </SettingsWorkflowShell>
  );
};

const MarketplaceHookCard: React.FC<MarketplaceHookCardProps> = ({ provider, entry }) => {
  const { t } = useI18n();
  const { hook } = entry;

  return (
    <div className="relative rounded-lg border border-border bg-background p-6">
      <div className="flex items-start">
        <div className="min-w-0 flex-1">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            {hook.path ? <Badge variant="outline" className="text-xs">{hook.path}</Badge> : null}
          </div>

          <HookCard
            provider={provider}
            hook={{
              event: t(commonHookEventLabelKey(entry.eventName)),
              description: t(commonHookEventDescriptionKey(entry.eventName)),
              matchers: entry.matchers,
            }}
            i18nKeyPrefix="marketplace.detail.hooks.card"
            showHookDescription
          />
          {entry.sourceDescription ? (
            <p className="mt-4 text-sm text-muted-foreground">{entry.sourceDescription}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
};

const normalizeMarketplaceHookAction = (action: MarketplaceHookAction): HookActionConfig => {
  if (action.type === 'http') {
    return {
      type: 'http',
      name: action.name,
      description: action.description,
      url: action.url ?? '',
      headers: action.headers,
      allowedEnvVars: action.allowedEnvVars,
      timeout: action.timeout,
      statusMessage: action.statusMessage,
      if: action.if,
    };
  }
  if (action.type === 'mcp_tool') {
    return {
      type: 'mcp_tool',
      name: action.name,
      description: action.description,
      server: action.server ?? '',
      tool: action.tool ?? '',
      input: action.input,
      timeout: action.timeout,
      statusMessage: action.statusMessage,
      if: action.if,
    };
  }
  if (action.type === 'prompt' || action.type === 'agent') {
    return {
      type: action.type,
      name: action.name,
      description: action.description,
      prompt: action.prompt ?? '',
      model: action.model,
      timeout: action.timeout,
      statusMessage: action.statusMessage,
      if: action.if,
    };
  }
  return {
    type: 'command',
    name: action.name,
    description: action.description,
    command: action.command ?? '',
    timeout: action.timeout,
    statusMessage: action.statusMessage,
    if: action.if,
    shell: action.shell === 'powershell' ? 'powershell' : action.shell === 'bash' ? 'bash' : undefined,
    async: action.async,
    asyncRewake: action.asyncRewake,
  };
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
        <MarketplaceDetailMCPCard key={server.id} server={server} />
      ))}
    </SettingsWorkflowShell>
  );
};

const buildDetailMCPCardLabels = (t: (key: string) => string): MCPServerCardLabels => ({
  enabled: t('marketplace.detail.mcp.card.status.enabled'),
  disabled: t('marketplace.detail.mcp.card.status.disabled'),
  transportType: t('marketplace.detail.mcp.card.sections.transport'),
  serverUrl: t('marketplace.detail.mcp.card.sections.url'),
  headers: t('marketplace.detail.mcp.card.sections.headers'),
  command: t('marketplace.detail.mcp.card.sections.command'),
  commandArgs: t('marketplace.detail.mcp.card.sections.arguments'),
  env: t('marketplace.detail.mcp.card.sections.env'),
  showEnvValues: t('marketplace.detail.mcp.card.showEnvValues'),
  hideEnvValues: t('marketplace.detail.mcp.card.hideEnvValues'),
});

const MarketplaceDetailMCPCard: React.FC<MarketplaceDetailMCPCardProps> = ({ server }) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const labels = React.useMemo(() => buildDetailMCPCardLabels(t), [t]);
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

  return (
    <MCPServerCard
      server={{
        id: server.id,
        name: server.name,
        description: server.description,
        scope: server.path ?? '',
        transport: serverType === 'http' || serverType === 'sse' || serverType === 'stdio' ? serverType : 'stdio',
        command: data.command,
        args: data.args,
        url: data.url,
        env: data.env,
        headers: data.headers,
      }}
      scopeBadge={server.path ? <Badge variant="outline" className="font-mono text-xs">{server.path}</Badge> : null}
      labels={labels}
      supportsToggle={false}
      canEdit={false}
      canDelete={false}
      envVisible={showEnvValues}
      readOnlyIndicator={(
        <Button variant="ghost" size="sm" type="button" onClick={handleCopyConfig} title={t('marketplace.detail.mcp.card.copyTooltip')}>
          <Copy className="h-4 w-4" />
        </Button>
      )}
      onToggleEnvVisibility={() => setShowEnvValues(value => !value)}
    />
  );
};
