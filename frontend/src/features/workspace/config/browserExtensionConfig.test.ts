import { describe, expect, it } from 'vitest';
import { resolveBrowserExtensionId } from './browserExtensionConfig';

describe('resolveBrowserExtensionId', () => {
  it('accepts only a canonical Chrome extension identifier', () => {
    expect(resolveBrowserExtensionId('abcdefghijklmnopabcdefghijklmnop')).toBe(
      'abcdefghijklmnopabcdefghijklmnop'
    );
  });

  it.each([
    undefined,
    '',
    '__VITE_BROWSER_EXTENSION_ID__',
    ' abcdefghijklmnopabcdefghijklmnop',
    'ABCDEFGHIJKLMNOPABCDEFGHIJKLMNOP',
    'qrstuvwxyzqrstuvwxyzqrstuvwxyzqr',
  ])('fails closed for an absent or invalid identifier', (value) => {
    expect(resolveBrowserExtensionId(value)).toBeNull();
  });
});
