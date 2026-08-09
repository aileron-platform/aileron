import { describe, expect, it } from 'vitest';
import { formatFileSize } from './fileTypeUtils';

describe('File Workbench file size formatting', () => {
  it.each([
    { bytes: 0, expected: '0 B' },
    { bytes: 1, expected: '1 B' },
    { bytes: 1023, expected: '1023 B' },
    { bytes: 1024, expected: '1 KB' },
    { bytes: 1536, expected: '1.5 KB' },
  ])('preserves the display for $bytes bytes', ({ bytes, expected }) => {
    expect(formatFileSize(bytes)).toBe(expected);
  });
});
