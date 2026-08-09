import { describe, expect, it } from 'vitest';
import { initialState } from '../providers/workspaceStateConstants';
import type { WorkspacePermissions } from '../model/workspacePermissions';
import type { WorkspaceContextType, WorkspaceState } from '../providers/workspaceStateTypes';
import { resolveWorkspaceShellSurface } from './workspaceShellSurfaceModel';

const permissions: Pick<WorkspacePermissions, 'canRead' | 'canUseChat' | 'canUseTerminal'> = {
  canRead: true,
  canUseChat: true,
  canUseTerminal: true,
};

const workspaceRuntime: Pick<WorkspaceContextType['workspaceRuntime'], 'workspaceId' | 'agenticTools'> = {
  workspaceId: 'ws-1',
  agenticTools: ['claude-code'],
};

const createState = (overrides: Partial<WorkspaceState> = {}): WorkspaceState => ({
  ...initialState,
  ...overrides,
  agentToolSettings: {
    ...initialState.agentToolSettings,
    ...overrides.agentToolSettings,
  },
  containerManagement: {
    ...initialState.containerManagement,
    ...overrides.containerManagement,
  },
});

describe('workspace shell surface model', () => {
  it('derives a bottom companion only for the active terminal surface', () => {
    const terminal = resolveWorkspaceShellSurface({
      state: createState({
        currentFeature: 'file-management',
        companionActiveTab: 'terminal',
        companionTerminalPlacement: 'bottom',
      }),
      permissions,
      workspaceRuntime,
    });
    const chat = resolveWorkspaceShellSurface({
      state: createState({
        currentFeature: 'file-management',
        companionActiveTab: 'ai-chat',
        companionTerminalPlacement: 'bottom',
      }),
      permissions,
      workspaceRuntime,
    });

    expect(terminal).toMatchObject({
      companionActiveTab: 'terminal',
      shouldRenderCompanion: true,
      companionPlacement: 'bottom',
      isCompanionFullscreen: false,
    });
    expect(chat).toMatchObject({
      companionActiveTab: 'ai-chat',
      shouldRenderCompanion: true,
      companionPlacement: 'side',
    });
  });

  it('removes zero-DOM companion and navigator regions for unavailable or expanded surfaces', () => {
    const runtimePending = resolveWorkspaceShellSurface({
      state: createState(),
      permissions,
      workspaceRuntime: { ...workspaceRuntime, workspaceId: null },
    });
    const denied = resolveWorkspaceShellSurface({
      state: createState({ currentFeature: 'file-management' }),
      permissions: { ...permissions, canRead: false },
      workspaceRuntime,
    });
    const expanded = resolveWorkspaceShellSurface({
      state: createState({ mainContentExpanded: true }),
      permissions,
      workspaceRuntime,
    });
    const terminalRoute = resolveWorkspaceShellSurface({
      state: createState({
        currentFeature: 'container-management',
        containerManagement: { subView: 'terminal' },
      }),
      permissions,
      workspaceRuntime,
    });

    expect(runtimePending.shouldRenderCompanion).toBe(false);
    expect(denied.shouldRenderNavigator).toBe(false);
    expect(expanded).toMatchObject({
      isMainContentExpanded: true,
      shouldRenderNavigator: false,
      shouldRenderCompanion: false,
    });
    expect(terminalRoute).toMatchObject({
      isContainerTerminalPage: true,
      shouldRenderNavigator: false,
      shouldRenderCompanion: false,
    });
  });

  it('keeps fullscreen derived state tied to a visible companion', () => {
    const fullscreen = resolveWorkspaceShellSurface({
      state: createState({ chatExpanded: true }),
      permissions,
      workspaceRuntime,
    });
    const unavailable = resolveWorkspaceShellSurface({
      state: createState({ chatExpanded: true }),
      permissions,
      workspaceRuntime: { ...workspaceRuntime, workspaceId: null },
    });

    expect(fullscreen.isCompanionFullscreen).toBe(true);
    expect(unavailable.isCompanionFullscreen).toBe(false);
  });
});
