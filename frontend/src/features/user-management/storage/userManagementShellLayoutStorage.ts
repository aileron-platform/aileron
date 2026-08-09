import {
  createShellLayoutStorage,
  type ShellLayoutStorageLimits,
  type ShellLayoutStoragePreferences,
} from '@/shared/storage/shellLayoutStorage';

// user-management has no per-entity concept (unlike marketplace/knowledge-base
// items), so every user shares one fixed layout key for the whole feature.
export const USER_MANAGEMENT_LAYOUT_ENTITY_ID = 'default';

export const USER_MANAGEMENT_SHELL_LAYOUT_LIMITS: ShellLayoutStorageLimits = {
  navSidebarWidth: { min: 220, max: 600 },
  secondColumnWidth: { min: 220, max: 600 },
  companionWidth: { min: 220, max: 600 },
  companionHeight: { min: 160, max: 520 },
};

export const USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS: ShellLayoutStoragePreferences = {
  navSidebarCollapsed: false,
  navSidebarWidth: 256,
  // User Management does not expose a navigator region, so these two fields
  // remain unused because the shared schema is common to every consumer.
  secondColumnCollapsed: false,
  secondColumnWidth: 256,
  companionCollapsed: false,
  companionWidth: 320,
  // The detail panel only ever uses side placement, so this field is
  // likewise unread — see the note above.
  companionHeight: 240,
  companionPlacement: 'side',
};

export const userManagementShellLayoutStorage = createShellLayoutStorage({
  featureKey: 'user-management',
  limits: USER_MANAGEMENT_SHELL_LAYOUT_LIMITS,
});
