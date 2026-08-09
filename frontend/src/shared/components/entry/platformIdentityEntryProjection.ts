import type {
  PlatformIdentityEntryProjection,
  WorkspaceIdentityEntrySource,
} from './workspaceEntryTypes';

export const projectPlatformIdentityEntry = (
  identity: WorkspaceIdentityEntrySource,
): PlatformIdentityEntryProjection => ({
  stages: [
    {
      id: 'identity',
      status: identity.status === 'checking'
        ? 'active'
        : identity.status === 'failed'
          ? 'failed'
          : identity.status === 'authenticated'
            ? 'complete'
            : 'active',
    },
  ],
  activeStage: 'identity',
  titleKey: 'common.entry.title',
  descriptionKey: identity.status === 'failed'
    ? 'common.entry.descriptions.identityFailed'
    : 'common.entry.descriptions.identity',
  reasonCode: identity.reasonCode ?? null,
  actions: identity.status === 'failed' || identity.status === 'unauthenticated'
    ? [{ id: 'login', emphasis: 'primary' }]
    : [],
});
