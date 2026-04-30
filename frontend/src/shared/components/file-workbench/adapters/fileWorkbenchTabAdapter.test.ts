import { describe, expect, it } from 'vitest';
import {
  toFileWorkbenchTab,
} from './index';

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
    });
  });
});
