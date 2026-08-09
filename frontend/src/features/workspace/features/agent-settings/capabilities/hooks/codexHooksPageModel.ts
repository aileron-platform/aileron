import type { HookDialogData } from '@/shared/components/hook-workflow';
import type { CodexHookAction as ApiCodexHookAction, CodexHookEntry, CodexHookSource, CodexHookScope as ApiCodexHookScope } from '../../api/agentSettingsApi';

export type CodexLayer = 'user' | 'project';
export type CodexHookScope = ApiCodexHookScope;
export type CodexHookAction = {
  type: 'command';
  command?: string;
  timeout?: number | null;
  statusMessage?: string | null;
  async?: boolean | null;
  commandWindows?: string | null;
  additionalContextLimit?: number | null;
  raw?: Record<string, unknown>;
};

export interface CodexHookListItem {
  id: string;
  scope: CodexHookScope;
  eventName: string;
  matchers: HookDialogData['matchers'];
  pluginName?: string;
  marketplaceName?: string;
  pluginId?: string;
  trustState?: 'trusted' | 'untrusted' | 'modified' | 'mixed';
  trusted?: boolean;
  effective?: boolean;
  trustRevision?: string;
  generation?: number;
  source: CodexHookSource;
  layer: CodexHookScope | null;
  readOnly: boolean;
  rawContent?: string;
  sourcePath?: string | null;
  entryIndexes?: number[];
}

const sourceToScope = (entry: CodexHookEntry): CodexHookScope => {
  if (entry.hookScope) return entry.hookScope;
  if ((entry.source === 'hooks_json' || entry.source === 'inline_config') && entry.layer) {
    return entry.layer;
  }
  return entry.source === 'session' ? 'session' : 'plugin';
};

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

const mapEntryAction = (action: ApiCodexHookAction): CodexHookAction => {
  if (!isRecord(action)) {
    return { type: 'command', command: '' };
  }
  if (action.type !== 'command') {
    return { type: 'command', command: '', raw: action };
  }
  const commandWindows = isRecord(action)
    ? action.commandWindows ?? action.command_windows
    : undefined;
  return {
    type: 'command',
    command: typeof action.command === 'string' ? action.command : '',
    timeout: typeof action.timeout === 'number' ? action.timeout : undefined,
    statusMessage: typeof action.statusMessage === 'string' ? action.statusMessage : undefined,
    async: typeof action.async === 'boolean' ? action.async : undefined,
    commandWindows: typeof commandWindows === 'string' ? commandWindows : undefined,
    additionalContextLimit: typeof action.additionalContextLimit === 'number' ? action.additionalContextLimit : undefined,
    raw: isRecord(action.raw) ? action.raw : action,
  };
};

const commandOf = (action: HookDialogData['matchers'][number]['hooks'][number]): string =>
  action.type === 'command' ? action.command : '';

const toCodexCommandAction = (
  action: HookDialogData['matchers'][number]['hooks'][number],
): Record<string, unknown> => {
  const raw = isRecord(action.raw) ? { ...action.raw } : {};
  if (raw.type && raw.type !== 'command') return raw;

  const result: Record<string, unknown> = {
    ...raw,
    type: 'command',
    command: commandOf(action),
  };
  if (typeof action.timeout === 'number') result.timeout = action.timeout;
  if (action.statusMessage !== undefined) {
    if (action.statusMessage?.trim()) result.statusMessage = action.statusMessage.trim();
    else delete result.statusMessage;
  }
  if (action.commandWindows === null) {
    delete result.commandWindows;
    delete result.command_windows;
  } else if (action.commandWindows !== undefined) {
    result.commandWindows = action.commandWindows;
    delete result.command_windows;
  }
  if (action.additionalContextLimit === null) delete result.additionalContextLimit;
  else if (action.additionalContextLimit !== undefined) result.additionalContextLimit = action.additionalContextLimit;
  return result;
};

export const mapCodexHookEntriesToItems = (entries: CodexHookEntry[]): CodexHookListItem[] => {
  const grouped = new Map<string, CodexHookListItem>();
  for (const entry of entries) {
    const scope = sourceToScope(entry);
    const layer = entry.layer === 'project' || entry.layer === 'user' ? entry.layer : null;
    const key = `${entry.source}:${scope}:${layer ?? ''}:${entry.event}:${entry.pluginId ?? ''}:${entry.sourcePath ?? ''}`;
    const item = grouped.get(key) ?? {
      id: key,
      scope,
      layer,
      source: entry.source,
      eventName: entry.event,
      matchers: [],
      pluginName: entry.pluginName ?? undefined,
      marketplaceName: entry.marketplaceName ?? undefined,
      pluginId: entry.pluginId ?? undefined,
      trustState: entry.trustState,
      trusted: entry.trusted,
      effective: entry.effective,
      trustRevision: entry.trustRevision,
      generation: entry.generation,
      readOnly: entry.readOnly,
      sourcePath: entry.sourcePath,
      rawContent: entry.raw ? JSON.stringify(entry.raw, null, 2) : undefined,
      entryIndexes: [],
    };
    item.matchers.push({
      matcher: entry.matcher || '*',
      hooks: entry.actions.map(mapEntryAction) as HookDialogData['matchers'][number]['hooks'],
      raw: entry.raw,
    });
    item.entryIndexes?.push(entry.index);
    grouped.set(key, item);
  }
  return Array.from(grouped.values());
};

export const toHookDialogData = (hook: CodexHookListItem | null): HookDialogData | null => {
  if (!hook) return null;
  return {
    id: hook.id,
    scope: hook.scope,
    eventName: hook.eventName,
    matchers: hook.matchers,
    pluginName: hook.pluginName,
    marketplaceName: hook.marketplaceName,
    pluginId: hook.pluginId,
    trustState: hook.trustState,
    trusted: hook.trusted,
    effective: hook.effective,
    trustRevision: hook.trustRevision,
    generation: hook.generation,
    readOnly: hook.readOnly,
    source: hook.source,
    sourcePath: hook.sourcePath,
    rawContent: hook.rawContent,
    metadata: {
    },
  };
};

export const toCodexHookEntry = (hook: HookDialogData): CodexHookEntry => {
  const matcher = hook.matchers[0];
  return {
    id: hook.id,
    event: hook.eventName,
    index: 0,
    matcher: matcher?.matcher && matcher.matcher !== '*' ? matcher.matcher : matcher?.matcher ?? null,
    actions: (matcher?.hooks ?? []).map(toCodexCommandAction),
    action: {},
    source: hook.source,
    layer: hook.scope === 'user' || hook.scope === 'project' ? hook.scope : null,
    hookScope: hook.scope,
    readOnly: hook.readOnly,
    raw: typeof matcher?.raw === 'object' && matcher.raw !== null ? matcher.raw : {},
  };
};
