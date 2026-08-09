import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  createAgentSettingsApi,
  type ClaudePluginsResponse,
  type CodexPluginsResponse,
} from '../../api/agentSettingsApi';
import {
  buildProviderPluginListQueryKey,
  type PluginResourceProvider,
} from '../../model/pluginResources';

interface UseProviderPluginListQueryOptions<
  Provider extends PluginResourceProvider,
> {
  provider: Provider;
  runtimeBaseUrl: string;
  workspaceId: string;
  enabled: boolean;
}

type ProviderPluginListResponse<
  Provider extends PluginResourceProvider,
> = Provider extends 'claude-code'
  ? ClaudePluginsResponse
  : CodexPluginsResponse;

export const useProviderPluginListQuery = <
  Provider extends PluginResourceProvider,
>({
  provider,
  runtimeBaseUrl,
  workspaceId,
  enabled,
}: UseProviderPluginListQueryOptions<Provider>) => {
  const api = useMemo(() => createAgentSettingsApi(provider), [provider]);

  return useQuery<ProviderPluginListResponse<Provider>>({
    queryKey: buildProviderPluginListQueryKey({
      provider,
      runtimeBaseUrl,
      workspaceId,
    }),
    queryFn: async (): Promise<ProviderPluginListResponse<Provider>> => (
      provider === 'claude-code'
        ? await api.listClaudePlugins(runtimeBaseUrl, workspaceId)
        : await api.listCodexPlugins(runtimeBaseUrl, workspaceId)
    ) as ProviderPluginListResponse<Provider>,
    enabled,
  });
};
