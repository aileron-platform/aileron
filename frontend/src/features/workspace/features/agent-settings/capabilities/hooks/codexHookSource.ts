import type { HookSource } from '../../model/hookSource';
import type { HookDialogData } from '@/shared/components/hook-workflow';
import type { CodexHookEntry, CodexHooksScopesResponse } from '../../api/agentSettingsApi';
import { mapCodexHookEntriesToItems, toCodexHookEntry, toHookDialogData } from './codexHooksPageModel';

type AgentSettingsApi = {
  listCodexHooksScopes(runtimeBaseUrl: string, workspaceId: string): Promise<CodexHooksScopesResponse>;
  upsertCodexHookEntry(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    entry: CodexHookEntry,
    revision?: string,
    previous?: CodexHookEntry | null,
  ): Promise<unknown>;
  deleteCodexHookEntry(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    entry: CodexHookEntry,
    revision?: string,
  ): Promise<unknown>;
  enableCodexHooks(runtimeBaseUrl: string, workspaceId: string, layer: 'user' | 'project'): Promise<unknown>;
  disableCodexHooks(runtimeBaseUrl: string, workspaceId: string, layer: 'user' | 'project'): Promise<unknown>;
  updateCodexPluginHookTrust(
    runtimeBaseUrl: string,
    workspaceId: string,
    pluginId: string,
    trusted: boolean,
    revision: string,
  ): Promise<unknown>;
};

const editableLayerOf = (entry: HookDialogData): 'user' | 'project' => (
  entry.scope === 'user' ? 'user' : 'project'
);

export const createCodexHookSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): HookSource => {
  const revisions = new Map<string, string>();
  let scopesCache: CodexHooksScopesResponse | null = null;
  let scopesPromise: Promise<CodexHooksScopesResponse> | null = null;
  const listScopes = async (): Promise<CodexHooksScopesResponse> => {
    if (scopesCache) return scopesCache;
    if (scopesPromise) return scopesPromise;
    scopesPromise = api.listCodexHooksScopes(runtimeBaseUrl, workspaceId);
    const response = await scopesPromise.finally(() => {
      scopesPromise = null;
    });
    scopesCache = response;
    for (const scope of response.scopes) {
      if ((scope.scope === 'project' || scope.scope === 'user') && scope.revision) {
        revisions.set(`${scope.scope}:${scope.source ?? 'hooks_json'}`, scope.revision);
      }
    }
    return response;
  };
  const revisionFor = async (layer: 'user' | 'project', source: 'hooks_json' | 'inline_config' = 'hooks_json'): Promise<string> => {
    const current = revisions.get(`${layer}:${source}`);
    if (current) return current;
    await listScopes();
    return revisions.get(`${layer}:${source}`) ?? '';
  };

  return {
    list: async () => {
      const response = await listScopes();
      const entries = response.scopes.flatMap((scope) => scope.entries);
      return mapCodexHookEntriesToItems(entries)
        .map(toHookDialogData)
        .filter((hook): hook is HookDialogData => hook !== null);
    },
    save: async (entry, previous) => {
      const layer = editableLayerOf(entry);
      const response = await api.upsertCodexHookEntry(
        runtimeBaseUrl,
        workspaceId,
        layer,
        toCodexHookEntry(entry),
        await revisionFor(layer, entry.source === 'inline_config' ? 'inline_config' : 'hooks_json'),
        previous ? toCodexHookEntry(previous) : null,
      );
      if ((response as { revision?: string } | undefined)?.revision) {
        revisions.set(
          `${layer}:${entry.source === 'inline_config' ? 'inline_config' : 'hooks_json'}`,
          (response as { revision: string }).revision,
        );
      }
      scopesCache = null;
    },
    remove: async (entry) => {
      const layer = editableLayerOf(entry);
      const response = await api.deleteCodexHookEntry(
        runtimeBaseUrl,
        workspaceId,
        layer,
        toCodexHookEntry(entry),
        await revisionFor(layer, entry.source === 'inline_config' ? 'inline_config' : 'hooks_json'),
      );
      if ((response as { revision?: string } | undefined)?.revision) {
        revisions.set(
          `${layer}:${entry.source === 'inline_config' ? 'inline_config' : 'hooks_json'}`,
          (response as { revision: string }).revision,
        );
      }
      scopesCache = null;
    },
    featureEnablement: {
      isEnabled: async (scope) => {
        const response = await listScopes();
        if (scope) {
          return response.scopes
            .filter((item) => item.scope === scope)
            .some((item) => item.featureEnabled);
        }
        return response.scopes.some((item) => item.effectiveFeatureEnabled ?? item.featureEnabled);
      },
      enable: async (scope = 'project') => {
        await api.enableCodexHooks(runtimeBaseUrl, workspaceId, scope);
        scopesCache = null;
      },
      disable: async (scope = 'project') => {
        await api.disableCodexHooks(runtimeBaseUrl, workspaceId, scope);
        scopesCache = null;
      },
    },
    pluginTrust: {
      update: async (entry, trusted) => {
        if (!entry.pluginId || !entry.trustRevision) {
          throw Object.assign(
            new Error('marketplace.settings.plugin_hook_trust_invalid'),
            {
              errorCode: 'marketplace.settings.plugin_hook_trust_invalid',
            },
          );
        }
        await api.updateCodexPluginHookTrust(
          runtimeBaseUrl,
          workspaceId,
          entry.pluginId,
          trusted,
          entry.trustRevision,
        );
        scopesCache = null;
      },
    },
  };
};
