import { beforeEach, describe, expect, it, vi } from 'vitest';

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    post: postMock,
  },
}));

import { workspaceBrowserExtensionApi } from './workspaceBrowserExtensionApi';

describe('workspaceBrowserExtensionApi', () => {
  beforeEach(() => {
    postMock.mockReset();
  });

  it('creates a no-body pairing assertion request for the encoded workspace', async () => {
    const response = {
      assertion: 'header.payload.signature',
      runtimeInstanceId: 'runtime-instance-123',
    };
    postMock.mockResolvedValue(response);

    await expect(
      workspaceBrowserExtensionApi.createPairingAssertion('workspace/one')
    ).resolves.toEqual(response);

    expect(postMock).toHaveBeenCalledWith(
      '/workspaces/workspace%2Fone/browser-extension-pairing-assertions'
    );
  });
});
