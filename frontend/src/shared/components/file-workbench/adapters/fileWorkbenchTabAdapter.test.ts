import { describe, expect, it } from 'vitest';
import {
  toFileWorkbenchTab,
} from './fileWorkbenchTabAdapter';

describe('file workbench tab adapter', () => {
  it('normalizes domain editor tabs into public workbench tabs', () => {
    expect(toFileWorkbenchTab({
      path: '/docs/readme.md',
      name: 'readme.md',
      content: 'current',
      originalContent: 'base',
      isModified: true,
      isLoading: true,
    })).toEqual({
      id: '/docs/readme.md',
      path: '/docs/readme.md',
      name: 'readme.md',
      content: 'current',
      originalContent: 'base',
      isModified: true,
      isLoading: true,
      error: undefined,
      readable: undefined,
      unreadableReason: undefined,
    });
  });

  it('preserves unreadable binary state for the shared viewer', () => {
    expect(toFileWorkbenchTab({
      path: '/archive.zip',
      name: 'archive.zip',
      content: '',
      originalContent: '',
      isModified: false,
      readable: false,
      unreadableReason: 'binary',
    })).toMatchObject({
      readable: false,
      unreadableReason: 'binary',
    });
  });
});
