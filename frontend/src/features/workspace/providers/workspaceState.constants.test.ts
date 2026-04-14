import { describe, expect, it } from 'vitest';
import { getClaudeCodeSubView } from './workspaceState.constants';
import { MAIN_NAVIGATION_ITEMS } from '../components/navigation-constants';

describe('Claude Code Memory navigation wiring', () => {
  it('resolves /claude-code/memory to the memory subview', () => {
    expect(getClaudeCodeSubView('/workspaces/ws-1/claude-code/memory')).toBe('memory');
  });

  it('registers memory under the Claude Code Settings submenu', () => {
    const claudeCodeItem = MAIN_NAVIGATION_ITEMS.find((item) => item.id === 'claude-code');

    expect(claudeCodeItem?.subItems?.some((item) => item.id === 'memory')).toBe(true);
  });
});
