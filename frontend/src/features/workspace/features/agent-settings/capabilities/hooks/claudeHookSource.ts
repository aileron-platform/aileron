import {
  buildHookRulesFromAgentHook,
  mapHookScopeDocumentToAgentHooks,
  type AgentHookRuleMap,
  type AgentHookScopeDocument,
} from '../../api/agentSettingsApi';
import type { HookSource } from '../../model/hookSource';
import type { HookDialogData } from '@/shared/components/hook-workflow';
import type {
  AgentHookScope,
  AgentHookWithEvent,
} from '../../model/agentHookTypes';

type AgentSettingsApi = {
  listHookScopes(runtimeBaseUrl: string, workspaceId: string): Promise<{ scopes: AgentHookScopeDocument[] }>;
  updateHookScope(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: string,
    hooks: AgentHookRuleMap,
    revision?: string,
  ): Promise<unknown>;
  deleteHookScope(runtimeBaseUrl: string, workspaceId: string, scope: string): Promise<unknown>;
};

const cloneRuleMap = (hooks: AgentHookRuleMap | undefined): AgentHookRuleMap => {
  if (!hooks) return {};
  return Object.fromEntries(
    Object.entries(hooks).map(([eventName, rules]) => [
      eventName,
      rules.map((rule) => ({
        matcher: rule.matcher,
        pluginName: rule.pluginName,
        marketplaceName: rule.marketplaceName,
        hooks: rule.hooks.map((action) => ({ ...action })),
      })),
    ]),
  );
};

const removeHookFromMap = (hooks: AgentHookRuleMap, target: HookDialogData): AgentHookRuleMap => {
  const next = cloneRuleMap(hooks);
  delete next[target.eventName];
  return next;
};

const upsertHookInMap = (
  hooks: AgentHookRuleMap,
  entry: HookDialogData,
  previous?: HookDialogData | null,
): AgentHookRuleMap => {
  const next = cloneRuleMap(hooks);
  if (previous && previous.scope === entry.scope && previous.eventName !== entry.eventName) {
    delete next[previous.eventName];
  }
  const rules = buildHookRulesFromAgentHook(entry as AgentHookWithEvent);
  if (rules.length > 0) {
    next[entry.eventName] = rules;
  } else {
    delete next[entry.eventName];
  }
  return next;
};

const isAgentHookScope = (
  scope: HookDialogData['scope'],
): scope is AgentHookScope => scope !== 'built_in';

export const createClaudeHookSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): HookSource => {
  const documents = async (): Promise<Record<string, AgentHookScopeDocument>> => {
    const response = await api.listHookScopes(runtimeBaseUrl, workspaceId);
    return Object.fromEntries(response.scopes.map((document) => [document.scope, document]));
  };

  return {
    list: async () => {
      const response = await api.listHookScopes(runtimeBaseUrl, workspaceId);
      return response.scopes.flatMap((document) => mapHookScopeDocumentToAgentHooks(document));
    },
    save: async (entry, previous) => {
      if (!isAgentHookScope(entry.scope)) return;
      const byScope = await documents();
      if (
        previous
        && previous.scope !== entry.scope
        && isAgentHookScope(previous.scope)
      ) {
        const previousDocument: AgentHookScopeDocument = byScope[previous.scope]
          ?? { scope: previous.scope, hooks: {} };
        const reducedMap = removeHookFromMap(previousDocument.hooks, previous);
        if (Object.keys(reducedMap).length === 0) {
          await api.deleteHookScope(runtimeBaseUrl, workspaceId, previous.scope);
        } else {
          await api.updateHookScope(runtimeBaseUrl, workspaceId, previous.scope, reducedMap, previousDocument.revision);
        }
      }

      const targetDocument: AgentHookScopeDocument = byScope[entry.scope]
        ?? { scope: entry.scope, hooks: {} };
      const updatedMap = upsertHookInMap(
        targetDocument.hooks,
        entry,
        previous?.scope === entry.scope ? previous : null,
      );
      await api.updateHookScope(runtimeBaseUrl, workspaceId, entry.scope, updatedMap, targetDocument.revision);
    },
    remove: async (entry) => {
      if (!isAgentHookScope(entry.scope)) return;
      const byScope = await documents();
      const document = byScope[entry.scope];
      if (!document) return;
      const updatedMap = removeHookFromMap(document.hooks, entry);
      if (Object.keys(updatedMap).length === 0) {
        await api.deleteHookScope(runtimeBaseUrl, workspaceId, entry.scope);
      } else {
        await api.updateHookScope(runtimeBaseUrl, workspaceId, entry.scope, updatedMap, document.revision);
      }
    },
  };
};
