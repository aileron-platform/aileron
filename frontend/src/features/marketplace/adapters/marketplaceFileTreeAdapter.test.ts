import { describe, expect, it } from 'vitest';
import {
  createMarketplacePackageFileTree,
  marketplaceFileContentsFromTree,
  marketplacePackageFilesFromTree,
  marketplacePackageFilesToFileTreeNodes,
} from './marketplaceFileTreeAdapter';
import type { MarketplacePackageFile } from '@/shared/types/marketplace';

const textFile = (path: string, content = path): MarketplacePackageFile => ({
  path,
  content,
  binary: false,
  mimeType: 'text/plain',
  size: content.length,
});

describe('marketplaceFileTreeAdapter', () => {
  it('converts a flat package file list into hierarchical file tree nodes', () => {
    const nodes = marketplacePackageFilesToFileTreeNodes([
      textFile('a/b.md'),
      textFile('a/c.md'),
      textFile('d.md'),
    ]);

    expect(nodes).toEqual([
      expect.objectContaining({
        name: 'a',
        path: 'a',
        type: 'directory',
        children: [
          expect.objectContaining({ name: 'b.md', path: 'a/b.md', type: 'file' }),
          expect.objectContaining({ name: 'c.md', path: 'a/c.md', type: 'file' }),
        ],
      }),
      expect.objectContaining({ name: 'd.md', path: 'd.md', type: 'file' }),
    ]);
  });

  it('returns an empty tree for an empty list', () => {
    expect(marketplacePackageFilesToFileTreeNodes([])).toEqual([]);
  });

  it('deduplicates duplicate paths', () => {
    const nodes = marketplacePackageFilesToFileTreeNodes([
      textFile('a/b.md', 'first'),
      textFile('a/b.md', 'second'),
    ]);

    expect(nodes[0]?.children).toHaveLength(1);
    expect(marketplaceFileContentsFromTree(nodes)).toEqual({ 'a/b.md': 'first' });
  });

  it('preserves deeply nested package paths under a package root', () => {
    const nodes = marketplacePackageFilesToFileTreeNodes(
      [textFile('skills/review/SKILL.md', '# Skill')],
      { rootPath: '/codex/plugins/demo-plugin', scope: 'plugin' },
    );

    expect(nodes).toEqual([
      expect.objectContaining({
        name: 'skills',
        path: '/codex/plugins/demo-plugin/skills',
        children: [
          expect.objectContaining({
            name: 'review',
            path: '/codex/plugins/demo-plugin/skills/review',
            children: [
              expect.objectContaining({
                name: 'SKILL.md',
                path: '/codex/plugins/demo-plugin/skills/review/SKILL.md',
                metadata: expect.objectContaining({ content: '# Skill' }),
              }),
            ],
          }),
        ],
      }),
    ]);
  });

  it('converts file tree nodes back into package files', () => {
    const nodes = marketplacePackageFilesToFileTreeNodes(
      [textFile('README.md', '# Demo')],
      { rootPath: '/codex/plugins/demo-plugin', scope: 'plugin' },
    );

    expect(marketplacePackageFilesFromTree(nodes, '/codex/plugins/demo-plugin', {
      '/codex/plugins/demo-plugin/README.md': '# Updated',
    })).toEqual([
      expect.objectContaining({
        path: 'README.md',
        content: '# Updated',
      }),
    ]);
  });

  it('keeps the package root node when creating a package file tree with files', () => {
    const nodes = createMarketplacePackageFileTree({
      provider: 'codex',
      packageRoot: 'codex/plugins/demo-plugin',
      displayName: 'Demo plugin',
      packageFiles: [textFile('README.md', '# Demo')],
    });

    expect(nodes).toEqual([
      expect.objectContaining({
        name: 'demo-plugin',
        path: '/codex/plugins/demo-plugin',
        type: 'directory',
        children: [
          expect.objectContaining({
            name: 'README.md',
            path: '/codex/plugins/demo-plugin/README.md',
          }),
        ],
      }),
    ]);
  });
});
