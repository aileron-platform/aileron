import { describe, expect, it, vi, beforeEach } from 'vitest';

const { postMock, getMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  getMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    post: postMock,
    get: getMock,
  },
}));

import { workspaceWizardService } from './workspaceWizardService';

describe('workspaceWizardService.createWorkspace', () => {
  beforeEach(() => {
    postMock.mockReset();
    getMock.mockReset();
  });

  it('includes target namespace in create payload when needed', async () => {
    postMock.mockResolvedValue({ id: 'ws-123' });

    const result = await workspaceWizardService.createWorkspace({
      name: 'K8s Workspace',
      description: 'test',
      gitUrl: 'https://github.com/example/repo.git',
      branch: 'main',
      runtime: 'universal',
      targetNamespace: 'workspace-system',
      setupScript: 'echo hello',
      envVars: [{ key: 'NODE_ENV', value: 'development' }],
      cliType: 'claude-code',
    });

    expect(result).toEqual({ workspaceId: 'ws-123' });
    expect(postMock).toHaveBeenCalledWith('/workspaces/', {
      name: 'K8s Workspace',
      description: 'test',
      gitUrl: 'https://github.com/example/repo.git',
      runtime: 'universal',
      targetNamespace: 'workspace-system',
      setupScript: 'echo hello',
      envVars: [{ key: 'NODE_ENV', value: 'development' }],
      branch: 'main',
      cliType: 'claude-code',
    });
  });

  it('omits port mappings when none are provided', async () => {
    postMock.mockResolvedValue({ id: 'ws-456' });

    await workspaceWizardService.createWorkspace({
      name: 'K8s Workspace',
      description: 'test',
      gitUrl: 'https://github.com/example/repo.git',
      branch: 'main',
      runtime: 'universal',
      targetNamespace: 'workspace-system',
      setupScript: 'echo hello',
      envVars: [{ key: 'NODE_ENV', value: 'development' }],
      cliType: 'claude-code',
    });

    expect(postMock).toHaveBeenCalledWith('/workspaces/', {
      name: 'K8s Workspace',
      description: 'test',
      gitUrl: 'https://github.com/example/repo.git',
      runtime: 'universal',
      targetNamespace: 'workspace-system',
      setupScript: 'echo hello',
      envVars: [{ key: 'NODE_ENV', value: 'development' }],
      branch: 'main',
      cliType: 'claude-code',
    });
  });
});
