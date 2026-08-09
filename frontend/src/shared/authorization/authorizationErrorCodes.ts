export const AUTHORIZATION_ERROR_CODES = {
  platformAuthorizationDenied: 'PLATFORM_AUTHORIZATION_DENIED',
  managerSessionRequired: 'MANAGER_SESSION_REQUIRED',
  managerSessionOriginInvalid: 'MANAGER_SESSION_ORIGIN_INVALID',
  managerSessionCsrfInvalid: 'MANAGER_SESSION_CSRF_INVALID',
  platformResourceInvalidRequest: 'PLATFORM_RESOURCE_INVALID_REQUEST',
  platformResourceNotFound: 'PLATFORM_RESOURCE_NOT_FOUND',
  platformResourceOwnerNotFound: 'PLATFORM_RESOURCE_OWNER_NOT_FOUND',
  platformResourceTargetNotAuthorizable: 'PLATFORM_RESOURCE_TARGET_NOT_AUTHORIZABLE',
  platformResourceTargetManagerRequired: 'PLATFORM_RESOURCE_TARGET_MANAGER_REQUIRED',
  platformResourceOwnerUnchanged: 'PLATFORM_RESOURCE_OWNER_UNCHANGED',
  platformResourceOwnerNotificationFailed: 'PLATFORM_RESOURCE_OWNER_NOTIFICATION_FAILED',
  platformResourceAccessRecycleFailed: 'PLATFORM_RESOURCE_ACCESS_RECYCLE_FAILED',
  workspaceAccessDenied: 'WORKSPACE_ACCESS_DENIED',
  workspaceOperationDenied: 'WORKSPACE_OPERATION_DENIED',
  workspaceRuntimeActionForbidden: 'WORKSPACE_RUNTIME_ACTION_FORBIDDEN',
  workspaceDeleteConflict: 'WORKSPACE_DELETE_CONFLICT',
  knowledgeBaseAccessDenied: 'KB_ACCESS_DENIED',
  knowledgeBasePermissionDenied: 'KB_PERMISSION_DENIED',
  knowledgeBaseDeleteAttachmentConflict: 'KB_DELETE_ATTACHMENT_CONFLICT',
  knowledgeBaseDeleteStorageCleanupFailed: 'KB_DELETE_STORAGE_CLEANUP_FAILED',
  resourceDeleteConfirmationMismatch: 'RESOURCE_DELETE_CONFIRMATION_MISMATCH',
} as const;

const WORKSPACE_AUTHORIZATION_DENIAL_CODES: ReadonlySet<string> = new Set([
  AUTHORIZATION_ERROR_CODES.workspaceAccessDenied,
  AUTHORIZATION_ERROR_CODES.workspaceOperationDenied,
  AUTHORIZATION_ERROR_CODES.workspaceRuntimeActionForbidden,
]);

const KNOWLEDGE_BASE_AUTHORIZATION_DENIAL_CODES: ReadonlySet<string> = new Set([
  AUTHORIZATION_ERROR_CODES.knowledgeBaseAccessDenied,
  AUTHORIZATION_ERROR_CODES.knowledgeBasePermissionDenied,
]);

export const isWorkspaceAuthorizationDenialCode = (
  errorCode: unknown,
): boolean => (
  typeof errorCode === 'string'
  && WORKSPACE_AUTHORIZATION_DENIAL_CODES.has(errorCode)
);

export const isKnowledgeBaseAuthorizationDenialCode = (
  errorCode: unknown,
): boolean => (
  typeof errorCode === 'string'
  && KNOWLEDGE_BASE_AUTHORIZATION_DENIAL_CODES.has(errorCode)
);

export const shouldRefreshPlatformAuthorization = (
  errorCode: unknown,
): boolean => (
  errorCode === AUTHORIZATION_ERROR_CODES.platformAuthorizationDenied
  || isWorkspaceAuthorizationDenialCode(errorCode)
  || isKnowledgeBaseAuthorizationDenialCode(errorCode)
);
