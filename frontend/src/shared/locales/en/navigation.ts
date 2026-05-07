const navigation = {
  workspace: 'Workspace',
  marketplace: 'Marketplace',
  automation: 'Automation',
  knowledgeBaseCenter: 'Knowledge Base Center',
  brand: {
    title: 'Aileron',
  },
  workspaceSelector: {
    label: 'Workspace:',
    current: 'Current workspace',
    description: 'No description provided',
    selectLabel: 'Select workspace',
    newWorkspace: 'Create workspace',
    empty: 'No workspaces available',
    error: 'Failed to load workspaces',
    active: 'Active',
    owner: 'Owner: {{name}}',
    namespace: 'Namespace: {{name}}',
    provisioners: {
      docker: 'Docker',
      kubernetes: 'Kubernetes',
    },
    phases: {
      running: 'Running',
      starting: 'Starting',
      reconciling: 'Reconciling',
      pending: 'Pending',
      failed: 'Failed',
      error: 'Error',
      stopped: 'Stopped',
      disabled: 'Disabled',
      unknown: 'Unknown',
    },
  },
  userMenu: {
    defaultUser: 'User',
    profile: 'Profile',
    settings: 'System settings',
    logout: 'Log out',
    login: 'Log in',
  },
  fullscreen: {
    enter: 'Enter fullscreen',
    exit: 'Exit fullscreen',
    error: 'Failed to toggle fullscreen',
  },
  compactHeader: {
    exitFullscreen: 'Exit fullscreen',
    modules: {
      workspace: 'Workspace',
      automation: 'Automation',
      marketplace: 'Marketplace',
      knowledgeBase: 'Knowledge Base Center',
    },
    separator: '›',
  },
};

export default navigation;
