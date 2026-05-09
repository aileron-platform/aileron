import { describe, expect, it } from 'vitest';
import { sortNodes, sortTreeNodes } from './fileTreeUtils';
import type { FileTreeNode } from '../types';

describe('fileTreeUtils sorting', () => {
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
