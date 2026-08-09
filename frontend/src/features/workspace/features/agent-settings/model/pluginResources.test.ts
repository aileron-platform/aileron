import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import {
  buildPluginDetailHref,
  buildPluginResourceQueryKey,
  buildPluginResourceSettingsHref,
  getCodexPluginControlErrorKey,
  invalidateMarketplaceUserScopeSettingsQueries,
  invalidateProviderResourceQueries,
  isProviderResourceQuery,
  resolvePluginResourceFilter,
} from './pluginResources';

describe('pluginResources model', () => {
  it('keeps generation and plugin filter in resource query identity', () => {
    const first = buildPluginResourceQueryKey({
      provider: 'codex',
      resource: 'hooks',
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'workspace-1',
      providerResourceGeneration: 7,
      scope: 'plugin',
      pluginId: 'review@official',
    });
    const nextGeneration = buildPluginResourceQueryKey({
      provider: 'codex',
      resource: 'hooks',
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'workspace-1',
      providerResourceGeneration: 8,
      scope: 'plugin',
      pluginId: 'review@official',
    });
    const nextFilter = buildPluginResourceQueryKey({
      provider: 'codex',
      resource: 'hooks',
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'workspace-1',
      providerResourceGeneration: 7,
      scope: 'plugin',
      pluginId: 'build@official',
    });
    const allScopes = buildPluginResourceQueryKey({
      provider: 'codex',
      resource: 'hooks',
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'workspace-1',
      providerResourceGeneration: 7,
      scope: null,
      pluginId: null,
    });
    const allPluginsInPluginScope = buildPluginResourceQueryKey({
      provider: 'codex',
      resource: 'hooks',
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'workspace-1',
      providerResourceGeneration: 7,
      scope: 'plugin',
      pluginId: null,
    });

    expect(nextGeneration).not.toEqual(first);
    expect(nextFilter).not.toEqual(first);
    expect(allPluginsInPluginScope).not.toEqual(allScopes);
    expect(isProviderResourceQuery(
      first,
      'codex',
      'workspace-1',
    )).toBe(true);
    expect(isProviderResourceQuery(
      first,
      'claude-code',
      'workspace-1',
    )).toBe(false);
  });

  it('only applies plugin identity when plugin scope is explicit', () => {
    expect(resolvePluginResourceFilter(
      new URLSearchParams('scope=plugin&pluginId=review%40official'),
    )).toEqual({
      scope: 'plugin',
      pluginId: 'review@official',
    });
    expect(resolvePluginResourceFilter(
      new URLSearchParams('pluginId=review%40official'),
    )).toEqual({
      scope: null,
      pluginId: null,
    });
  });

  it('invalidates plugin resources and one-shot user-scope copy resources independently', async () => {
    const pluginClient = new QueryClient();
    const pluginRoot = [
      'provider-resource',
      'codex',
      'workspace-1',
      'runtime',
      'plugins',
    ];
    const nestedPluginResource = [
      'document-resource',
      'provider-resource',
      'codex',
      'workspace-1',
      'runtime',
      'settings',
      'hooks',
    ];
    const userScopePrompt = ['document-resource', 'prompts', 'codex'];
    pluginClient.setQueryData(pluginRoot, []);
    pluginClient.setQueryData(nestedPluginResource, []);
    pluginClient.setQueryData(userScopePrompt, []);

    await invalidateProviderResourceQueries(
      pluginClient,
      'codex',
      'workspace-1',
    );

    expect(pluginClient.getQueryState(pluginRoot)?.isInvalidated).toBe(true);
    expect(
      pluginClient.getQueryState(nestedPluginResource)?.isInvalidated,
    ).toBe(true);
    expect(
      pluginClient.getQueryState(userScopePrompt)?.isInvalidated,
    ).toBe(false);

    const userCopyClient = new QueryClient();
    const userScopeAgentsMd = [
      'single-document',
      'agents-md',
      'codex',
      'user',
    ];
    const userScopeSubagents = ['document-resource', 'subagents', 'codex'];
    const agentSettingsCollection = [
      'agent-settings',
      'http://runtime.test',
      'workspace-1',
      'codex',
      'skills',
      'all',
      'collection',
    ];
    const otherWorkspaceAgentSettings = [
      'agent-settings',
      'http://runtime.test',
      'workspace-2',
      'codex',
      'skills',
      'all',
      'collection',
    ];
    const otherProvider = ['document-resource', 'slash-commands', 'claude'];
    userCopyClient.setQueryData(pluginRoot, []);
    userCopyClient.setQueryData(userScopePrompt, []);
    userCopyClient.setQueryData(userScopeAgentsMd, []);
    userCopyClient.setQueryData(userScopeSubagents, []);
    userCopyClient.setQueryData(agentSettingsCollection, []);
    userCopyClient.setQueryData(otherWorkspaceAgentSettings, []);
    userCopyClient.setQueryData(otherProvider, []);

    await invalidateMarketplaceUserScopeSettingsQueries(
      userCopyClient,
      'codex',
      'workspace-1',
    );

    expect(userCopyClient.getQueryState(pluginRoot)?.isInvalidated).toBe(true);
    expect(
      userCopyClient.getQueryState(userScopePrompt)?.isInvalidated,
    ).toBe(true);
    expect(
      userCopyClient.getQueryState(userScopeAgentsMd)?.isInvalidated,
    ).toBe(true);
    expect(
      userCopyClient.getQueryState(userScopeSubagents)?.isInvalidated,
    ).toBe(true);
    expect(
      userCopyClient.getQueryState(agentSettingsCollection)?.isInvalidated,
    ).toBe(true);
    expect(
      userCopyClient.getQueryState(otherWorkspaceAgentSettings)?.isInvalidated,
    ).toBe(false);
    expect(
      userCopyClient.getQueryState(otherProvider)?.isInvalidated,
    ).toBe(false);
  });

  it('builds bidirectional settings and plugin detail deep links', () => {
    expect(buildPluginResourceSettingsHref({
      workspaceId: 'workspace 1',
      provider: 'codex',
      resource: 'hooks',
      pluginId: 'review@official',
    })).toBe(
      '/workspaces/workspace 1/codex/hooks?scope=plugin&pluginId=review%40official',
    );
    expect(buildPluginDetailHref({
      workspaceId: 'workspace 1',
      provider: 'codex',
      pluginId: 'review@official',
      resource: 'hooks',
    })).toBe(
      '/workspaces/workspace 1/codex/plugins?pluginId=review%40official&resource=hooks',
    );
  });

  it('maps Codex plugin control error codes without exposing raw messages', () => {
    expect(getCodexPluginControlErrorKey('mcp-policy', {
      errorCode: 'REVISION_CONFLICT',
      message: 'sensitive runtime detail',
    })).toBe(
      'workspace.agentSettings.pluginResources.controlErrors.revisionConflict',
    );
    expect(getCodexPluginControlErrorKey('mcp-policy', {
      errorCode: 'marketplace.settings.plugin_resource_not_found',
    })).toBe(
      'workspace.agentSettings.pluginResources.controlErrors.notFound',
    );
    expect(getCodexPluginControlErrorKey('mcp-policy', {
      errorCode: 'marketplace.settings.plugin_mcp_policy_invalid',
    })).toBe(
      'workspace.agentSettings.pluginResources.controlErrors.invalidMcpPolicy',
    );
    expect(getCodexPluginControlErrorKey('hook-trust', {
      errorCode: 'marketplace.settings.plugin_hook_trust_invalid',
    })).toBe(
      'workspace.agentSettings.pluginResources.controlErrors.invalidHookTrust',
    );
    expect(getCodexPluginControlErrorKey('hook-trust', {
      errorCode: 'marketplace.settings.plugin_hook_trust_not_supported',
    })).toBe(
      'workspace.agentSettings.pluginResources.controlErrors.hookTrustNotSupported',
    );
    expect(getCodexPluginControlErrorKey('mcp-policy', {
      errorCode: 'marketplace.settings.plugin_scope_not_supported',
    })).toBe(
      'workspace.agentSettings.pluginResources.controlErrors.scopeNotSupported',
    );
    expect(getCodexPluginControlErrorKey('mcp-policy', {
      errorCode: 'UNKNOWN',
      message: 'must not be shown',
    })).toBe(
      'workspace.agentSettings.pluginResources.controlErrors.unknown',
    );
  });
});
