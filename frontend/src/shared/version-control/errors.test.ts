import { describe, expect, it } from 'vitest';
import {
  getConflictSource,
  getVersionControlErrorMessageKey,
  isHttpStatusError,
  isVersionControlOperationInProgressError,
} from './errors';

const err = (status: number, stale?: boolean) => ({
  status,
  errorCode: 'operation_locked',
  messageKey: 'shared.versionControl.errors.operationLocked',
  stale,
});

describe('getConflictSource', () => {
  it('returns stale when stale is true', () => {
    expect(getConflictSource(err(409, true))).toBe('stale');
  });

  it('returns collision when stale is false', () => {
    expect(getConflictSource(err(409, false))).toBe('collision');
  });

  it('returns null when not a 409 or stale metadata is missing', () => {
    expect(getConflictSource(err(500))).toBeNull();
    expect(getConflictSource(err(409))).toBeNull();
  });
});

describe('isVersionControlOperationInProgressError', () => {
  it('matches the expected 409 error code only', () => {
    expect(isVersionControlOperationInProgressError(err(409), 'operation_locked')).toBe(true);
    expect(isVersionControlOperationInProgressError(err(500), 'operation_locked')).toBe(false);
    expect(isVersionControlOperationInProgressError(err(409), 'OTHER_ERROR')).toBe(false);
  });
});

describe('getVersionControlErrorMessageKey', () => {
  it('returns only a structured messageKey', () => {
    expect(getVersionControlErrorMessageKey(err(409))).toBe('shared.versionControl.errors.operationLocked');
    expect(getVersionControlErrorMessageKey(new Error('backend text'))).toBeNull();
  });

  it('maps a missing Git identity to the shared actionable message', () => {
    expect(getVersionControlErrorMessageKey({
      status: 409,
      errorCode: 'git_identity_missing',
      messageKey: 'git_identity_missing',
    })).toBe('shared.versionControl.errors.gitIdentityMissing');
  });
});

describe('isHttpStatusError', () => {
  it('matches the expected HTTP status only', () => {
    expect(isHttpStatusError(err(403), 403)).toBe(true);
    expect(isHttpStatusError(err(409), 403)).toBe(false);
    expect(isHttpStatusError(null, 403)).toBe(false);
  });
});
