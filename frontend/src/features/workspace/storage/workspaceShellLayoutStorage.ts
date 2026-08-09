import {
  createShellLayoutStorage,
  type ShellLayoutStorageLimits,
  type ShellLayoutStoragePreferences,
} from '@/shared/storage/shellLayoutStorage';

export const WORKSPACE_SHELL_LAYOUT_LIMITS: ShellLayoutStorageLimits = {
  navSidebarWidth: { min: 240, max: 500 },
  secondColumnWidth: { min: 270, max: 600 },
  companionWidth: { min: 408, max: 800 },
  companionHeight: { min: 160, max: 520 },
};

export const WORKSPACE_SHELL_LAYOUT_DEFAULTS: ShellLayoutStoragePreferences = {
  navSidebarCollapsed: false,
  navSidebarWidth: 240,
  secondColumnCollapsed: false,
  secondColumnWidth: 270,
  companionCollapsed: false,
  companionWidth: 408,
  companionHeight: 240,
  companionPlacement: 'side',
};

export const workspaceShellLayoutStorage = createShellLayoutStorage({
  featureKey: 'workspace',
  limits: WORKSPACE_SHELL_LAYOUT_LIMITS,
});
