import { describe, expect, it } from 'vitest';
import { ROUTES } from './routes';

describe('ROUTES canonical builders', () => {
  it('builds every workspace feature under an explicit workspace id', () => {
    expect(ROUTES.workspace.home('ws-1')).toBe('/workspaces/ws-1/home');
    expect(ROUTES.workspace.files('ws-1')).toBe('/workspaces/ws-1/files');
    expect(ROUTES.workspace.versionControl('ws-1', 'history')).toBe(
      '/workspaces/ws-1/version-control/history',
    );
    expect(ROUTES.workspace.settings('ws-1', 'basic')).toBe(
      '/workspaces/ws-1/workspace-settings/basic',
    );
    expect(ROUTES.workspace.containers('ws-1', 'runtime')).toBe(
      '/workspaces/ws-1/container-management/runtime',
    );
    expect(ROUTES.workspace.automation('ws-1')).toBe(
      '/workspaces/ws-1/workspace-automation',
    );
    expect(ROUTES.workspace.canvas('ws-1')).toBe('/workspaces/ws-1/canvas');
    expect(ROUTES.workspace.browser('ws-1')).toBe('/workspaces/ws-1/browser');
    expect(ROUTES.workspace.agentTool('ws-1', 'codex', 'settings')).toBe(
      '/workspaces/ws-1/codex/settings',
    );
  });

  it('builds marketplace and knowledge base routes without hardcoded helper callers', () => {
    expect(ROUTES.marketplace.packages).toBe('/marketplace/packages');
    expect(ROUTES.knowledgeBase.files('kb-1')).toBe('/knowledge-bases/kb-1/files');
    expect(ROUTES.knowledgeBase.workspaces('kb-1')).toBe('/knowledge-bases/kb-1/workspaces');
  });

  it('keeps the global automation route at the top level', () => {
    expect(ROUTES.automation).toBe('/automation');
  });
});
