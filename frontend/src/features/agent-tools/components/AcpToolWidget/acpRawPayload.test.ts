import { describe, expect, it } from 'vitest';

import { extractAcpErrorText, extractAcpOutputText } from './acpRawPayload';

describe('acpRawPayload', () => {
  it('treats plain string output as normal content, not error', () => {
    const output = '-rw-r--r-- 1 developer developer 1821 May  3 12:45 test.html';

    expect(extractAcpOutputText(output)).toBe(output);
    expect(extractAcpErrorText(output)).toBe('');
  });

  it('extracts structured error fields from object output', () => {
    expect(
      extractAcpErrorText({
        error_message: 'command failed',
      })
    ).toBe('command failed');
  });
});
