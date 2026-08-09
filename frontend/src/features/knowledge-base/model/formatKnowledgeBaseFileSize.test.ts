import { describe, expect, it } from 'vitest';
import { formatKnowledgeBaseFileSize } from './formatKnowledgeBaseFileSize';

describe('Knowledge Base file size formatting', () => {
  it.each([
    { bytes: 0, expected: '0 Bytes' },
    { bytes: 1, expected: '1 Bytes' },
    { bytes: 1023, expected: '1023 Bytes' },
    { bytes: 1024, expected: '1 KB' },
    { bytes: 1536, expected: '1.5 KB' },
  ])('preserves the display for $bytes bytes', ({ bytes, expected }) => {
    expect(formatKnowledgeBaseFileSize(bytes)).toBe(expected);
  });
});
