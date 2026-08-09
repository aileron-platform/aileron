import type { AgentFileCollection } from '../model/documents';
import type { AgentFileTreeVisibleScope } from '../adapters/agentFileTreeDataAdapter';

export interface AgentSettingsCollectionIdentity {
  runtimeBaseUrl: string;
  workspaceId: string;
  provider: string;
  capability: AgentFileCollection | string;
  scope: AgentFileTreeVisibleScope | string;
}

export const agentSettingsQueryKeys = {
  root: ['agent-settings'] as const,
  provider: (
    runtimeBaseUrl: string,
    workspaceId: string,
    provider: string,
  ) => [
    ...agentSettingsQueryKeys.root,
    runtimeBaseUrl,
    workspaceId,
    provider,
  ] as const,
  collection: (identity: AgentSettingsCollectionIdentity) => [
    ...agentSettingsQueryKeys.provider(
      identity.runtimeBaseUrl,
      identity.workspaceId,
      identity.provider,
    ),
    identity.capability,
    identity.scope,
    'collection',
  ] as const,
  content: (
    identity: AgentSettingsCollectionIdentity,
    path: string,
    revision?: string | null,
  ) => [
    ...agentSettingsQueryKeys.provider(
      identity.runtimeBaseUrl,
      identity.workspaceId,
      identity.provider,
    ),
    identity.capability,
    identity.scope,
    'content',
    path,
    revision ?? null,
  ] as const,
  documentCollectionIdentity: (
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    provider: string,
    ...variant: readonly string[]
  ) => [
    runtimeBaseUrl,
    workspaceId,
    resource,
    provider,
    ...variant,
  ] as const,
  documentCollection: (
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    provider: string,
    ...variant: readonly string[]
  ) => [
    'document-resource',
    ...agentSettingsQueryKeys.documentCollectionIdentity(
      runtimeBaseUrl,
      workspaceId,
      resource,
      provider,
      ...variant,
    ),
  ] as const,
};
