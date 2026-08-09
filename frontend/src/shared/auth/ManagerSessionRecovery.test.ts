import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ManagerSessionRecovery } from './ManagerSessionRecovery';

describe('ManagerSessionRecovery', () => {
  const navigate = vi.fn();

  beforeEach(() => {
    navigate.mockReset();
  });

  it('gives the first Manager Session failure redirect ownership and preserves the return target', () => {
    const recovery = new ManagerSessionRecovery(navigate);

    expect(recovery.handle(
      401,
      'MANAGER_SESSION_REQUIRED',
      '/workspaces/workspace-1/files?tab=changes#diff',
    )).toBe(true);
    expect(recovery.handle(
      401,
      'MANAGER_SESSION_REQUIRED',
      '/workspaces/workspace-2/files',
    )).toBe(false);

    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith(
      '/api/v1/oauth2/login?return_path=%2Fworkspaces%2Fworkspace-1%2Ffiles%3Ftab%3Dchanges%23diff',
    );
  });

  it('does not release redirect ownership after unrelated successful responses', () => {
    const recovery = new ManagerSessionRecovery(navigate);

    expect(recovery.handle(401, 'MANAGER_SESSION_REQUIRED', '/workspaces')).toBe(true);
    expect(recovery.handle(200, undefined, '/workspaces')).toBe(false);
    expect(recovery.handle(401, 'MANAGER_SESSION_REQUIRED', '/marketplace')).toBe(false);

    expect(navigate).toHaveBeenCalledTimes(1);
  });

  it('allows a new redirect only after an explicit bootstrap reset', () => {
    const recovery = new ManagerSessionRecovery(navigate);

    recovery.handle(401, 'MANAGER_SESSION_REQUIRED', '/workspaces');
    recovery.reset();

    expect(recovery.handle(401, 'MANAGER_SESSION_REQUIRED', '/marketplace')).toBe(true);
    expect(navigate).toHaveBeenCalledTimes(2);
  });

  it.each([
    [403, 'PLATFORM_AUTHORIZATION_DENIED'],
    [403, 'MANAGER_SESSION_ORIGIN_INVALID'],
    [403, 'MANAGER_SESSION_CSRF_INVALID'],
    [401, 'WORKSPACE_RUNTIME_ACCESS_DENIED'],
    [401, 'TERMINAL_EXECUTION_GRANT_REQUIRED'],
    [401, 'BROWSER_ACCESS_CREDENTIAL_REQUIRED'],
    [503, 'WORKSPACE_RUNTIME_UNAVAILABLE'],
  ])('does not redirect for HTTP %s with %s', (status, errorCode) => {
    const recovery = new ManagerSessionRecovery(navigate);

    expect(recovery.handle(status, errorCode, '/workspaces')).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });

  it.each([
    '/login',
    '/api/v1/oauth2/login',
    '/api/v1/oauth2/callback?code=opaque',
    '/api/v1/oauth2/logout',
  ])('does not redirect while already inside an authentication route: %s', (returnPath) => {
    const recovery = new ManagerSessionRecovery(navigate);

    expect(recovery.handle(401, 'MANAGER_SESSION_REQUIRED', returnPath)).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });

  it.each(['https://attacker.example/steal', '//attacker.example/steal', 'workspaces'])(
    'falls back to the platform root for an unsafe return target: %s',
    (returnPath) => {
      const recovery = new ManagerSessionRecovery(navigate);

      expect(recovery.handle(401, 'MANAGER_SESSION_REQUIRED', returnPath)).toBe(true);
      expect(navigate).toHaveBeenCalledWith(
        '/api/v1/oauth2/login?return_path=%2F',
      );
    },
  );
});
