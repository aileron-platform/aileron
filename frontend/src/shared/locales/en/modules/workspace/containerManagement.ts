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
    browserCredential: {
      title: 'Browser access credential',
      description: 'Rotate the user and administrator credentials for this workspace browser.',
      rotate: 'Rotate credential',
      rotateSuccess: 'Browser credential rotation has started.',
      rotateFailed: 'Browser credential rotation could not be started.',
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
    envVars: {
      label: 'Environment variables',
      keyPlaceholder: 'Variable name',
      valuePlaceholder: 'Variable value',
      configuredValuePlaceholder: 'Configured — enter a new value to replace',
      replaceConfiguredValues: 'Re-enter every configured value before replacing the environment variable list.',
      add: 'Add environment variable',
    },
    environments: {
      universal: {
        label: 'Standard Container Image',
        description: 'Aileron standard runtime with Python, Node.js, Git, SSH, Claude Code, and a complete developer toolchain.',
      },
      java: {
        label: 'Java 21 + Maven',
        description: 'Eclipse Temurin JDK 21 with Apache Maven 3.9, ready for Spring Boot and Maven projects.',
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
      applied: 'Firewall settings are now enforced.',
      saveFailed: 'Failed to save firewall settings.',
      refreshFailed: 'Unable to refresh firewall synchronization status.',
      retryFailed: 'Unable to retry firewall synchronization.',
      revisionConflict: 'Firewall settings changed elsewhere. The latest settings were loaded.',
    },
    sync: {
      applying: {
        title: 'Applying firewall settings',
        description: 'Observed revision {{observedRevision}} is converging on desired revision {{desiredRevision}}.',
      },
      applied: 'Applied revision {{revision}} is enforced.',
      failed: {
        title: 'Firewall enforcement failed',
        description: 'The desired firewall revision could not be enforced.',
        retry: 'Retry enforcement',
        retrying: 'Retrying…',
      },
    },
    errors: {
      FIREWALL_DELIVERY_FAILED: 'The control plane could not deliver the desired firewall revision.',
      FIREWALL_APPLY_FAILED: 'The platform could not enforce the desired firewall revision.',
      FIREWALL_DOMAIN_INVALID: 'Enter one canonical exact hostname without a wildcard, URL, path, port, or IP address.',
      FIREWALL_DOMAIN_DUPLICATE: 'This exact hostname is already present.',
      FIREWALL_DOMAIN_LIMIT_EXCEEDED: 'The allowed-domain limit has been exceeded.',
      FIREWALL_ALLOWLIST_EMPTY: 'Allow specified domains requires at least one allowed domain.',
      FIREWALL_DOMAINS_NOT_ALLOWED: 'Allowed domains must be empty unless external network access uses Allow specified domains.',
      FIREWALL_RETRY_NOT_ALLOWED: 'This firewall revision can no longer be retried. Reload the latest status.',
      CILIUM_NOT_ENABLED: 'Cilium is not enabled on this platform.',
      FIREWALL_CILIUM_ENDPOINT_DISCOVERY_FAILED: 'The platform could not inspect Cilium endpoints for firewall enforcement.',
      FIREWALL_POLICY_APPLY_FAILED: 'The platform could not create or update the Cilium firewall policy.',
      FIREWALL_POLICY_ENFORCEMENT_TIMEOUT: 'Cilium did not confirm firewall policy enforcement before the timeout.',
      FIREWALL_POLICY_REJECTED: 'Cilium rejected the firewall policy.',
      FIREWALL_POLICY_STATUS_INVALID: 'Cilium returned an invalid firewall policy status.',
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
        title: 'Workspace Runtime network rules',
        description: 'Controls external access for the Runtime execution group independently from Browser.',
      },
      browser: {
        title: 'Browser network rules',
        description: 'Controls external access for Browser independently from Workspace Runtime.',
      },
    },
    egressMode: {
      label: 'External network access',
      options: {
        blocked: {
          label: 'Block external network',
          description: 'Deny all external connections while retaining DNS resolution',
        },
        allowlist: {
          label: 'Allow specified domains',
          description: 'Only allow external connections to the configured domains',
        },
        unrestricted: {
          label: 'Allow all external network',
          description: 'Allow external connections without domain restrictions',
        },
      },
    },
    allowedDomains: {
      label: 'Allowed Domains',
      placeholder: 'Enter a domain, e.g. example.com',
      add: 'Add allowed domain',
      remove: 'Remove {{domain}}',
      exactHostnameHint: 'Exact hostnames only. Wildcards and implicit subdomains are not allowed.',
      invalid: 'Enter one canonical exact hostname without a wildcard, URL, path, port, or IP address.',
      duplicate: 'This exact hostname is already present.',
      required: 'Allow specified domains requires at least one allowed domain.',
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
      scrollLeft: 'Scroll terminal tabs left',
      scrollRight: 'Scroll terminal tabs right',
    },
    theme: {
      label: 'Terminal theme',
      options: {
        light: 'Light terminal',
        dark: 'Dark terminal',
      },
    },
    menus: {
      actions: 'Actions',
      context: {
        clear: 'Clear',
        close: 'Close terminal',
        unassign: 'Unassign',
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
      syncing: 'Syncing terminal sessions...',
      replayReset: 'Terminal screen was reset after reconnect',
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
