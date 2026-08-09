import { describe, expect, it } from 'vitest';
import { getGlobalNavigationModule } from './globalNavigationModel';

describe('getGlobalNavigationModule', () => {
  it.each([
    ['/workspaces/ws-1/files', 'workspace'],
    ['/marketplace', 'marketplace'],
    ['/marketplace/packages', 'marketplace'],
    ['/automation/jobs', 'automation'],
    ['/knowledge-bases/kb-1/files', 'knowledge-base'],
    ['/user-management/groups', 'user-management'],
    ['/platform-resources/workspaces', 'platform-resources'],
    ['/marketplace-copy', 'workspace'],
    ['/profile', 'workspace'],
  ] as const)('maps %s to %s', (pathname, expected) => {
    expect(getGlobalNavigationModule(pathname)).toBe(expected);
  });
});
