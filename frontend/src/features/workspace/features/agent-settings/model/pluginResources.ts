import { ROUTES } from '@/shared/constants/routes';
import type { QueryClient, QueryKey } from '@tanstack/react-query';

export type PluginResourceProvider = 'claude-code' | 'codex';
export type PluginSettingsResourceKind =
  | 'hooks'
  | 'mcp'
  | 'output-styles'
  | 'skills'
  | 'slash-commands'
  | 'subagents';

export interface PluginResourceFilter {
  scope: 'plugin' | null;
  pluginId: string | null;
}

export const resolvePluginResourceFilter = (
  searchParams: URLSearchParams,
): PluginResourceFilter => {
  const pluginScopeSelected = searchParams.get('scope') === 'plugin';
  return {
    scope: pluginScopeSelected ? 'plugin' : null,
    pluginId: pluginScopeSelected
      ? searchParams.get('pluginId')?.trim() || null
      : null,
  };
};

export const buildPluginResourceQueryKey = ({
  provider,
  resource,
  runtimeBaseUrl,
  workspaceId,
  providerResourceGeneration,
  scope,
  pluginId,
}: {
  provider: PluginResourceProvider;
  resource: PluginSettingsResourceKind;
  runtimeBaseUrl: string;
  workspaceId: string;
  providerResourceGeneration: number;
  scope: 'plugin' | null;
  pluginId: string | null;
}) => [
  ...buildProviderResourceQueryRoot(provider, workspaceId),
  runtimeBaseUrl,
  'generation',
  providerResourceGeneration,
  'settings',
  resource,
  'scope',
  scope ?? 'all',
  'filter',
  pluginId ?? 'all',
] as const;

export const buildProviderResourceQueryRoot = (
  provider: PluginResourceProvider,
  workspaceId: string,
) => ['provider-resource', provider, workspaceId] as const;

export const buildProviderPluginListQueryKey = ({
  provider,
  runtimeBaseUrl,
  workspaceId,
}: {
  provider: PluginResourceProvider;
  runtimeBaseUrl: string;
  workspaceId: string;
}) => [
  ...buildProviderResourceQueryRoot(provider, workspaceId),
  runtimeBaseUrl,
  'plugins',
] as const;

export const buildProviderPluginDetailQueryKey = ({
  provider,
  runtimeBaseUrl,
  workspaceId,
  providerResourceGeneration,
  pluginId,
}: {
  provider: PluginResourceProvider;
  runtimeBaseUrl: string;
  workspaceId: string;
  providerResourceGeneration: number;
  pluginId: string | null;
}) => [
  ...buildProviderResourceQueryRoot(provider, workspaceId),
  runtimeBaseUrl,
  'generation',
  providerResourceGeneration,
  'plugin-detail',
  pluginId ?? 'none',
] as const;

export const isProviderResourceQuery = (
  queryKey: QueryKey,
  provider: PluginResourceProvider,
  workspaceId: string,
): boolean => {
  const root = buildProviderResourceQueryRoot(provider, workspaceId);
  return queryKey.some((_, startIndex) => (
    root.every((value, offset) => queryKey[startIndex + offset] === value)
  ));
};

export const invalidateProviderResourceQueries = async (
  queryClient: QueryClient,
  provider: PluginResourceProvider,
  workspaceId: string,
): Promise<void> => {
  await queryClient.invalidateQueries({
    predicate: query => isProviderResourceQuery(
      query.queryKey,
      provider,
      workspaceId,
    ),
  });
};

const providerQueryAliases = (
  provider: PluginResourceProvider,
): readonly string[] => (
  provider === 'claude-code' ? ['claude-code', 'claude'] : ['codex']
);

const hasProviderAlias = (
  queryKey: QueryKey,
  provider: PluginResourceProvider,
): boolean => {
  const aliases = providerQueryAliases(provider);
  return queryKey.some(value => (
    typeof value === 'string' && aliases.includes(value)
  ));
};

