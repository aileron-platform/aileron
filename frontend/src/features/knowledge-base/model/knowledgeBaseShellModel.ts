import { ROUTES } from '@/shared/constants/routes';

export type KnowledgeBaseFeatureId =
  | 'files'
  | 'version-control'
  | 'sharing'
  | 'workspaces'
  | 'settings';

export type KnowledgeBaseVersionControlSubView = 'changes' | 'history';

interface KnowledgeBaseActiveNav {
  featureId: KnowledgeBaseFeatureId | null;
  subItemId: KnowledgeBaseVersionControlSubView | null;
}

const FEATURE_IDS: readonly KnowledgeBaseFeatureId[] = [
  'files',
  'version-control',
  'sharing',
  'workspaces',
  'settings',
];

const DEFAULT_NAV: KnowledgeBaseActiveNav = { featureId: 'files', subItemId: null };

export const resolveKnowledgeBaseActiveNav = (pathname: string): KnowledgeBaseActiveNav => {
  const match = pathname.match(/\/knowledge-bases\/[^/]+\/([^/]+)(?:\/([^/]+))?/);
  if (!match) {
    return DEFAULT_NAV;
  }
  const featureId = FEATURE_IDS.find((id) => id === match[1]);
  if (!featureId) {
    return { featureId: null, subItemId: null };
  }
  if (featureId === 'version-control') {
    return { featureId, subItemId: match[2] === 'history' ? 'history' : 'changes' };
  }
  return { featureId, subItemId: null };
};

export const buildKnowledgeBaseNavPath = (
  knowledgeBaseId: string,
  featureId: KnowledgeBaseFeatureId,
  subItemId?: KnowledgeBaseVersionControlSubView,
): string => {
  if (featureId === 'version-control') {
    return subItemId === 'history'
      ? ROUTES.knowledgeBase.versionControlHistory(knowledgeBaseId)
      : ROUTES.knowledgeBase.versionControlChanges(knowledgeBaseId);
  }

  if (featureId === 'files') {
    return ROUTES.knowledgeBase.files(knowledgeBaseId);
  }

  if (featureId === 'sharing') {
    return ROUTES.knowledgeBase.sharing(knowledgeBaseId);
  }

  if (featureId === 'workspaces') {
    return ROUTES.knowledgeBase.workspaces(knowledgeBaseId);
  }

  return ROUTES.knowledgeBase.settings(knowledgeBaseId);
};
