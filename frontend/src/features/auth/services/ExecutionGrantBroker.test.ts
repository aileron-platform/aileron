import { beforeEach, describe, expect, it, vi } from 'vitest';
import { executionGrantBroker } from './ExecutionGrantBroker';
import { managerSessionService } from './ManagerSessionService';
import { managerSessionRecovery } from '@/shared/auth/ManagerSessionRecovery';

describe('ExecutionGrantBroker', () => {
  beforeEach(() => {
    managerSessionService.clear();
    vi.restoreAllMocks();
  });

  it('checks availability before reusing a grant for the same runtime generation', async () => {
    vi.spyOn(managerSessionService, 'bootstrap').mockImplementation(async () => {
      Object.defineProperty(managerSessionService, 'csrfToken', {
        configurable: true,
        value: 'csrf-1',
        writable: true,
      });
      return null;
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        runtimeInstanceId: 'runtime-1',
        runtimeAccessDesiredRevision: 7,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        grant: 'grant-1', expiresIn: 60,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        runtimeInstanceId: 'runtime-1',
        runtimeAccessDesiredRevision: 7,
      }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    const first = await executionGrantBroker.getGrant(
      'https://terminal.example.test', 'workspace-terminal', 'terminal', 'workspace-1',
    );
    const second = await executionGrantBroker.getGrant(
      'https://terminal.example.test', 'workspace-terminal', 'terminal', 'workspace-1',
    );

    expect(first).toBe('grant-1');
    expect(second).toBe('grant-1');
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('does not reuse a grant after runtime instance or access revision changes', async () => {
    Object.defineProperty(managerSessionService, 'csrfToken', {
      configurable: true,
      value: 'csrf-1',
      writable: true,
    });
    const availability = (runtimeInstanceId: string, runtimeAccessDesiredRevision: number) => (
      new Response(JSON.stringify({ runtimeInstanceId, runtimeAccessDesiredRevision }), { status: 200 })
    );
    const grant = (value: string) => new Response(JSON.stringify({
      grant: value,
      expiresIn: 60,
    }), { status: 200 });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(availability('runtime-1', 7))
      .mockResolvedValueOnce(grant('grant-1'))
      .mockResolvedValueOnce(availability('runtime-2', 7))
      .mockResolvedValueOnce(grant('grant-2'))
      .mockResolvedValueOnce(availability('runtime-2', 8))
      .mockResolvedValueOnce(grant('grant-3'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(executionGrantBroker.getGrant(
      'https://runtime-generation.test', 'workspace-runtime', 'runtime_read', 'workspace-generation',
    )).resolves.toBe('grant-1');
    await expect(executionGrantBroker.getGrant(
      'https://runtime-generation.test', 'workspace-runtime', 'runtime_read', 'workspace-generation',
    )).resolves.toBe('grant-2');
    await expect(executionGrantBroker.getGrant(
      'https://runtime-generation.test', 'workspace-runtime', 'runtime_read', 'workspace-generation',
    )).resolves.toBe('grant-3');

    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it('routes Manager API session failures through the process-wide recovery seam', async () => {
    const recovery = vi.spyOn(managerSessionRecovery, 'handle').mockReturnValue(true);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        errorCode: 'MANAGER_SESSION_REQUIRED',
        message: 'auth.manager_session.required',
        details: {},
      },
    }), { status: 401 })));

    await expect(executionGrantBroker.getGrant(
      'https://runtime-auth.test', 'workspace-runtime', 'runtime_read', 'workspace-auth',
    )).rejects.toMatchObject({
      status: 401,
      errorCode: 'MANAGER_SESSION_REQUIRED',
    });
    expect(recovery).toHaveBeenCalledWith(
      401,
      'MANAGER_SESSION_REQUIRED',
      expect.any(String),
    );
  });
});
