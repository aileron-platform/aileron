import { ApiError } from '@/shared/api/apiClient';

type UserManagementErrorCode =
  | 'USER_ADMIN_INVALID_REQUEST'
  | 'USER_ADMIN_FORBIDDEN'
  | 'USER_ADMIN_USER_NOT_FOUND'
  | 'USER_ADMIN_INVALID_PAGE_REQUEST'
  | 'USER_ADMIN_INVALID_ROLE'
  | 'USER_ADMIN_ROLE_PROVISIONING_REQUIRED'
  | 'USER_ADMIN_ROLE_STATE_INVALID'
  | 'USER_ADMIN_LAST_ADMIN_FORBIDDEN'
  | 'USER_ADMIN_SELF_DEMOTE_FORBIDDEN'
  | 'USER_ADMIN_LOCAL_SHADOW_SYNC_FAILED'
  | 'USER_ADMIN_IDENTITY_SYNC_FAILED'
  | 'USER_ADMIN_IDENTITY_UNAVAILABLE'
  | 'USER_RECONCILIATION_SCAN_INCOMPLETE'
  | 'USER_RECONCILIATION_LOOKUP_FAILED'
  | 'USER_IDENTITY_FRESHNESS_EXPIRED'
  | 'KB_GROUP_ADMIN_INVALID_REQUEST'
  | 'KB_GROUP_ADMIN_DUPLICATE_NAME'
  | 'KB_GROUP_ADMIN_NOT_FOUND'
  | 'KB_GROUP_ADMIN_MEMBER_NOT_FOUND'
  | 'KB_GROUP_ADMIN_MEMBER_NOT_AUTHORIZABLE'
  | 'KB_GROUP_ADMIN_INVALID_PAGE_REQUEST';

export const USER_MANAGEMENT_ERROR_I18N_KEYS = {
  USER_ADMIN_INVALID_REQUEST: 'userManagement.errors.invalidRequest',
  USER_ADMIN_FORBIDDEN: 'userManagement.errors.forbidden',
  USER_ADMIN_USER_NOT_FOUND: 'userManagement.errors.userNotFound',
  USER_ADMIN_INVALID_PAGE_REQUEST: 'userManagement.errors.invalidPageRequest',
  USER_ADMIN_INVALID_ROLE: 'userManagement.errors.invalidRole',
  USER_ADMIN_ROLE_PROVISIONING_REQUIRED: 'userManagement.errors.roleProvisioningRequired',
  USER_ADMIN_ROLE_STATE_INVALID: 'userManagement.errors.roleStateInvalid',
  USER_ADMIN_LAST_ADMIN_FORBIDDEN: 'userManagement.errors.lastAdminForbidden',
  USER_ADMIN_SELF_DEMOTE_FORBIDDEN: 'userManagement.errors.selfDemoteForbidden',
  USER_ADMIN_LOCAL_SHADOW_SYNC_FAILED: 'userManagement.errors.localShadowSyncFailed',
  USER_ADMIN_IDENTITY_SYNC_FAILED: 'userManagement.errors.identitySyncFailed',
  USER_ADMIN_IDENTITY_UNAVAILABLE: 'userManagement.errors.identityUnavailable',
  USER_RECONCILIATION_SCAN_INCOMPLETE: 'userManagement.errors.reconciliationFailed',
  USER_RECONCILIATION_LOOKUP_FAILED: 'userManagement.errors.reconciliationFailed',
  USER_IDENTITY_FRESHNESS_EXPIRED: 'userManagement.errors.identityFreshnessExpired',
  KB_GROUP_ADMIN_INVALID_REQUEST: 'userManagement.errors.groupInvalidRequest',
  KB_GROUP_ADMIN_DUPLICATE_NAME: 'userManagement.errors.groupDuplicateName',
  KB_GROUP_ADMIN_NOT_FOUND: 'userManagement.errors.groupNotFound',
  KB_GROUP_ADMIN_MEMBER_NOT_FOUND: 'userManagement.errors.groupMemberNotFound',
  KB_GROUP_ADMIN_MEMBER_NOT_AUTHORIZABLE: 'userManagement.errors.groupMemberNotAuthorizable',
  KB_GROUP_ADMIN_INVALID_PAGE_REQUEST: 'userManagement.errors.groupInvalidPageRequest',
} as const satisfies Record<UserManagementErrorCode, string>;

const isUserManagementErrorCode = (value: string): value is UserManagementErrorCode => (
  Object.prototype.hasOwnProperty.call(USER_MANAGEMENT_ERROR_I18N_KEYS, value)
);

export const getUserManagementErrorI18nKey = (error: unknown): string => {
  if (error instanceof ApiError && error.errorCode && isUserManagementErrorCode(error.errorCode)) {
    return USER_MANAGEMENT_ERROR_I18N_KEYS[error.errorCode];
  }
  return 'common.errors.generic';
};

export const getUserManagementErrorCodeI18nKey = (errorCode: string): string => (
  isUserManagementErrorCode(errorCode)
    ? USER_MANAGEMENT_ERROR_I18N_KEYS[errorCode]
    : 'common.errors.generic'
);
