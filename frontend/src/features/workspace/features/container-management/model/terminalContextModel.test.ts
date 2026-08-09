import { describe, expect, it } from 'vitest';
import { resolveDefaultTerminalWorkspacePath } from './terminalContextModel';

describe('resolveDefaultTerminalWorkspacePath', () => {
  it('returns the selected git context repoPath when available', () => {
    expect(
      resolveDefaultTerminalWorkspacePath(
        [
          {
            id: 'primary',
            kind: 'primary',
            displayName: 'main',
            repoPath: '/workspace',
            detached: false,
            locked: false,
            prunable: false,
          },
          {
            id: 'worktree:feature-auth',
            kind: 'worktree',
            displayName: 'feature-auth',
            repoPath: '/workspace/.worktrees/feature-auth',
            detached: false,
            locked: false,
            prunable: false,
          },
        ],
        'worktree:feature-auth',
      ),
    ).toBe('/workspace/.worktrees/feature-auth');
  });

  it('falls back to /workspace when the selected context is missing', () => {
    expect(resolveDefaultTerminalWorkspacePath([], 'worktree:missing')).toBe('/workspace');
    expect(resolveDefaultTerminalWorkspacePath(undefined, null)).toBe('/workspace');
  });
});
