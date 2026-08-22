import { describe, expect, it } from 'vitest';
import {
  ApiError,
  type ApiErrorOperationStatus,
} from '@/shared/api/apiClient';
import { shouldRetryVersionControlQuery } from './versionControlSessionCore';

const operationStatus = (
  overrides: Partial<ApiErrorOperationStatus> = {},
): ApiErrorOperationStatus => ({
  isActive: true,
  operation: 'changes.numstat',
  actorDisplayName: null,
  startedAt: '2026-08-12T08:15:30+00:00',
  blockingScope: 'working_tree_target',
  stale: false,
  retryable: true,
  progressCurrent: 0,
  progressTotal: 0,
  phase: '',
  cancellable: false,
  cancelRequested: false,
  ...overrides,
});

const conflict = (status?: ApiErrorOperationStatus): ApiError => Object.assign(
  new ApiError('Version control operation already in progress', 409),
  { operationStatus: status },
);

describe('shouldRetryVersionControlQuery', () => {
  it.each([
    [0, true],
    [1, true],
    [2, false],
    [3, false],
  ])('bounds an explicitly retryable active 409 at failure count %s', (failureCount, expected) => {
    expect(shouldRetryVersionControlQuery(
      failureCount,
      conflict(operationStatus()),
    )).toBe(expected);
  });

  it.each([
    ['non-retryable status', conflict(operationStatus({ retryable: false }))],
    ['inactive status', conflict(operationStatus({ isActive: false }))],
    ['metadata-less status', conflict()],
    ['message-only collision', new ApiError('retryable active lock collision', 409)],
  ])('does not retry a 409 with %s', (_label, error) => {
    expect(shouldRetryVersionControlQuery(0, error)).toBe(false);
  });

  it.each([400, 401, 403, 404, 408, 422, 429])(
    'does not retry another HTTP %s client error',
    status => {
      const error = Object.assign(new ApiError('client error', status), {
        operationStatus: operationStatus(),
      });
      expect(shouldRetryVersionControlQuery(0, error)).toBe(false);
    },
  );

  it.each([
    ['ApiError 500', new ApiError('server error', 500)],
    ['network error', new TypeError('network unavailable')],
  ])('preserves the bounded retry policy for %s', (_label, error) => {
    expect(shouldRetryVersionControlQuery(0, error)).toBe(true);
    expect(shouldRetryVersionControlQuery(1, error)).toBe(true);
    expect(shouldRetryVersionControlQuery(2, error)).toBe(false);
  });

  it('does not trust a non-boolean retryable value', () => {
    const error = Object.assign(conflict(), {
      operationStatus: {
        ...operationStatus(),
        retryable: 'true',
      },
    });

    expect(shouldRetryVersionControlQuery(0, error)).toBe(false);
  });
});
