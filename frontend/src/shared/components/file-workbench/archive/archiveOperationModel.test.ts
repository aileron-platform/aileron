import { describe, expect, it } from 'vitest';
import { buildArchiveProgressFromStatus } from './archiveOperationModel';

describe('archiveOperationModel', () => {
  it('builds running archive progress while preserving existing download URL', () => {
    expect(
      buildArchiveProgressFromStatus({
        current: {
          operationId: 'archive-1',
          archiveName: 'selection.zip',
          paths: ['/src'],
          status: 'pending',
          progress: 0,
          message: 'Pending',
          downloadUrl: '/previous',
        },
        status: {
          status: 'running',
          progress: 0.5,
          message: 'Running',
          result: null,
        },
      }),
    ).toEqual({
      operationId: 'archive-1',
      archiveName: 'selection.zip',
      paths: ['/src'],
      status: 'running',
      progress: 0.5,
      message: 'Running',
      downloadUrl: '/previous',
      errorMessage: null,
    });
  });

  it('uses completed archive metadata from the runtime status result', () => {
    expect(
      buildArchiveProgressFromStatus({
        current: {
          operationId: 'archive-1',
          archiveName: 'selection.zip',
          paths: ['/src'],
          status: 'running',
          progress: 0.5,
          message: 'Running',
        },
        status: {
          status: 'completed',
          progress: 1,
          message: 'Ready',
          result: {
            archiveName: 'runtime.zip',
            downloadUrl: '/download/runtime.zip',
          },
        },
      }),
    ).toMatchObject({
      archiveName: 'runtime.zip',
      status: 'completed',
      progress: 1,
      message: 'Ready',
      downloadUrl: '/download/runtime.zip',
      errorMessage: null,
    });
  });

  it('uses runtime error text for failed archive progress', () => {
    expect(
      buildArchiveProgressFromStatus({
        current: {
          operationId: 'archive-1',
          archiveName: 'selection.zip',
          paths: ['/src'],
          status: 'running',
          progress: 0.5,
          message: 'Running',
        },
        status: {
          status: 'failed',
          progress: 0.5,
          message: 'Failed',
          error: 'Archive failed',
        },
      }),
    ).toMatchObject({
      status: 'failed',
      message: 'Archive failed',
      errorMessage: 'Archive failed',
    });
  });
});
