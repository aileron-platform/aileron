import { describe, expect, it } from 'vitest';
import type { FileTreeNode } from '@/shared/components/file-workbench';
import {
  createPlaceholderNode,
  getContextMenuTargetDirectory,
  getParentPath,
  getRelatedPathsForDelete,
  resolveTargetDirectory,
} from './fileManagementSidebarModel';
import { ensureLeadingSlash } from './filePathModel';

const flatNodes: FileTreeNode[] = [
  { id: '/src', name: 'src', path: '/src', type: 'directory' },
  { id: '/src/App.tsx', name: 'App.tsx', path: '/src/App.tsx', type: 'file' },
  { id: '/src/components', name: 'components', path: '/src/components', type: 'directory' },
  { id: '/src/components/Button.tsx', name: 'Button.tsx', path: '/src/components/Button.tsx', type: 'file' },
];

describe('fileManagementSidebarModel', () => {
  it('normalizes paths and resolves parent directories for root-safe workspace paths', () => {
    expect(ensureLeadingSlash('src/App.tsx')).toBe('/src/App.tsx');
    expect(ensureLeadingSlash('/src/App.tsx')).toBe('/src/App.tsx');
    expect(getParentPath('')).toBe('/');
    expect(getParentPath('/')).toBe('/');
    expect(getParentPath('/src/App.tsx')).toBe('/src');
    expect(getParentPath('/README.md')).toBe('/');
  });

  it('resolves file and directory selections to upload/create target directories', () => {
    expect(resolveTargetDirectory({ basePath: '/', flatNodes })).toBe('/');
    expect(resolveTargetDirectory({ basePath: '/src', flatNodes })).toBe('/src');
    expect(resolveTargetDirectory({ basePath: '/src/App.tsx', flatNodes })).toBe('/src');
    expect(resolveTargetDirectory({ basePath: '/missing/file.txt', flatNodes })).toBe('/missing');
  });

  it('creates placeholder file tree nodes from paths', () => {
    expect(createPlaceholderNode('/src/NewFile.tsx')).toEqual({
      id: '/src/NewFile.tsx',
      name: 'NewFile.tsx',
      path: '/src/NewFile.tsx',
      type: 'file',
    });
    expect(createPlaceholderNode('/src/new-folder', 'directory')).toMatchObject({
      name: 'new-folder',
      type: 'directory',
    });
  });

  it('collects descendant paths for file and directory deletes', () => {
    expect(getRelatedPathsForDelete({ paths: ['/src/App.tsx'], flatNodes })).toEqual(['/src/App.tsx']);
    expect(getRelatedPathsForDelete({ paths: ['/src'], flatNodes })).toEqual([
      '/src',
      '/src/App.tsx',
      '/src/components',
      '/src/components/Button.tsx',
    ]);
  });

  it('derives context menu target directories', () => {
    expect(getContextMenuTargetDirectory({ id: '/src', name: 'src', path: '/src', type: 'directory' })).toBe('/src');
    expect(getContextMenuTargetDirectory({ id: '/src/App.tsx', name: 'App.tsx', path: '/src/App.tsx', type: 'file' })).toBe('/src');
    expect(getContextMenuTargetDirectory(null)).toBe('/');
  });
});
