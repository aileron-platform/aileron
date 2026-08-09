import { describe, expect, it } from 'vitest';
import type { FileTreeNode } from '@/shared/components/file-workbench';
import {
  buildChildPath,
  ensureScopedPath,
  getContextParentPath,
  isManagedFileRootPath,
  marketplaceContextMenuFeatures,
  renamePath,
  sortEntries,
  toFileTreeNode,
  toResourceEntries,
  type ResourceEntry,
} from './marketplaceFileResourceModel';

const createNode = (path: string, type: FileTreeNode['type']): FileTreeNode => ({
  id: path,
  path,
  name: path.split('/').at(-1) ?? path,
  type,
});

describe('marketplaceFileResourceModel', () => {
  describe('managed file roots', () => {
    it.each([
      ['commands', true],
      ['/skills/example/SKILL.md', true],
      ['.mcp.json', true],
      ['AGENTS.md/nested', true],
      ['documents/readme.md', false],
      ['', false],
    ])('classifies %j as managed=%s', (path, expected) => {
      expect(isManagedFileRootPath(path)).toBe(expected);
    });
  });

  describe('resource entries', () => {
    const entries: Parameters<typeof toResourceEntries>[1] = [
      { path: 'skills', name: 'skills', type: 'directory' },
      { path: 'skills/reviewer/SKILL.md', name: 'SKILL.md', type: 'file' },
      { path: 'skills-extra/file.md', name: 'file.md', type: 'file' },
      { path: '.mcp.json', name: '.mcp.json', type: 'file' },
    ];

    it.each([
      {
        resourceType: 'files' as const,
        expectedPaths: ['skills', 'skills/reviewer/SKILL.md', 'skills-extra/file.md', '.mcp.json'],
      },
      {
        resourceType: 'skills' as const,
        expectedPaths: ['skills', 'skills/reviewer/SKILL.md'],
      },
    ])('filters $resourceType entries without changing their order', ({ resourceType, expectedPaths }) => {
      const result = toResourceEntries(resourceType, entries);

      expect(result.map((entry) => entry.path)).toEqual(expectedPaths);
      expect(result.map((entry) => entry.isDirectory)).toEqual(
        expectedPaths.map((path) => path === 'skills'),
      );
    });

    it('sorts directories before files and leaves the input unchanged', () => {
      const unsorted: ResourceEntry[] = [
        { path: 'z-file.md', name: 'z-file.md', type: 'file', isDirectory: false },
        { path: 'z-directory', name: 'z-directory', type: 'directory', isDirectory: true },
        { path: 'a-file.md', name: 'a-file.md', type: 'file', isDirectory: false },
        { path: 'a-directory', name: 'a-directory', type: 'directory', isDirectory: true },
      ];

      expect(sortEntries(unsorted).map((entry) => entry.path)).toEqual([
        'a-directory',
        'z-directory',
        'a-file.md',
        'z-file.md',
      ]);
      expect(unsorted.map((entry) => entry.path)).toEqual([
        'z-file.md',
        'z-directory',
        'a-file.md',
        'a-directory',
      ]);
    });
  });

  describe('resource paths', () => {
    it.each([
      ['skills' as const, ' reviewer/SKILL.md/ ', 'skills/reviewer/SKILL.md'],
      ['skills' as const, '/skills/reviewer/SKILL.md/', 'skills/reviewer/SKILL.md'],
      ['files' as const, '/documents/readme.md/', 'documents/readme.md'],
      ['files' as const, ' / ', ''],
    ])('scopes %s path %j to %j', (resourceType, input, expected) => {
      expect(ensureScopedPath(resourceType, input)).toBe(expected);
    });

    it.each([
      ['skills' as const, '', 'reviewer/SKILL.md', 'skills/reviewer/SKILL.md'],
      ['skills' as const, 'skills/reviewer', 'SKILL.md', 'skills/reviewer/SKILL.md'],
      ['files' as const, 'documents', 'readme.md', 'documents/readme.md'],
    ])('builds a child path for %s resources', (resourceType, parentPath, name, expected) => {
      expect(buildChildPath(resourceType, parentPath, name)).toBe(expected);
    });

    it.each([
      [null, ''],
      [createNode('documents', 'directory'), 'documents'],
      [createNode('documents/readme.md', 'file'), 'documents'],
      [createNode('README.md', 'file'), ''],
    ])('resolves the context parent path', (node, expected) => {
      expect(getContextParentPath(node)).toBe(expected);
    });

    it.each([
      ['documents/readme.md', 'guide.md', 'documents/guide.md'],
      ['/README.md', 'AGENTS.md', 'AGENTS.md'],
    ])('renames %j to %j', (path, nextName, expected) => {
      expect(renamePath(path, nextName)).toBe(expected);
    });
  });

  describe('file tree presentation model', () => {
    it.each([
      {
        resourceType: 'files' as const,
        entry: {
          path: 'skills/reviewer/SKILL.md',
          name: 'SKILL.md',
          type: 'file' as const,
          isDirectory: false,
        },
        writable: false,
      },
      {
        resourceType: 'files' as const,
        entry: {
          path: 'documents/readme.md',
          name: 'readme.md',
          type: 'file' as const,
          isDirectory: false,
        },
        writable: true,
      },
      {
        resourceType: 'skills' as const,
        entry: {
          path: 'skills/reviewer',
          name: 'reviewer',
          type: 'directory' as const,
          isDirectory: true,
        },
        writable: true,
      },
    ])('maps $resourceType entry $entry.path to its tree node', ({ resourceType, entry, writable }) => {
      const result = toFileTreeNode(entry, resourceType);

      expect(result).toEqual({
        id: entry.path,
        path: entry.path,
        name: entry.name,
        type: entry.isDirectory ? 'directory' : 'file',
        children: entry.isDirectory ? [] : undefined,
        extension: entry.isDirectory ? undefined : entry.name.split('.').pop(),
        writable,
      });
    });

    it.each([
      ['files' as const, createNode('skills/reviewer', 'directory'), false],
      ['files' as const, createNode('documents', 'directory'), true],
      ['files' as const, null, true],
      ['skills' as const, createNode('skills/reviewer', 'directory'), true],
    ])('sets mutation features for %s resources', (resourceType, node, canMutate) => {
      expect(marketplaceContextMenuFeatures(resourceType, node)).toEqual({
        upload: canMutate,
        createFile: canMutate,
        createFolder: canMutate,
        extractArchive: canMutate,
        copy: canMutate,
        copyPath: true,
        paste: resourceType === 'files' && canMutate,
        rename: canMutate,
        delete: canMutate,
      });
    });
  });
});
