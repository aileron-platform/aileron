import { describe, expect, it } from 'vitest';
import { isPathWritable } from './pathWritability';

describe('isPathWritable', () => {
  it.each([
    ['', false],
    ['/', false],
    ['raw', true],
    ['/raw', true],
    ['raw/', true],
    ['raw/sources/a.md', true],
    ['wiki', false],
    ['wiki/index.md', false],
    ['.aileron-kb/reviews.json', false],
  ])('returns %s for %s', (path, expected) => {
    expect(isPathWritable(path)).toBe(expected);
  });
});
