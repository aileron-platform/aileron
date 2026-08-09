import { describe, expect, it } from 'vitest';
import { parseCodexPluginToolPolicies } from './CodexPluginMcpPolicyControl';

describe('parseCodexPluginToolPolicies', () => {
  it('normalizes valid per-tool approval policy JSON', () => {
    expect(parseCodexPluginToolPolicies(JSON.stringify({
      search: { approvalMode: 'prompt' },
      write: { approvalMode: null },
    }))).toEqual({
      search: { approvalMode: 'prompt' },
      write: { approvalMode: null },
    });
  });

  it('rejects unsupported approval modes', () => {
    expect(() => parseCodexPluginToolPolicies(JSON.stringify({
      search: { approvalMode: 'allow' },
    }))).toThrow('INVALID_TOOL_POLICY');
  });
});
