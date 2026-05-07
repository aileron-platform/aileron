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

  // Marketplace
  MARKETPLACE: '/marketplace',
  MARKETPLACE_PACKAGES: '/marketplace/packages',
  MARKETPLACE_SETTINGS: '/marketplace/packages/settings',
  MARKETPLACE_PACKAGE_DETAIL: (provider: string, id: string) => `/marketplace/packages/${provider}/${id}`,
  MARKETPLACE_PACKAGE_EDIT: (provider: string, id: string) => `/marketplace/packages/${provider}/${id}/edit`,

  // Automation
  AUTOMATION: '/automation',

  // Knowledge Bases
  KNOWLEDGE_BASES: '/knowledge-bases',
  KNOWLEDGE_BASE_DETAIL: (id: string) => `/knowledge-bases/${id}`,
  KNOWLEDGE_BASE_DETAIL_FILES: (id: string) => `/knowledge-bases/${id}/files`,
  KNOWLEDGE_BASE_DETAIL_WIKI: (id: string) => `/knowledge-bases/${id}/wiki`,
  KNOWLEDGE_BASE_DETAIL_GRAPH: (id: string) => `/knowledge-bases/${id}/graph`,
  KNOWLEDGE_BASE_DETAIL_VERSION_CONTROL: (id: string) => `/knowledge-bases/${id}/version-control`,
  KNOWLEDGE_BASE_DETAIL_SCHEDULES: (id: string) => `/knowledge-bases/${id}/schedules`,
  KNOWLEDGE_BASE_DETAIL_SHARING: (id: string) => `/knowledge-bases/${id}/sharing`,
  KNOWLEDGE_BASE_DETAIL_WORKSPACES: (id: string) => `/knowledge-bases/${id}/workspaces`,

  // User Settings
  PROFILE: '/profile',
  SETTINGS: '/settings',
} as const;

export type RouteKey = keyof typeof ROUTES;
