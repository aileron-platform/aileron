import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createMarketplaceVersionControlSession } from './versionControlSession';

const { getMock, postMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => ({
    get: getMock,
    post: postMock,
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  })),
  ApiError: class ApiError extends Error {
    status = 500;
  },
}));

const createHarness = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  return {
    queryClient,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  };
};

describe('version control LFS capability', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
  });

  it('uses the identical LFS and cancellation suffixes exposed by every product adapter', async () => {
    getMock.mockResolvedValue({ patterns: ['*.zip'] });
    postMock.mockImplementation((path: string) => {
      if (path.endsWith('/lfs/preview')) {
        return Promise.resolve({
          matchedTotal: 1,
          totalSize: 12,
          pathSample: ['asset.zip'],
        });
      }
      return Promise.resolve({
        commandId: 'command',
        headSha: 'abc',
        branch: 'main',
        affectedTotal: 1,
        skippedTotal: 0,
        output: '',
      });
    });
    const session = createMarketplaceVersionControlSession({ isGitRepo: true });
    const { wrapper } = createHarness();
    const result = renderHook(() => ({
      patterns: session.remote.useLfsPatternsQuery(),
      update: session.remote.useUpdateLfsPatternsMutation(),
      preview: session.remote.usePreviewLfsSnapshotMutation(),
      convert: session.remote.useConvertLfsSnapshotMutation(),
      cancel: session.remote.useCancelOperationMutation(),
    }), { wrapper });

    await waitFor(() => expect(result.result.current.patterns.data).toEqual({
      patterns: ['*.zip'],
    }));
    expect(getMock).toHaveBeenCalledWith('/marketplace/version-control/lfs');

    await act(async () => {
      await result.result.current.update.mutateAsync({ patterns: ['*.zip', '*.pdf'] });
      await result.result.current.preview.mutateAsync({ patterns: ['*.zip'] });
      await result.result.current.convert.mutateAsync({ paths: ['asset.zip'] });
      await result.result.current.cancel.mutateAsync();
    });

    expect(postMock).toHaveBeenNthCalledWith(
      1,
      '/marketplace/version-control/lfs',
      { patterns: ['*.zip', '*.pdf'] },
    );
    expect(postMock).toHaveBeenNthCalledWith(
      2,
      '/marketplace/version-control/lfs/preview',
      { patterns: ['*.zip'] },
    );
    expect(postMock).toHaveBeenNthCalledWith(
      3,
      '/marketplace/version-control/lfs/convert',
      { paths: ['asset.zip'] },
    );
    expect(postMock).toHaveBeenNthCalledWith(
      4,
      '/marketplace/version-control/operation/cancel',
      undefined,
    );
  });
});
