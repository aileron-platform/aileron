import { describe, expect, it } from 'vitest';
import {
  classifyMarkdownHref,
  parseWorkspaceFileHref,
  resolveWorkspaceMarkdownPath,
} from './markdownLinkUtils';

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

  describe('parseWorkspaceFileHref', () => {
    const origin = 'http://localhost:8082';

    it('rewrites root-relative /workspace paths to workspace-relative file paths', () => {
      expect(parseWorkspaceFileHref('/workspace/foo.md', origin)).toEqual({
        filePath: '/foo.md',
      });
      expect(parseWorkspaceFileHref('/workspace/dir/file.tsx', origin)).toEqual({
        filePath: '/dir/file.tsx',
      });
    });

    it('strips trailing :line[:column] location suffix', () => {
      expect(parseWorkspaceFileHref('/workspace/foo.md:1', origin)).toEqual({
        filePath: '/foo.md',
      });
      expect(parseWorkspaceFileHref('/workspace/dir/foo.md:42:7', origin)).toEqual({
        filePath: '/dir/foo.md',
      });
    });

    it('strips query and hash before computing the file path', () => {
      expect(parseWorkspaceFileHref('/workspace/foo.md?ref=main', origin)).toEqual({
        filePath: '/foo.md',
      });
      expect(parseWorkspaceFileHref('/workspace/foo.md#section', origin)).toEqual({
        filePath: '/foo.md',
      });
    });

    it('accepts absolute URLs that share the current origin', () => {
      expect(
        parseWorkspaceFileHref('http://localhost:8082/workspace/foo.md:1', origin),
      ).toEqual({ filePath: '/foo.md' });
    });

    it('rejects absolute URLs from a different origin', () => {
      expect(
        parseWorkspaceFileHref('https://example.com/workspace/foo.md', origin),
      ).toBeNull();
    });

    it('rejects paths outside the /workspace prefix', () => {
      expect(parseWorkspaceFileHref('/openspec/foo.md', origin)).toBeNull();
      expect(parseWorkspaceFileHref('foo.md', origin)).toBeNull();
    });

    it('rejects anchors, mailto, javascript, and empty values', () => {
      expect(parseWorkspaceFileHref('#section', origin)).toBeNull();
      expect(parseWorkspaceFileHref('mailto:user@example.com', origin)).toBeNull();
      expect(parseWorkspaceFileHref('javascript:alert(1)', origin)).toBeNull();
      expect(parseWorkspaceFileHref('', origin)).toBeNull();
      expect(parseWorkspaceFileHref(null, origin)).toBeNull();
      expect(parseWorkspaceFileHref(undefined, origin)).toBeNull();
    });

    it('rejects /workspace itself with no file segment', () => {
      expect(parseWorkspaceFileHref('/workspace', origin)).toBeNull();
      expect(parseWorkspaceFileHref('/workspace/', origin)).toBeNull();
    });
  });
});
