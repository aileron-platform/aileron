import { beforeEach, describe, expect, it, vi } from 'vitest';
import { managerSessionRecovery } from '@/shared/auth/ManagerSessionRecovery';
import { managerSessionService } from './ManagerSessionService';

describe('ManagerSessionService', () => {
  beforeEach(() => {
    managerSessionService.clear();
    vi.restoreAllMocks();
  });

  it('bootstraps opaque-cookie session and keeps only CSRF in memory', async () => {
    const resetRecovery = vi.spyOn(managerSessionRecovery, 'reset');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      user: {
        id: 'user-1', username: 'nova', email: null, display_name: null,
        platform_role: 'member', allowed_operations: [],
      },
      csrf_token: 'csrf-1',
      absolute_expires_at: '2026-08-06T08:00:00Z',
    }), { status: 200 })));

    await expect(managerSessionService.bootstrap()).resolves.toMatchObject({
      user: { id: 'user-1' },
    });
    expect(managerSessionService.getCsrfToken()).toBe('csrf-1');
    expect(fetch).toHaveBeenCalledWith('/api/v1/oauth2/session', expect.objectContaining({
      credentials: 'include',
    }));
    expect(sessionStorage.length).toBe(0);
    expect(resetRecovery).toHaveBeenCalledTimes(1);
  });

  it('clears in-memory state on unauthorized bootstrap', async () => {
    const recover = vi.spyOn(managerSessionRecovery, 'handle');
    const resetRecovery = vi.spyOn(managerSessionRecovery, 'reset');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(managerSessionService.bootstrap()).resolves.toBeNull();
    expect(managerSessionService.getCsrfToken()).toBeNull();
    expect(recover).not.toHaveBeenCalled();
    expect(resetRecovery).not.toHaveBeenCalled();
  });

  it('starts process-wide recovery for an expired Manager Session bootstrap', async () => {
    const recover = vi.spyOn(managerSessionRecovery, 'handle').mockReturnValue(true);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        errorCode: 'MANAGER_SESSION_REQUIRED',
        message: 'auth.manager_session.required',
        details: {},
      },
    }), { status: 401 })));

    await expect(managerSessionService.bootstrap()).resolves.toBeNull();
    expect(recover).toHaveBeenCalledWith(
      401,
      'MANAGER_SESSION_REQUIRED',
      `${window.location.pathname}${window.location.search}${window.location.hash}`,
    );
  });

  it('preserves the platform authorization denial classification from bootstrap', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      errorCode: 'PLATFORM_AUTHORIZATION_DENIED',
    }), { status: 403 })));

    await expect(managerSessionService.bootstrap()).rejects.toThrow(
      'PLATFORM_AUTHORIZATION_DENIED',
    );
  });
});
