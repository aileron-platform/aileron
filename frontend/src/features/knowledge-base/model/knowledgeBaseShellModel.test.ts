import { describe, expect, it } from 'vitest';
import {
  buildKnowledgeBaseNavPath,
  resolveKnowledgeBaseActiveNav,
} from './knowledgeBaseShellModel';

describe('resolveKnowledgeBaseActiveNav', () => {
  it.each([
    ['/knowledge-bases/kb-1/files', 'files', null],
    ['/knowledge-bases/kb-1/version-control/changes', 'version-control', 'changes'],
    ['/knowledge-bases/kb-1/version-control/history', 'version-control', 'history'],
    ['/knowledge-bases/kb-1/version-control', 'version-control', 'changes'],
    ['/knowledge-bases/kb-1/sharing', 'sharing', null],
    ['/knowledge-bases/kb-1/workspaces', 'workspaces', null],
    ['/knowledge-bases/kb-1/settings', 'settings', null],
  ])('resolves %s to %s / %s', (pathname, featureId, subItemId) => {
    expect(resolveKnowledgeBaseActiveNav(pathname)).toEqual({ featureId, subItemId });
  });

  it('falls back to files for the detail root', () => {
    expect(resolveKnowledgeBaseActiveNav('/knowledge-bases/kb-1')).toEqual({ featureId: 'files', subItemId: null });
  });

  it('does not activate navigation for an unknown path', () => {
    expect(resolveKnowledgeBaseActiveNav('/knowledge-bases/kb-1/unknown')).toEqual({
      featureId: null,
      subItemId: null,
    });
  });
});

describe('buildKnowledgeBaseNavPath', () => {
  it('builds feature paths', () => {
    expect(buildKnowledgeBaseNavPath('kb-1', 'files')).toBe('/knowledge-bases/kb-1/files');
    expect(buildKnowledgeBaseNavPath('kb-1', 'version-control')).toBe('/knowledge-bases/kb-1/version-control/changes');
    expect(buildKnowledgeBaseNavPath('kb-1', 'version-control', 'history')).toBe('/knowledge-bases/kb-1/version-control/history');
    expect(buildKnowledgeBaseNavPath('kb-1', 'workspaces')).toBe('/knowledge-bases/kb-1/workspaces');
    expect(buildKnowledgeBaseNavPath('kb-1', 'settings')).toBe('/knowledge-bases/kb-1/settings');
  });
});
