import { describe, expect, it } from 'vitest';
import {
  encodeWorkspaceOpenPath,
  parseWorkspaceFileHref,
  parseWorkspaceLocationPathname,
  parseWorkspaceOpenPath,
} from './markdownLinkUtils';

const origin = 'http://localhost:8082';

describe('workspace markdown file links', () => {
  it('parses raw /workspace hrefs and strips line suffixes', () => {
    expect(parseWorkspaceFileHref('/workspace/dir/foo.md:42', origin)).toEqual({
      filePath: '/dir/foo.md',
    });
  });

  it('parses same-origin absolute raw hrefs', () => {
    expect(parseWorkspaceFileHref('http://localhost:8082/workspace/app/page.tsx', origin)).toEqual({
      filePath: '/app/page.tsx',
    });
  });

  it('decodes raw hrefs exactly once', () => {
    expect(parseWorkspaceFileHref('/workspace/%E6%96%87%E4%BB%B6/page.tsx', origin)).toEqual({
      filePath: '/\u6587\u4ef6/page.tsx',
    });
    expect(parseWorkspaceFileHref('/workspace/%252e%252e/app.ts', origin)).toBeNull();
  });

  it('rejects external raw hrefs', () => {
    expect(parseWorkspaceFileHref('https://example.com/workspace/app/page.tsx', origin)).toBeNull();
  });

  it('rejects malformed raw href encoding and encoded slash', () => {
    expect(parseWorkspaceFileHref('/workspace/%E0%A4%A', origin)).toBeNull();
    expect(parseWorkspaceFileHref('/workspace/dir%2Fsecret.ts', origin)).toBeNull();
  });

  it('parses raw browser location pathnames before router splat decoding', () => {
    expect(parseWorkspaceLocationPathname('/workspace/.aileron/canvases/demo/page.tsx')).toEqual({
      filePath: '/.aileron/canvases/demo/page.tsx',
    });
    expect(parseWorkspaceLocationPathname('/workspace/dir%2Fsecret.ts')).toBeNull();
    expect(parseWorkspaceLocationPathname('/workspace/..%2f..%2fsecret.ts')).toBeNull();
    expect(parseWorkspaceLocationPathname('/workspace/%252e%252e/app.ts')).toBeNull();
  });

  it('rejects traversal, NUL, backslash, empty, and oversized paths', () => {
    expect(parseWorkspaceOpenPath('../secret.ts')).toBeNull();
    expect(parseWorkspaceOpenPath('./secret.ts')).toBeNull();
    expect(parseWorkspaceOpenPath('dir/..')).toBeNull();
    expect(parseWorkspaceOpenPath('dir\\secret.ts')).toBeNull();
    expect(parseWorkspaceOpenPath('dir/\u0000secret.ts')).toBeNull();
    expect(parseWorkspaceOpenPath('%2e%2e/app.ts')).toBeNull();
    expect(parseWorkspaceOpenPath('')).toBeNull();
    expect(parseWorkspaceOpenPath(`${'a'.repeat(4097)}.ts`)).toBeNull();
  });

  it('preserves non-ASCII paths after normalization', () => {
    expect(parseWorkspaceOpenPath('\u6587\u4ef6/\u81ea\u6211\u4ecb\u7d39.tsx')).toEqual({
      filePath: '/\u6587\u4ef6/\u81ea\u6211\u4ecb\u7d39.tsx',
    });
  });

  it('encodes normalized paths for open query parameters', () => {
    expect(encodeWorkspaceOpenPath('/\u6587\u4ef6/page.tsx')).toBe('%2F%E6%96%87%E4%BB%B6%2Fpage.tsx');
  });
});
