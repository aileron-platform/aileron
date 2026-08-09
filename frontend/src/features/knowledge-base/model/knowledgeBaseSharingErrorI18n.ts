import { ApiError } from '@/shared/api/apiClient';

type KnowledgeBaseSharingErrorCode =
  | 'KB_SHARE_INVALID_TARGET_TYPE'
  | 'KB_SHARE_TARGET_NOT_FOUND'
  | 'KB_SHARE_DUPLICATE_TARGET'
  | 'KB_SHARE_INVALID_ROLE'
  | 'KB_SHARE_OWNER_TARGET_FORBIDDEN'
  | 'KB_SHARE_FORBIDDEN';

export const KNOWLEDGE_BASE_SHARING_ERROR_I18N_KEYS = {
  KB_SHARE_INVALID_TARGET_TYPE: 'knowledgeBase.sharing.errors.invalidTargetType',
  KB_SHARE_TARGET_NOT_FOUND: 'knowledgeBase.sharing.errors.targetNotFound',
  KB_SHARE_DUPLICATE_TARGET: 'knowledgeBase.sharing.errors.duplicateTarget',
  KB_SHARE_INVALID_ROLE: 'knowledgeBase.sharing.errors.invalidRole',
  KB_SHARE_OWNER_TARGET_FORBIDDEN: 'knowledgeBase.sharing.errors.ownerTargetForbidden',
  KB_SHARE_FORBIDDEN: 'knowledgeBase.sharing.errors.forbidden',
} as const satisfies Record<KnowledgeBaseSharingErrorCode, string>;

const isKnowledgeBaseSharingErrorCode = (
  value: string,
): value is KnowledgeBaseSharingErrorCode => (
  Object.prototype.hasOwnProperty.call(KNOWLEDGE_BASE_SHARING_ERROR_I18N_KEYS, value)
);

export const getKnowledgeBaseSharingErrorI18nKey = (error: unknown): string => {
  if (
    error instanceof ApiError
    && error.errorCode
    && isKnowledgeBaseSharingErrorCode(error.errorCode)
  ) {
    return KNOWLEDGE_BASE_SHARING_ERROR_I18N_KEYS[error.errorCode];
  }
  return 'common.errors.generic';
};
