import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: class MockApiClient {
    constructor(_options?: unknown) {}

    get = getMock;
  },
}));

import { promptInvocationApi } from './promptInvocationApi';

describe('promptInvocationApi', () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it('loads the tool-specific Catalog with one Runtime request', async () => {
    getMock.mockResolvedValue({
      workspaceId: 'ws-1',
      agenticTool: 'codex',
      completeness: 'complete',
      revision: 'revision-1',
      availableScopes: ['project', 'user', 'plugin'],
      sourceErrors: [],
      items: [
        {
          id: 'codex:skill:project:review/SKILL.md',
          sourceKey: 'review/SKILL.md',
          fileName: 'SKILL.md',
          kind: 'skill',
          scope: 'project',
          displayName: 'review',
          category: 'project',
          description: 'Review the current changes',
          invocation: '$review',
          tags: [],
        },
      ],
    });

    const catalog = await promptInvocationApi.list(
      'http://runtime.test',
      'ws-1',
      'codex',
    );

    expect(getMock).toHaveBeenCalledTimes(1);
    expect(getMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/cli-settings/codex/prompt-invocations',
    );
    expect(catalog.items[0]?.invocation).toBe('$review');
  });
});
