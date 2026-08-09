import { describe, expect, it } from 'vitest';
import { isDepthTruncatedDirectory, sortNodes, sortTreeNodes } from './fileTreeModel';
import type { FileTreeNode } from '../types';

describe('file tree model sorting', () => {
  it('sorts directories first and files by extension then name', () => {
    const nodes: FileTreeNode[] = [
      { id: 'z-ts', name: 'zeta.ts', path: '/zeta.ts', type: 'file' },
      { id: 'b-dir', name: 'beta', path: '/beta', type: 'directory' },
      { id: 'a-md', name: 'alpha.md', path: '/alpha.md', type: 'file' },
      { id: 'a-dir', name: 'alpha', path: '/alpha', type: 'directory' },
      { id: 'b-md', name: 'beta.md', path: '/beta.md', type: 'file' },
      { id: 'readme', name: 'README', path: '/README', type: 'file' },
      { id: 'a-ts', name: 'alpha.ts', path: '/alpha.ts', type: 'file' },
    ];

    expect(sortNodes(nodes).map((node) => node.name)).toEqual([
      'alpha',
      'beta',
      'README',
      'alpha.md',
      'beta.md',
      'alpha.ts',
      'zeta.ts',
    ]);
  });

  it('sorts child nodes recursively by file extension', () => {
    const nodes: FileTreeNode[] = [
      {
        id: 'src',
        name: 'src',
        path: '/src',
        type: 'directory',
        children: [
          { id: 'src/b-ts', name: 'b.ts', path: '/src/b.ts', type: 'file' },
          { id: 'src/a-json', name: 'a.json', path: '/src/a.json', type: 'file' },
          { id: 'src/a-ts', name: 'a.ts', path: '/src/a.ts', type: 'file' },
        ],
      },
    ];

    expect(sortTreeNodes(nodes)[0]?.children?.map((node) => node.name)).toEqual([
      'a.json',
      'a.ts',
      'b.ts',
    ]);
  });
});

describe('isDepthTruncatedDirectory', () => {
  it('returns true for a directory with empty children and hasChildren true', () => {
    const node: FileTreeNode = {
      id: '/a',
      name: 'a',
      path: '/a',
      type: 'directory',
      hasChildren: true,
      children: [],
    };
    expect(isDepthTruncatedDirectory(node)).toBe(true);
  });

  it('returns false for a directory with loaded children', () => {
    const node: FileTreeNode = {
      id: '/a',
      name: 'a',
      path: '/a',
      type: 'directory',
      hasChildren: true,
      children: [
        { id: '/a/b.ts', name: 'b.ts', path: '/a/b.ts', type: 'file' },
      ],
    };
    expect(isDepthTruncatedDirectory(node)).toBe(false);
  });

  it('returns false for a directory that is truly empty (hasChildren false)', () => {
    const node: FileTreeNode = {
      id: '/a',
      name: 'a',
      path: '/a',
      type: 'directory',
      hasChildren: false,
      children: [],
    };
    expect(isDepthTruncatedDirectory(node)).toBe(false);
  });

  it('returns false when children is undefined (both hasChildren true and false)', () => {
    const truncatedHint: FileTreeNode = {
      id: '/a',
      name: 'a',
      path: '/a',
      type: 'directory',
      hasChildren: true,
    };
    const noChildHint: FileTreeNode = {
      id: '/a',
      name: 'a',
      path: '/a',
      type: 'directory',
      hasChildren: false,
    };
    expect(isDepthTruncatedDirectory(truncatedHint)).toBe(false);
    expect(isDepthTruncatedDirectory(noChildHint)).toBe(false);
  });

  it('returns false for file nodes even if children is somehow an empty array', () => {
    const node: FileTreeNode = {
      id: '/a.ts',
      name: 'a.ts',
      path: '/a.ts',
      type: 'file',
      hasChildren: true,
      children: [],
    };
    expect(isDepthTruncatedDirectory(node)).toBe(false);
  });
});
