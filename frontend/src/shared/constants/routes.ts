/**
 * 應用程式路由常數
 * 集中管理所有路由路徑，避免硬編碼
 */

export const ROUTES = {
  // 根路徑
  ROOT: '/',

  // Workspace 相關
  WORKSPACES: '/workspaces',
  WORKSPACE_WIZARD: '/workspaces/workspace-wizard',
  WORKSPACE_DETAIL: (id: string) => `/workspaces/${id}`,

  // Template Management
  TEMPLATE_MANAGEMENT: '/templates',
  TEMPLATE_CENTER: '/templates/templates',
  TEMPLATE_CENTER_SETTINGS: '/templates/templates/settings',
  TEMPLATE_DETAIL: (id: string) => `/templates/templates/${id}`,
  TEMPLATE_EDIT: (id: string) => `/templates/templates/${id}/edit`,

  // Automation
  AUTOMATION: '/automation',

  // User Settings
  PROFILE: '/profile',
  SETTINGS: '/settings',
} as const;

export type RouteKey = keyof typeof ROUTES;
