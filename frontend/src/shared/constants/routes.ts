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
  TEMPLATE_MANAGEMENT: '/workspaces/template-management',
  TEMPLATE_CENTER: '/workspaces/template-management/templates',
  TEMPLATE_CENTER_SETTINGS: '/workspaces/template-management/templates/settings',
  TEMPLATE_DETAIL: (id: string) => `/workspaces/template-management/templates/${id}`,
  TEMPLATE_EDIT: (id: string) => `/workspaces/template-management/templates/${id}/edit`,
  
  // Automation
  AUTOMATION: '/workspaces/automation',
  
  // User Settings
  PROFILE: '/workspaces/profile',
  SETTINGS: '/workspaces/settings',
} as const;

export type RouteKey = keyof typeof ROUTES;

