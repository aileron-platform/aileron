import type { VersionControlConflictSource } from './types';

type ApiErrorLike = {
  status?: unknown;
  errorCode?: unknown;
  messageKey?: unknown;
  stale?: unknown;
  canForceUnlock?: unknown;
};

const isApiErrorLike = (error: unknown): error is ApiErrorLike => (
  typeof error === 'object' && error !== null
);

const VERSION_CONTROL_ERROR_MESSAGE_KEYS: Record<string, string> = {
  git_identity_missing: 'shared.versionControl.errors.gitIdentityMissing',
};

export const isVersionControlOperationInProgressError = (
  error: unknown,
  expectedCode: string,
): boolean => (
  isApiErrorLike(error)
  && error.status === 409
  && error.errorCode === expectedCode
);

export const isHttpStatusError = (
  error: unknown,
  expectedStatus: number,
): boolean => (
  isApiErrorLike(error)
  && error.status === expectedStatus
);

export const getConflictSource = (error: unknown): VersionControlConflictSource | null => {
  if (!isApiErrorLike(error) || error.status !== 409) return null;
  if (error.stale === true) return 'stale';
  if (error.stale === false) return 'collision';
  return null;
};

export const getVersionControlErrorMessageKey = (error: unknown): string | null => {
  if (!isApiErrorLike(error)) return null;
  if (typeof error.errorCode === 'string') {
    const mappedKey = VERSION_CONTROL_ERROR_MESSAGE_KEYS[error.errorCode];
    if (mappedKey) return mappedKey;
  }
  return typeof error.messageKey === 'string' ? error.messageKey : null;
};
