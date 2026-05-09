import { describe, expect, it } from 'vitest';
import { classifyMarkdownHref, resolveWorkspaceMarkdownPath } from './markdownLinkUtils';

describe('markdownLinkUtils', () => {
  it('classifies anchor, external, and internal links', () => {
    expect(classifyMarkdownHref('#section')).toBe('anchor');
    expect(classifyMarkdownHref('https://example.com')).toBe('external');
    expect(classifyMarkdownHref('mailto:test@example.com')).toBe('external');
    expect(classifyMarkdownHref('../../schemas/spec.md')).toBe('internal');
    expect(classifyMarkdownHref('/openspec/specs/api-common/spec.md')).toBe('internal');
  });

  it('resolves OpenSpec relative links from a change design document', () => {
    expect(resolveWorkspaceMarkdownPath(
      '/openspec/changes/parse-policy-excel-file/design.md',
      '../../schemas/spec-driven-api/standards/configuration-standards.md',
    )).toBe('/openspec/schemas/spec-driven-api/standards/configuration-standards.md');
  });

  it('resolves absolute workspace links and strips hash or query suffixes', () => {
    expect(resolveWorkspaceMarkdownPath(
      '/openspec/changes/parse-policy-excel-file/design.md',
      '/openspec/specs/api-common/spec.md#headers',
    )).toBe('/openspec/specs/api-common/spec.md');

    expect(resolveWorkspaceMarkdownPath(
      '/openspec/changes/parse-policy-excel-file/design.md',
      '../proposal.md?view=preview',
    )).toBe('/openspec/changes/proposal.md');
  });
});
