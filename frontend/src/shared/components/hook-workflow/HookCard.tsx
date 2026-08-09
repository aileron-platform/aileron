import React from 'react';
import { Terminal } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import type { HookActionConfig, HookMatcher } from './model/hookTypes';
import {
  getHookDefaults,
  getHookFieldSupport,
  type HookProvider,
} from './model/providerHookSpec';

export interface HookCardMatcher extends HookMatcher {
  event?: string | null;
}

export interface HookCardValue {
  event: string;
  description?: string | null;
  matchers: HookCardMatcher[];
}

export interface HookCardProps {
  provider: HookProvider;
  hook: HookCardValue;
  i18nKeyPrefix: string;
  actionPreviewLimit?: number;
  showHookDescription?: boolean;
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

const truncatePrompt = (prompt: string): string => (
  prompt.length > 80 ? `${prompt.slice(0, 80)}...` : prompt
);

const actionSummary = (action: HookActionConfig, t: Translate, i18nKeyPrefix: string): string => {
  if (action.type === 'http') return action.url?.trim() || t(`${i18nKeyPrefix}.emptyUrl`);
  if (action.type === 'mcp_tool') return [action.server, action.tool].filter(Boolean).join('.') || t(`${i18nKeyPrefix}.emptyCommand`);
  if (action.type === 'prompt' || action.type === 'agent') {
    const prompt = action.prompt?.trim();
    return prompt ? truncatePrompt(prompt) : t(`${i18nKeyPrefix}.emptyCommand`);
  }
  return action.command?.trim() || t(`${i18nKeyPrefix}.emptyCommand`);
};

const hasRecordEntries = (value: Record<string, unknown> | undefined): value is Record<string, unknown> => (
  Boolean(value && Object.keys(value).length > 0)
);

export const HookCard: React.FC<HookCardProps> = ({
  provider,
  hook,
  i18nKeyPrefix,
  actionPreviewLimit = 2,
  showHookDescription = true,
}) => {
  const { t } = useI18n();
  const fieldSupport = getHookFieldSupport(provider);
  const defaults = getHookDefaults(provider);
  const totalCommands = hook.matchers.reduce((acc, matcher) => acc + matcher.hooks.length, 0);

  return (
    <div className="min-w-0 flex-1">
      <div className="mb-3">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-lg font-semibold text-foreground">{hook.event}</h3>
        </div>
      </div>

      {showHookDescription && hook.description ? (
        <p className="mb-4 text-sm text-muted-foreground">{hook.description}</p>
      ) : null}

      <div className="mb-4">
        <div className="mb-3 flex items-center gap-2">
          <Terminal className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-muted-foreground">
            {t(`${i18nKeyPrefix}.matchersTitle`)}
          </span>
        </div>
        <div className="space-y-2">
          {hook.matchers.map((matcher, matcherIndex) => (
            <div
              key={`${hook.event}-matcher-${matcherIndex}`}
              className="rounded-lg bg-muted/50 p-3"
              data-testid="hook-card-matcher"
            >
              <div className="mb-2 flex items-center justify-between gap-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {t(`${i18nKeyPrefix}.matcherLabel`)}
                  </span>
                  <code className="rounded bg-muted px-1 text-xs">{matcher.matcher || '*'}</code>
                  {fieldSupport.sequential && matcher.sequential ? (
                    <Badge variant="outline" className="px-1 py-0 text-xs">
                      {t(`${i18nKeyPrefix}.sequential`)}
                    </Badge>
                  ) : null}
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {t(`${i18nKeyPrefix}.actionsCount`, { count: matcher.hooks.length })}
                </span>
              </div>
              {matcher.hooks.slice(0, actionPreviewLimit).map((action, actionIndex) => (
                <div
                  key={`${hook.event}-action-${matcherIndex}-${actionIndex}`}
                  className="mb-1 rounded bg-muted px-2 py-1 text-xs"
                  data-testid="hook-card-action"
                >
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="px-1 py-0 text-xs">
                      {t(`${i18nKeyPrefix}.executionTypes.${action.type}`)}
                    </Badge>
                    {fieldSupport.actionMetadata && action.name ? (
                      <span className="text-muted-foreground">{action.name}</span>
                    ) : null}
                    {action.timeout ? (
                      <span className="text-muted-foreground">
                        {defaults.timeoutUnit === 'ms'
                          ? t(`${i18nKeyPrefix}.timeoutMilliseconds`, { count: action.timeout })
                          : t(`${i18nKeyPrefix}.timeoutSeconds`, { count: action.timeout })}
                      </span>
                    ) : null}
                    {fieldSupport.statusMessage && action.statusMessage ? (
                      <span className="text-muted-foreground">
                        {t(`${i18nKeyPrefix}.statusMessage`, { value: action.statusMessage })}
                      </span>
                    ) : null}
                    {fieldSupport.additionalContextLimit && action.type === 'command' && action.additionalContextLimit !== undefined && action.additionalContextLimit !== null ? (
                      <span className="text-muted-foreground">
                        {t(`${i18nKeyPrefix}.additionalContextLimit`, { count: action.additionalContextLimit })}
                      </span>
                    ) : null}
                    {fieldSupport.commandWindows && action.type === 'command' && action.commandWindows ? (
                      <span className="text-muted-foreground">
                        {t(`${i18nKeyPrefix}.commandWindows`, { value: action.commandWindows })}
                      </span>
                    ) : null}
                    {fieldSupport.shell && action.type === 'command' && action.shell ? (
                      <span className="text-muted-foreground">
                        {t(`${i18nKeyPrefix}.shell`, { value: action.shell })}
                      </span>
                    ) : null}
                    {(action.type === 'prompt' || action.type === 'agent') && action.model ? (
                      <span className="text-muted-foreground">{action.model}</span>
                    ) : null}
                    {fieldSupport.async && action.type === 'command' && action.async ? (
                      <Badge variant="outline" className="px-1 py-0 text-xs">
                        {t(`${i18nKeyPrefix}.async`)}
                      </Badge>
                    ) : null}
                    {fieldSupport.async && action.type === 'command' && action.asyncRewake ? (
                      <Badge variant="outline" className="px-1 py-0 text-xs">
                        {t(`${i18nKeyPrefix}.asyncRewake`)}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="truncate font-mono text-muted-foreground">{actionSummary(action, t, i18nKeyPrefix)}</p>
                  {fieldSupport.condition && action.if ? (
                    <div className="mt-1 flex min-w-0 items-center gap-2 text-muted-foreground">
                      <span>{t(`${i18nKeyPrefix}.ifLabel`)}</span>
                      <code className="truncate rounded bg-background px-1 py-0.5 font-mono">
                        {action.if}
                      </code>
                    </div>
                  ) : null}
                  {fieldSupport.actionMetadata && action.description ? (
                    <p className="mt-1 truncate text-muted-foreground">{action.description}</p>
                  ) : null}
                  {action.type === 'http' && hasRecordEntries(action.headers) ? (
                    <details className="mt-2 rounded bg-background/60 px-2 py-1">
                      <summary className="cursor-pointer text-muted-foreground">
                        {t(`${i18nKeyPrefix}.headersTitle`)} · {t(`${i18nKeyPrefix}.headersItemCount`, { count: Object.keys(action.headers).length })}
                      </summary>
                      <div className="mt-1 space-y-1 font-mono text-muted-foreground">
                        {Object.entries(action.headers).map(([key, value]) => (
                          <div key={key}>{key}: {String(value)}</div>
                        ))}
                      </div>
                    </details>
                  ) : null}
                  {action.type === 'http' && action.allowedEnvVars?.length ? (
                    <details className="mt-2 rounded bg-background/60 px-2 py-1">
                      <summary className="cursor-pointer text-muted-foreground">
                        {t(`${i18nKeyPrefix}.envVarsTitle`)} · {t(`${i18nKeyPrefix}.envVarsItemCount`, { count: action.allowedEnvVars.length })}
                      </summary>
                      <ul className="mt-1 space-y-1 font-mono text-muted-foreground">
                        {action.allowedEnvVars.map((envVar) => (
                          <li key={envVar}>{envVar}</li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                  {action.type === 'mcp_tool' && hasRecordEntries(action.input) ? (
                    <details className="mt-2 rounded bg-background/60 px-2 py-1">
                      <summary className="cursor-pointer text-muted-foreground">
                        {t(`${i18nKeyPrefix}.inputTitle`)} · {t(`${i18nKeyPrefix}.inputItemCount`, { count: Object.keys(action.input).length })}
                      </summary>
                      <pre className="mt-1 overflow-auto whitespace-pre-wrap rounded bg-background p-2 text-muted-foreground">
                        <code>{JSON.stringify(action.input, null, 2)}</code>
                      </pre>
                    </details>
                  ) : null}
                </div>
              ))}
              {matcher.hooks.length > actionPreviewLimit ? (
                <div className="text-xs italic text-muted-foreground">
                  {t(`${i18nKeyPrefix}.moreActions`, { count: matcher.hooks.length - actionPreviewLimit })}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-4 rounded bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <span>{t(`${i18nKeyPrefix}.summary.matchers`, { count: hook.matchers.length })}</span>
        <span>{t(`${i18nKeyPrefix}.summary.commands`, { count: totalCommands })}</span>
      </div>
    </div>
  );
};
