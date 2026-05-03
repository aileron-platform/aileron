const containerManagement = {
  runtime: {
    header: {
      title: 'Runtime settings',
      actions: {
        save: 'Save settings',
        saving: 'Saving…',
      },
    },
    status: {
      loading: 'Loading runtime settings…',
      empty: 'Runtime settings are not available yet.',
    },
    notifications: {
      loadFailed: 'Failed to load runtime settings.',
      saveSuccess: 'Runtime settings have been updated.',
      saveFailed: 'Failed to save runtime settings.',
    },
    form: {
      runtime: {
        label: 'Container image',
        placeholder: 'Select container image',
        loading: 'Loading...',
        recommended: 'Recommended',
      },
      setupScript: {
        label: 'Setup script',
        placeholder:
          'Enter commands to install dependencies, e.g. npm install or pip install -r requirements.txt',
        description: 'These commands run automatically after the workspace is created.',
      },
    },
    resources: {
      title: 'Runtime resources',
      description: 'Only Kubernetes workspaces can override runtime CPU and memory requests / limits.',
      scope: 'workspace-browser and workspace-canvas continue using the platform defaults from the Helm chart.',
      requests: {
        title: 'Requests',
      },
      limits: {
        title: 'Limits',
      },
      fields: {
        cpu: 'CPU',
        memory: 'Memory',
      },
    },
    envVars: {
      label: 'Environment variables',
      keyPlaceholder: 'Variable name',
      valuePlaceholder: 'Variable value',
      add: 'Add environment variable',
    },
    environments: {
      universal: {
        label: 'Standard Container Image',
        description: 'Aileron standard runtime with Python, Node.js, Git, SSH, Claude Code, and a complete developer toolchain.',
      },
      'ubuntu-22': {
        label: 'Ubuntu 22.04',
        description: 'General-purpose Linux development environment',
      },
      'ubuntu-24': {
        label: 'Ubuntu 24.04',
        description: 'Latest Ubuntu LTS release',
      },
      'node-18': {
        label: 'Node.js 18',
        description: 'Node.js 18 with npm tooling',
      },
      'node-20': {
        label: 'Node.js 20',
        description: 'Node.js 20 with npm tooling',
      },
      'python-311': {
        label: 'Python 3.11',
        description: 'Python 3.11 with pip tooling',
      },
      'python-312': {
        label: 'Python 3.12',
        description: 'Python 3.12 with pip tooling',
      },
    },
  },
  firewall: {
    header: {
      title: 'Firewall',
      actions: {
        save: 'Save settings',
        saving: 'Saving…',
      },
    },
    status: {
      loading: 'Loading firewall settings…',
      empty: 'Firewall settings are not available yet.',
    },
    notifications: {
      loadFailed: 'Failed to load firewall settings.',
      saveSuccess: 'Firewall settings have been updated.',
      saveFailed: 'Failed to save firewall settings.',
    },
    unavailable: {
      title: 'Firewall unavailable',
      description: 'Cilium is not enabled on this platform, so firewall features are unavailable.',
      reasons: {
        CILIUM_NOT_ENABLED: 'Cilium is not enabled on this platform, so firewall features are unavailable.',
      },
    },
    groups: {
      workspace: {
        title: 'Workspace network rules',
        description: 'Applied to workspace-runtime and workspace-canvas.',
      },
      browser: {
        title: 'Browser network rules',
        description: 'Applied to workspace-browser.',
      },
    },
    networkAccess: {
      label: 'Network Access',
      badge: {
        enabled: 'Enabled',
        disabled: 'Disabled',
      },
      options: {
        enabled: {
          description: 'Allow container to access external network',
        },
        disabled: {
          description: 'Deny container access to external network',
        },
      },
    },
    domainAccessMode: {
      label: 'Domain Access Mode',
      badge: {
        all: 'All (Unrestricted)',
        specific: 'Specific Domains',
      },
      options: {
        all: {
          description: 'Allow access to all domains',
        },
        specific: {
          description: 'Only allow access to specified domains',
        },
      },
    },
    allowedDomains: {
      label: 'Allowed Domains',
      placeholder: 'Enter a domain, e.g. example.com',
      add: 'Add allowed domain',
    },
    effectiveAllowedDomains: {
      label: 'Effective allowed domains',
      empty: 'No additional effective domains are available yet.',
    },
  },
  terminal: {
    title: 'Terminal',
    newTab: 'New Tab',
    header: {
      title: 'Workspace terminal',
    },
    tabs: {
      label: 'Terminal {{index}}',
      add: 'Add terminal',
      empty: 'No terminal',
      new: 'New terminal',
      close: 'Close terminal',
      active: 'Active',
    },
    menus: {
      actions: 'Actions',
      context: {
        clear: 'Clear',
        close: 'Close terminal',
        rename: 'Rename',
        unassign: 'Unassign',
        renamePrompt: 'Enter a new terminal name',
        switch: 'Switch terminal',
      },
    },
    layout: {
      changeTooltip: 'Change layout',
      confirm: {
        title: 'Change layout?',
        description:
          'Switching to this layout will close {{count}} active terminal connection(s). The oldest connections will be kept. Continue?',
        cancel: 'Cancel',
        confirm: 'Continue',
      },
      options: {
        single: {
          label: 'Single',
          description: '1 pane',
        },
        splitHorizontal: {
          label: 'Split Horizontal',
          description: '2 side-by-side panes',
        },
        splitVertical: {
          label: 'Split Vertical',
          description: '2 stacked panes',
        },
        quad: {
          label: 'Quad',
          description: '4 equal panes',
        },
        leftOneRightTwo: {
          label: 'Left 1 Right 2',
          description: '1 left pane, 2 right panes (top/bottom)',
        },
        rightOneLeftTwo: {
          label: 'Right 1 Left 2',
          description: '2 left panes (top/bottom), 1 right pane',
        },
        topOneBottomTwo: {
          label: 'Top 1 Bottom 2',
          description: '1 top pane, 2 bottom panes (left/right)',
        },
        bottomOneTopTwo: {
          label: 'Bottom 1 Top 2',
          description: '2 top panes (left/right), 1 bottom pane',
        },
      },
    },
    status: {
      connecting: 'Connecting...',
      reconnecting: 'Reconnecting...',
      connected: 'Connected',
      disconnected: 'Disconnected',
      unassigned: 'Not assigned',
    },
    connectionError: 'Connection Error',
    connect: 'Connect',
    retry: 'Retry',
    actions: {
      copy: 'Copy',
      paste: 'Paste',
      restart: 'Restart terminal',
      enterFullscreen: 'Enter fullscreen',
      exitFullscreen: 'Exit fullscreen',
    },
    footer: {
      rows_one: 'Row {{count}}',
      rows_other: 'Rows {{count}}',
      columns_one: 'Column {{count}}',
      columns_other: 'Columns {{count}}',
      selection_one: 'Selected {{count}} character',
      selection_other: 'Selected {{count}} characters',
      rows: 'Rows: {{count}}',
      columns: 'Cols: {{count}}',
      encoding: 'UTF-8',
      selection: 'Selected: {{count}}',
    },
    limits: {
      max: {
        title: 'Terminal limit reached',
        description: 'You can open up to {{count}} terminals.',
      },
    },
  },
};

export default containerManagement;
