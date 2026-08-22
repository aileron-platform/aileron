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
          <dt className="text-muted-foreground">{t('marketplace.install.fields.targetClient')}</dt>
          <dd>{t(`marketplace.targetClients.${result.targetClient}`)}</dd>
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
      {(result.warnings ?? []).map(warning => (
        <p key={warning} className="mt-2 text-xs text-amber-600">
          {t(`marketplace.install.warnings.${warning.split('.').at(-1)}`)}
        </p>
      ))}
      {(result.commands ?? []).length > 0 ? (
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer font-medium">
            {t('marketplace.install.output.diagnostics')}
          </summary>
          <div className="mt-2 space-y-2">
            {(result.commands ?? []).map(command => (
              <div key={command.sequence} className="rounded border border-border p-2">
                <div className="font-mono">{command.argvDisplay}</div>
                <div className="text-muted-foreground">
                  {t(`marketplace.install.stages.${command.stage}`)} · {command.exitCode ?? t('marketplace.common.unknown')}
                </div>
                {command.stdout ? <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap">{command.stdout}</pre> : null}
                {command.stderr ? <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap">{command.stderr}</pre> : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
};
