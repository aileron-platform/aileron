import type { HookActionConfig, HookCardMatcher } from '@/shared/components/hook-workflow';
import type { MarketplaceFeatureContentItem } from '@/features/marketplace/model/marketplaceTypes';

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

export interface MarketplaceHookCardEntry {
  id: string;
  hook: MarketplaceFeatureContentItem;
  eventName: string;
  matchers: HookCardMatcher[];
  sourceDescription?: string;
}

const toFeatureData = <T extends Record<string, unknown>>(item: MarketplaceFeatureContentItem): T =>
  (item.data ?? {}) as T;

export const normalizeMarketplaceHookAction = (action: MarketplaceHookAction): HookActionConfig => {
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

export const marketplaceHookCardEntriesFromItem = (hook: MarketplaceFeatureContentItem): MarketplaceHookCardEntry[] => {
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
