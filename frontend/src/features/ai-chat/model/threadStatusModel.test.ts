import { describe, expect, it } from 'vitest';
import { canRetry, isLocked, isRunning, toMinimalStatus } from './threadStatusModel';

describe('toMinimalStatus', () => {
  it.each([
    ['draft', 'draft'],
    ['queued', 'pending'],
    ['booting', 'active'],
    ['working', 'active'],
    ['stopping', 'finishing'],
    ['complete', 'complete'],
    ['stopped', 'complete'],
    ['canceled', 'complete'],
    ['error', 'error'],
  ] as const)('%s -> %s', (status, expected) => {
    expect(toMinimalStatus(status)).toBe(expected);
  });
});

describe('status predicates', () => {
  it('isRunning covers queued/booting/working/stopping only', () => {
    expect(['queued', 'booting', 'working', 'stopping'].every(isRunning)).toBe(true);
    expect(['draft', 'complete', 'stopped', 'error', 'canceled'].some(isRunning)).toBe(false);
  });

  it('canRetry only on error', () => {
    expect(canRetry('error')).toBe(true);
    expect(canRetry('complete')).toBe(false);
  });

  it('locked whenever not draft', () => {
    expect(isLocked('draft')).toBe(false);
    expect(isLocked('working')).toBe(true);
  });
});
