import React from 'react';
import {
  Copy,
  Download,
  FileText,
  Info,
  Server,
  Zap,
} from 'lucide-react';
import { DocumentContentDetail } from '@/shared/components/document-workflow';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Separator } from '@/shared/components/ui/separator';
import { HookCard, getHookEventI18nKey } from '@/shared/components/hook-workflow';
import { MCPServerCard, type MCPServerCardLabels } from '@/shared/components/mcp-workflow';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  SettingsWorkflowActionButton,
  SettingsWorkflowCountBadge,
  SettingsWorkflowShell,
} from '@/shared/components/settings-workflow';
import type {
  MarketplaceFeatureContentItem,
  MarketplacePackageDetail,
  MarketplaceProvider,
} from '@/features/marketplace/model/marketplaceTypes';
import { downloadBlob } from '../../../utils/downloadBlob';
import { MarketplaceInfoGridRow } from './MarketplaceInfoGridRow';
import {
  marketplaceHookCardEntriesFromItem,
  type MarketplaceHookCardEntry,
} from '../model/marketplaceDetailHookModel';

interface MarketplaceBasicInfoPanelProps {
  detail: MarketplacePackageDetail;
  onOpenVariant: (provider: MarketplaceProvider, packageId: string) => void;
}

interface MarketplaceMarkdownDetailPanelProps {
  title: string;
  content: string;
}

interface MarketplaceHooksWorkflowProps {
  provider: MarketplaceProvider;
  hooks: MarketplaceFeatureContentItem[];
}

interface MarketplaceMCPWorkflowProps {
  servers: MarketplaceFeatureContentItem[];
}

interface ValidationResultRowProps {
  severity: 'error' | 'warning' | 'info';
  severityLabel: string;
  message: string;
  code: string;
  filePath?: string;
}

interface MarketplaceHookCardProps {
  provider: MarketplaceProvider;
  entry: MarketplaceHookCardEntry;
}

interface MarketplaceMCPData {
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
            <MarketplaceInfoGridRow label={t('marketplace.detail.basicInfo.packageId')} value={detail.packageId} monospace />
            <MarketplaceInfoGridRow label={t('marketplace.detail.basicInfo.registryPath')} value={detail.registryPath} monospace />
            <MarketplaceInfoGridRow label={t('marketplace.detail.basicInfo.provider')} value={<Badge variant="outline">{t(`marketplace.providers.${detail.provider}`)}</Badge>} />
            <MarketplaceInfoGridRow label={t('marketplace.detail.basicInfo.version')} value={<Badge variant="secondary">{detail.version ?? t('marketplace.common.noVersion')}</Badge>} />
            {detail.familyDisplayName || detail.sourceIdentity ? (
              <MarketplaceInfoGridRow
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
              <MarketplaceInfoGridRow
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

export const MarketplaceMarkdownDetailPanel: React.FC<MarketplaceMarkdownDetailPanelProps> = ({ title, content }) => {
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
    <DocumentContentDetail
      title={title}
      content={content}
      format="markdown"
      metadata={[]}
      headerLeading={<FileText className="h-5 w-5 text-primary" />}
      headerActions={(
        <>
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleCopy}>
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.detail.agentsMd.actions.copy')}
          </Button>
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleDownload}>
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.detail.agentsMd.actions.download')}
          </Button>
        </>
      )}
      emptyPreview={<p className="text-sm text-muted-foreground">{t('marketplace.detail.agentsMd.placeholder')}</p>}
      readOnly
      onSave={() => undefined}
    />
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

export const MarketplaceMCPWorkflow: React.FC<MarketplaceMCPWorkflowProps> = ({ servers }) => {
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
  const data = toFeatureData<MarketplaceMCPData>(server);
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
