import { describe, expect, it } from 'vitest';
import { getAgentToolSubView, getClaudeCodeSubView } from './workspaceState.constants';
import { MAIN_NAVIGATION_ITEMS } from '../components/navigation-constants';

describe('Claude Code Memory navigation wiring', () => {
  it('resolves /claude-code/memory to the memory subview', () => {
    expect(getClaudeCodeSubView('/workspaces/ws-1/claude-code/memory')).toBe('memory');
  });

  it('resolves /claude-code/plugins to the plugins subview', () => {
    expect(getClaudeCodeSubView('/workspaces/ws-1/claude-code/plugins')).toBe('plugins');
  });

  it('registers memory under the Claude Code Settings submenu', () => {
    const claudeCodeItem = MAIN_NAVIGATION_ITEMS.find((item) => item.id === 'claude-code');

    expect(claudeCodeItem?.subItems?.some((item) => item.id === 'memory')).toBe(true);
  });
});

describe('Agent tool navigation routing', () => {
  it.each([
    ['/workspaces/codex', 'agents-md'],
    ['/workspaces/codex/agents-md', 'agents-md'],
    ['/workspaces/codex/skills', 'skills'],
    ['/workspaces/codex/subagents', 'subagents'],
    ['/workspaces/codex/prompts', 'prompts'],
    ['/workspaces/codex/mcp', 'mcp'],
    ['/workspaces/codex/hooks', 'hooks'],
    ['/workspaces/codex/rules', 'rules'],
    ['/workspaces/codex/plugins', 'plugins'],
    ['/workspaces/codex/config', 'agents-md'],
    ['/workspaces/gemini', 'gemini-md'],
    ['/workspaces/opencode', 'agents-md'],
  ])('resolves %s to %s', (pathname, expected) => {
    expect(getAgentToolSubView(pathname)).toBe(expected);
  });
});
