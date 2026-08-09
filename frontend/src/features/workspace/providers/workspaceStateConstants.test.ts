import { describe, expect, it } from 'vitest';
import {
  getAgentToolSubView,
  getContainerManagementSubView,
  getFeatureFromPath,
  getVersionControlSubView,
  getWorkspaceSettingsSubView,
  initialState,
  WORKSPACE_LAYOUT_HEIGHT_LIMITS,
} from './workspaceStateConstants';
import { MAIN_NAVIGATION_ITEMS } from '../layout/workspaceNavigationModel';

describe('Claude Code Memory navigation wiring', () => {
  it('resolves /claude-code/memory to the memory subview', () => {
    expect(getAgentToolSubView('/workspaces/ws-1/claude-code/memory')).toBe('memory');
  });

  it('resolves /claude-code/plugins to the plugins subview', () => {
    expect(getAgentToolSubView('/workspaces/ws-1/claude-code/plugins')).toBe('plugins');
  });

  it('registers memory under the Claude Code Settings submenu', () => {
    const claudeCodeItem = MAIN_NAVIGATION_ITEMS.find((item) => item.id === 'claude-code');

    expect(claudeCodeItem?.subItems?.some((item) => item.id === 'memory')).toBe(true);
  });
});

describe('Agent tool navigation routing', () => {
  it.each([
    ['/workspaces/ws-1/claude-code', 'claude-md'],
    ['/workspaces/ws-1/claude-code/mcp', 'mcp'],
    ['/workspaces/ws-1/claude-code/skills', 'skills'],
    ['/workspaces/ws-1/claude-code/permissions', 'settings'],
    ['/workspaces/ws-1/claude-code/settings', 'settings'],
    ['/workspaces/ws-1/codex', 'agents-md'],
    ['/workspaces/ws-1/codex/agents-md', 'agents-md'],
    ['/workspaces/ws-1/codex/skills', 'skills'],
    ['/workspaces/ws-1/codex/subagents', 'subagents'],
    ['/workspaces/ws-1/codex/prompts', 'prompts'],
    ['/workspaces/ws-1/codex/mcp', 'mcp'],
    ['/workspaces/ws-1/codex/hooks', 'hooks'],
    ['/workspaces/ws-1/codex/rules', 'rules'],
    ['/workspaces/ws-1/codex/plugins', 'plugins'],
    ['/workspaces/ws-1/codex/settings', 'settings'],
    ['/workspaces/ws-1/codex/config', 'agents-md'],
    ['/workspaces/ws-1/opencode', 'agents-md'],
  ])('resolves %s to %s', (pathname, expected) => {
    expect(getAgentToolSubView(pathname)).toBe(expected);
  });

  it('does not resolve removed Gemini paths as agent settings subviews', () => {
    expect(getAgentToolSubView('/workspaces/ws-1/gemini')).toBe('agents-md');
    expect(getAgentToolSubView('/workspaces/ws-1/gemini/settings')).toBe('agents-md');
  });
});

describe('Workspace canonical route parsing', () => {
  it.each([
    ['/workspaces/ws-1/home', 'ai-chat-home'],
    ['/workspaces/ws-1/files', 'file-management'],
    ['/workspaces/ws-1/version-control/history', 'version-control'],
    ['/workspaces/ws-1/workspace-settings/reset', 'workspace-settings'],
    ['/workspaces/ws-1/container-management/terminal', 'container-management'],
    ['/workspaces/ws-1/workspace-automation', 'workspace-automation'],
    ['/workspaces/ws-1/canvas', 'canvas'],
    ['/workspaces/ws-1/browser', 'browser'],
    ['/workspaces/ws-1/claude-code/memory', 'claude-code'],
    ['/workspaces/ws-1/opencode/settings', 'opencode'],
    ['/workspaces/ws-1/codex/rules', 'codex'],
  ])('resolves %s to %s', (pathname, expected) => {
    expect(getFeatureFromPath(pathname)).toBe(expected);
  });

  it.each([
    '/workspaces/ws-1/canvas/browser',
    '/workspaces/ws-1/canvas/web-canvas',
    '/workspaces/ws-1/browser/session',
  ])('does not resolve removed single-view feature subpaths from %s', (pathname) => {
    expect(getFeatureFromPath(pathname)).toBe('file-management');
  });

  it('ignores feature-like workspace id segments', () => {
    expect(getFeatureFromPath('/workspaces/my-codex/files')).toBe('file-management');
    expect(getFeatureFromPath('/workspaces/version-control-team/canvas')).toBe('canvas');
    expect(getFeatureFromPath('/workspaces/canvas-team/browser')).toBe('browser');
  });

  it('reads subviews only from the canonical feature segment', () => {
    expect(getVersionControlSubView('/workspaces/history/version-control/history')).toBe('history');
    expect(getWorkspaceSettingsSubView('/workspaces/reset/workspace-settings/reset')).toBe('reset');
    expect(getContainerManagementSubView('/workspaces/terminal/container-management/terminal')).toBe('terminal');
  });
});

describe('workspace companion active tab defaults', () => {
  it('defaults the companion tab to ai chat', () => {
    expect(initialState.companionActiveTab).toBe('ai-chat');
    expect(initialState.companionTerminalPlacement).toBe('side');
    expect(WORKSPACE_LAYOUT_HEIGHT_LIMITS.mainContent).toEqual({
      preferredMin: 240,
    });
  });
});
