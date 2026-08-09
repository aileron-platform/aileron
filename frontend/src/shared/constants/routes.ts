/**
 * Canonical route constants for the application.
 *
 * Routes are grouped by domain and exposed as builder functions for any path
 * that requires a dynamic segment. Navigation under src/features and src/app
 * must go through these builders rather than hardcoded path strings.
 */

export const ROUTES = {
  root: '/',
  login: '/login',
  register: '/register',
  // Global (non-workspace-scoped) routes.
  automation: '/automation',
  userManagement: {
    root: '/user-management',
    users: '/user-management/users',
    roleIssues: '/user-management/role-issues',
    disabledUsers: '/user-management/disabled',
    groups: '/user-management/groups',
    emptyGroups: '/user-management/groups/empty',
    groupMembers: (groupId: string) => `/user-management/groups/${groupId}/members`,
  },
  platformResources: {
    root: '/platform-resources',
    workspaces: '/platform-resources/workspaces',
    knowledgeBases: '/platform-resources/knowledge-bases',
    analytics: {
      root: '/platform-resources/analytics',
      workspaces: '/platform-resources/analytics/workspaces',
      knowledgeBases: '/platform-resources/analytics/knowledge-bases',
    },
  },
  workspace: {
    root: '/workspaces',
    wizard: '/workspaces/workspace-wizard',
    home: (workspaceId: string) => `/workspaces/${workspaceId}/home`,
    unavailable: (workspaceId: string) => `/workspaces/${workspaceId}/unavailable`,
    files: (workspaceId: string) => `/workspaces/${workspaceId}/files`,
    versionControl: (workspaceId: string, subView?: string) =>
      `/workspaces/${workspaceId}/version-control${subView ? `/${subView}` : ''}`,
    settings: (workspaceId: string, subView?: string) =>
      `/workspaces/${workspaceId}/workspace-settings${subView ? `/${subView}` : ''}`,
    containers: (workspaceId: string, subView?: string) =>
      `/workspaces/${workspaceId}/container-management${subView ? `/${subView}` : ''}`,
    automation: (workspaceId: string) => `/workspaces/${workspaceId}/workspace-automation`,
    canvas: (workspaceId: string) => `/workspaces/${workspaceId}/canvas`,
    browser: (workspaceId: string) => `/workspaces/${workspaceId}/browser`,
    agentTool: (workspaceId: string, agentTool: string, subView?: string) =>
      `/workspaces/${workspaceId}/${agentTool}${subView ? `/${subView}` : ''}`,
  },
  marketplace: {
    root: '/marketplace',
    packages: '/marketplace/packages',
    settings: '/marketplace/packages/settings',
    packageDetail: (provider: string, id: string) => `/marketplace/packages/${provider}/${id}`,
    packageEdit: (provider: string, id: string) => `/marketplace/packages/${provider}/${id}/edit`,
  },
  knowledgeBase: {
    root: '/knowledge-bases',
    detail: (id: string) => `/knowledge-bases/${id}`,
    files: (id: string) => `/knowledge-bases/${id}/files`,
    versionControl: (id: string) => `/knowledge-bases/${id}/version-control`,
    versionControlChanges: (id: string) => `/knowledge-bases/${id}/version-control/changes`,
    versionControlHistory: (id: string) => `/knowledge-bases/${id}/version-control/history`,
    sharing: (id: string) => `/knowledge-bases/${id}/sharing`,
    workspaces: (id: string) => `/knowledge-bases/${id}/workspaces`,
    settings: (id: string) => `/knowledge-bases/${id}/settings`,
  },
  profile: '/profile',
  settings: '/settings',
} as const;
