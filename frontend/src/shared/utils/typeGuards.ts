/**
 * Shared runtime type guards.
 */

/**
 * Narrow an unknown value to a plain object record.
 * Note: arrays are objects too, so callers that need to exclude arrays must
 * check `Array.isArray` before calling this guard.
 */
export const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;
