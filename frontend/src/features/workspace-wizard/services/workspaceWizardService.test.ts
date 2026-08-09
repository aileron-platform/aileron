import { describe, expect, it, vi, beforeEach } from 'vitest';

const { postMock, putMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  putMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    post: postMock,
    put: putMock,
  },
}));

import { workspaceWizardService } from './workspaceWizardService';

describe('workspaceWizardService.createWorkspace', () => {
  beforeEach(() => {
    postMock.mockReset();
    putMock.mockReset().mockResolvedValue({});
  });

  it('starts a new lifecycle job for a failed workspace', async () => {
    postMock.mockResolvedValue({
      workspaceId: 'workspace/1',
      status: 'queued',
      jobId: 'job-2',
    });

    const result = await workspaceWizardService.startWorkspace('workspace/1');

    expect(result).toEqual({
      workspaceId: 'workspace/1',
      status: 'queued',
      jobId: 'job-2',
    });
    expect(postMock).toHaveBeenCalledWith('/workspaces/workspace%2F1/start');
  });

  it('maps workspace creation fields to the API payload', async () => {
    postMock.mockResolvedValue({ id: 'ws-123' });

    const result = await workspaceWizardService.createWorkspace({
      name: 'K8s Workspace',
      description: 'test',
      runtime: 'universal',
      setupScript: 'echo hello',
      envVars: [{ key: 'NODE_ENV', value: 'development' }],
      agenticTools: ['claude-code'],
    });

    expect(result).toEqual({ workspaceId: 'ws-123' });
    expect(postMock).toHaveBeenCalledWith('/workspaces', {
      name: 'K8s Workspace',
      description: 'test',
      runtime: 'universal',
      agenticTools: ['claude-code'],
    });
    expect(putMock).toHaveBeenCalledWith(
      '/workspaces/ws-123/sensitive-settings',
      {
        setupScript: 'echo hello',
        envVars: [{ key: 'NODE_ENV', value: 'development' }],
      },
    );
  });

  it('uses the default runtime when runtime selection is empty', async () => {
    postMock.mockResolvedValue({ id: 'ws-789' });

    await workspaceWizardService.createWorkspace({
      name: 'Default Runtime Workspace',
      description: 'test',
      runtime: '',
      setupScript: '',
      envVars: [],
      agenticTools: ['claude-code'],
    });

    expect(postMock).toHaveBeenCalledWith('/workspaces', {
      name: 'Default Runtime Workspace',
      description: 'test',
      runtime: 'universal',
      agenticTools: ['claude-code'],
    });
    expect(putMock).not.toHaveBeenCalled();
  });
});
