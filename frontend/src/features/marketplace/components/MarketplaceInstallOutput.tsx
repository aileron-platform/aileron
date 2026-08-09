import React from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePluginCommandResult } from '@/features/marketplace/model/marketplaceTypes';

export const MarketplaceInstallOutput: React.FC<{
  result: MarketplacePluginCommandResult;
}> = ({ result }) => {
  const { t } = useI18n();

  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <div className="mb-2 text-xs font-medium text-muted-foreground">{t('marketplace.install.output.title')}</div>
      <dl className="mb-3 grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">{t('marketplace.install.output.provider')}</dt>
          <dd>{t(`marketplace.providers.${result.provider}`)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t('marketplace.install.output.stage')}</dt>
          <dd>{t(`marketplace.install.stages.${result.stage}`)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t('marketplace.install.output.exitCode')}</dt>
          <dd className="font-mono">
            {result.exitCode ?? t('marketplace.common.unknown')}
          </dd>
        </div>
      </dl>
      {result.cliMessage ? (
        <div className="mb-2 space-y-1">
          <div className="text-[11px] font-medium text-muted-foreground">{t('marketplace.install.output.message')}</div>
          <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-background p-2 text-xs">{result.cliMessage}</pre>
        </div>
      ) : null}
      {result.stdout ? (
        <div className="space-y-1">
          <div className="text-[11px] font-medium text-muted-foreground">{t('marketplace.install.output.stdout')}</div>
          <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-background p-2 text-xs">{result.stdout}</pre>
        </div>
      ) : null}
      {result.stderr ? (
        <div className="mt-2 space-y-1">
          <div className="text-[11px] font-medium text-muted-foreground">{t('marketplace.install.output.stderr')}</div>
          <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-background p-2 text-xs">{result.stderr}</pre>
        </div>
      ) : null}
      {result.truncated ? (
        <p className="mt-2 text-xs text-muted-foreground">{t('marketplace.install.output.truncated')}</p>
      ) : null}
    </div>
  );
};
