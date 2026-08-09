import { describe, expect, it } from 'vitest';
import {
  isKnowledgeBaseAuthorizationDenialCode,
  isWorkspaceAuthorizationDenialCode,
  shouldRefreshPlatformAuthorization,
} from './authorizationErrorCodes';

describe('authorizationErrorCodes', () => {
  it.each([
    'WORKSPACE_ACCESS_DENIED',
    'WORKSPACE_OPERATION_DENIED',
    'WORKSPACE_RUNTIME_ACTION_FORBIDDEN',
  ])('recognizes workspace denial code %s', (errorCode) => {
    expect(isWorkspaceAuthorizationDenialCode(errorCode)).toBe(true);
    expect(shouldRefreshPlatformAuthorization(errorCode)).toBe(true);
  });

  it.each([
    'KB_ACCESS_DENIED',
    'KB_PERMISSION_DENIED',
  ])('recognizes knowledge base denial code %s', (errorCode) => {
    expect(isKnowledgeBaseAuthorizationDenialCode(errorCode)).toBe(true);
    expect(shouldRefreshPlatformAuthorization(errorCode)).toBe(true);
  });

  it('refreshes platform authorization for a platform denial', () => {
    expect(
      shouldRefreshPlatformAuthorization('PLATFORM_AUTHORIZATION_DENIED'),
    ).toBe(true);
  });

  it.each([undefined, null, '', 'UNRELATED_ERROR'])(
    'ignores unrelated code %s',
    (errorCode) => {
      expect(isWorkspaceAuthorizationDenialCode(errorCode)).toBe(false);
      expect(isKnowledgeBaseAuthorizationDenialCode(errorCode)).toBe(false);
      expect(shouldRefreshPlatformAuthorization(errorCode)).toBe(false);
    },
  );
});
