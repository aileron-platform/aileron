import { describe, expect, it } from 'vitest';
import { formatDocumentContentSize } from './documentContentModel';

describe('formatDocumentContentSize', () => {
  it('formats empty content as 1KB', () => {
    expect(formatDocumentContentSize('')).toBe('1KB');
  });

  it('rounds 1200 characters up to 2KB', () => {
    expect(formatDocumentContentSize('x'.repeat(1200))).toBe('2KB');
  });
});
