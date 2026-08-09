import { describe, expect, it } from 'vitest';
import {
  getFileOperationResponseRevision,
  parseFileContent,
  parseFileTree,
} from './fileResponseAdapter';
import type { FileOperationResponse } from '../types';

describe('parseFileTree', () => {
  it('normalizes workspace FileTreeResponse (nodes)', () => {
    const raw = {
      path: '/',
      scope: 'project',
      total: 1,
      nodes: [
        {
          id: 'skills/a',
          name: 'a',
          path: 'skills/a',
          type: 'directory',
          hasChildren: true,
          children: [
            {
              id: 'skills/a/SKILL.md',
              name: 'SKILL.md',
              path: 'skills/a/SKILL.md',
              type: 'file',
              size: 10,
              writable: true,
              metadata: { source: 'user' },
              badges: [{ key: 'origin', label: 'review-tools' }],
              hasChildren: false,
              children: [],
            },
          ],
        },
      ],
    };
    const out = parseFileTree(raw);
    expect(out[0].children?.[0].path).toBe('skills/a/SKILL.md');
    expect(out[0].children?.[0].type).toBe('file');
    expect(out[0].children?.[0]).toMatchObject({
      writable: true,
      metadata: { source: 'user' },
      badges: [{ key: 'origin', label: 'review-tools' }],
    });
  });

  it('normalizes plain nodes array', () => {
    const raw = [{ id: 'commands/x.md', name: 'x.md', path: 'commands/x.md', type: 'file' }];
    expect(parseFileTree(raw)[0].name).toBe('x.md');
  });
});

describe('parseFileContent', () => {
  it('reads FileContentResponse revision without legacy token fallback', () => {
    expect(parseFileContent({
      path: 'a',
      scope: 'project',
      content: 'hi',
      size: 2,
      updatedAt: '',
      revision: 'r1',
    })).toEqual({ path: 'a', content: 'hi', size: 2, revision: 'r1' });
    expect(parseFileContent({
      path: 'b',
      content: 'yo',
      size: 2,
      updatedAt: '',
      versionId: 'legacy',
      contentHash: 'legacy-hash',
    })).toEqual({ path: 'b', content: 'yo', size: 2 });
  });
});

describe('getFileOperationResponseRevision', () => {
  it.each([
    [{ success: true, data: { revision: 'revision-1' } }, 'revision-1'],
    [{ success: true, data: { revision: null } }, null],
    [{ success: true, data: {} }, undefined],
    [{ success: true, data: { revision: 1 } }, undefined],
    [undefined, undefined],
  ] as Array<[FileOperationResponse | undefined, string | null | undefined]>)(
    'maps the optional revision without legacy fallback',
    (response, expected) => {
      expect(getFileOperationResponseRevision(response)).toBe(expected);
    },
  );
});
