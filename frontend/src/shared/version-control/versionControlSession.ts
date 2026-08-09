import { useMemo } from 'react';
import {
  createKnowledgeBaseChangesCapability,
  createMarketplaceChangesCapability,
} from './versionControlChangesCapability';
import {
  createKnowledgeBaseHistoryCapability,
  createMarketplaceHistoryCapability,
} from './versionControlHistoryCapability';
import {
  createKnowledgeBaseRemoteCapability,
  createMarketplaceRemoteCapability,
} from './versionControlRemoteCapability';
import { createVersionControlCore } from './versionControlSessionCore';

interface KnowledgeBaseVersionControlSessionOptions {
  knowledgeBaseId: string;
  isGitRepo: boolean;
}

interface MarketplaceVersionControlSessionOptions {
  isGitRepo: boolean;
}

export const createKnowledgeBaseVersionControlSession = ({
  knowledgeBaseId,
  isGitRepo,
}: KnowledgeBaseVersionControlSessionOptions) => {
  const core = createVersionControlCore({
    baseUrl: '/api/v1',
    scope: 'knowledge-bases',
    id: knowledgeBaseId,
    gitQueriesEnabled: isGitRepo,
  });

  return {
    changes: createKnowledgeBaseChangesCapability(core),
    history: createKnowledgeBaseHistoryCapability(core),
    remote: createKnowledgeBaseRemoteCapability(core),
    refresh: core.refresh,
  };
};

export const createMarketplaceVersionControlSession = ({
  isGitRepo,
}: MarketplaceVersionControlSessionOptions) => {
  const core = createVersionControlCore({
    baseUrl: '/api/v1',
    scope: 'marketplace',
    gitQueriesEnabled: isGitRepo,
  });

  return {
    changes: createMarketplaceChangesCapability(core),
    history: createMarketplaceHistoryCapability(core),
    remote: createMarketplaceRemoteCapability(core),
    refresh: core.refresh,
  };
};

export const useKnowledgeBaseVersionControlSession = (
  options: KnowledgeBaseVersionControlSessionOptions,
) => {
  const { isGitRepo, knowledgeBaseId } = options;
  return useMemo(
    () => createKnowledgeBaseVersionControlSession({
      isGitRepo,
      knowledgeBaseId,
    }),
    [isGitRepo, knowledgeBaseId],
  );
};

export const useMarketplaceVersionControlSession = (
  options: MarketplaceVersionControlSessionOptions,
) => {
  const { isGitRepo } = options;
  return useMemo(
    () => createMarketplaceVersionControlSession({ isGitRepo }),
    [isGitRepo],
  );
};

export type KnowledgeBaseVersionControlSession =
  ReturnType<typeof createKnowledgeBaseVersionControlSession>;
export type MarketplaceVersionControlSession =
  ReturnType<typeof createMarketplaceVersionControlSession>;
export type { VersionControlCapabilityGroup } from './versionControlSessionCore';