export const isMarketplaceProviderSettingsQuery = (
  queryKey: QueryKey,
  provider: PluginResourceProvider,
  workspaceId: string,
): boolean => {
  if (isProviderResourceQuery(queryKey, provider, workspaceId)) {
    return true;
  }

  const root = queryKey[0];
  if (root === 'agent-settings') {
    return queryKey.includes(provider)
      && queryKey.includes(workspaceId);
  }
  if (root === 'agent-file-tree') {
    return true;
  }
  if (
    root === 'single-document'
    || root === 'document-resource'
    || root === 'document-resource-content'
    || root === 'raw-settings'
  ) {
    return hasProviderAlias(queryKey, provider);
  }
  if (root === 'hooks') {
    return hasProviderAlias(queryKey, provider)
      && queryKey.includes(workspaceId);
  }
  if (root === 'agent-settings-mcp') {
    return hasProviderAlias(queryKey, provider)
      && queryKey.includes(workspaceId);
  }
  if (root === 'agent-document-sidebar') {
    return hasProviderAlias(queryKey, provider)
      && queryKey.includes(workspaceId);
  }
  if (root === 'codex-document-sidebar') {
    return provider === 'codex' && queryKey.includes(workspaceId);
  }
  if (root === 'agent-plugin-skills') {
    return hasProviderAlias(queryKey, provider)
      && queryKey.includes(workspaceId);
  }
  if (
    root === 'codex-hooks-workflow'
    || root === 'codex-skills-scope-availability'
  ) {
    return provider === 'codex' && queryKey.includes(workspaceId);
  }
  return false;
};

export const invalidateMarketplaceUserScopeSettingsQueries = async (
  queryClient: QueryClient,
  provider: PluginResourceProvider,
  workspaceId: string,
): Promise<void> => {
  await queryClient.invalidateQueries({
    predicate: query => isMarketplaceProviderSettingsQuery(
      query.queryKey,
      provider,
      workspaceId,
    ),
  });
};

export const buildPluginResourceSettingsHref = ({
  workspaceId,
  provider,
  resource,
  pluginId,
}: {
  workspaceId: string;
  provider: PluginResourceProvider;
  resource: PluginSettingsResourceKind;
  pluginId: string;
}): string => {
  const query = new URLSearchParams({ scope: 'plugin', pluginId });
  return `${ROUTES.workspace.agentTool(workspaceId, provider, resource)}?${query.toString()}`;
};

export const buildPluginDetailHref = ({
  workspaceId,
  provider,
  pluginId,
  resource,
}: {
  workspaceId: string;
  provider: PluginResourceProvider;
  pluginId: string;
  resource?: PluginSettingsResourceKind;
}): string => {
  const query = new URLSearchParams({ pluginId });
  if (resource) {
    query.set('resource', resource);
  }
  return `${ROUTES.workspace.agentTool(workspaceId, provider, 'plugins')}?${query.toString()}`;
};

export type CodexPluginControlKind = 'mcp-policy' | 'hook-trust';

const CODEX_PLUGIN_CONTROL_ERROR_KEYS: Record<string, string> = {
  REVISION_CONFLICT:
    'workspace.agentSettings.pluginResources.controlErrors.revisionConflict',
  'marketplace.settings.plugin_resource_not_found':
    'workspace.agentSettings.pluginResources.controlErrors.notFound',
  'marketplace.settings.plugin_scope_not_supported':
    'workspace.agentSettings.pluginResources.controlErrors.scopeNotSupported',
  'marketplace.settings.plugin_provenance_missing':
    'workspace.agentSettings.pluginResources.controlErrors.provenanceMissing',
};

const CODEX_PLUGIN_CONTROL_KIND_ERROR_KEYS: Record<
  CodexPluginControlKind,
  Record<string, string>
> = {
  'mcp-policy': {
    'marketplace.settings.plugin_mcp_policy_invalid':
      'workspace.agentSettings.pluginResources.controlErrors.invalidMcpPolicy',
  },
  'hook-trust': {
    'marketplace.settings.plugin_hook_trust_invalid':
      'workspace.agentSettings.pluginResources.controlErrors.invalidHookTrust',
    'marketplace.settings.plugin_hook_trust_not_supported':
      'workspace.agentSettings.pluginResources.controlErrors.hookTrustNotSupported',
  },
};

export const getCodexPluginControlErrorCode = (
  error: unknown,
): string | null => {
  if (!error || typeof error !== 'object') {
    return null;
  }
  const errorCode = (error as { errorCode?: unknown }).errorCode;
  return typeof errorCode === 'string' ? errorCode : null;
};

export const getCodexPluginControlErrorKey = (
  kind: CodexPluginControlKind,
  error: unknown,
): string => {
  const errorCode = getCodexPluginControlErrorCode(error);
  return (
    (errorCode && CODEX_PLUGIN_CONTROL_KIND_ERROR_KEYS[kind][errorCode])
    || (errorCode && CODEX_PLUGIN_CONTROL_ERROR_KEYS[errorCode])
    || 'workspace.agentSettings.pluginResources.controlErrors.unknown'
  );
};
