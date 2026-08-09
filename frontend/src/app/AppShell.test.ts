import { describe, expect, it } from 'vitest';

import { ApiError } from '@/shared/api/apiClient';
import { shouldRetryQuery } from './AppShell';

describe('AppShell query retry policy', () => {
  it.each([400, 401, 403, 404, 409, 423])('does not retry stable HTTP %s responses', (status) => {
    expect(shouldRetryQuery(0, new ApiError('request failed', status))).toBe(false);
  });

  it.each([408, 429, 500])('retries transient HTTP %s responses once', (status) => {
    const error = new ApiError('request failed', status);

    expect(shouldRetryQuery(0, error)).toBe(true);
    expect(shouldRetryQuery(1, error)).toBe(false);
  });

  it('retries other failures once', () => {
    const error = new Error('temporary failure');

    expect(shouldRetryQuery(0, error)).toBe(true);
    expect(shouldRetryQuery(1, error)).toBe(false);
  });
});
