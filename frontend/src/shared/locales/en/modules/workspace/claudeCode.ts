const claudeCode = {
  shellRequired: 'Use Claude Code from the workspace shell.',
  unsupportedView: 'Unsupported view.',
  documents: {
    meta: {
      'slash-commands': { title: 'Slash Commands' },
      'output-styles': { title: 'Output Styles' },
      subagents: { title: 'Subagents' },
      memory: { title: 'Memory' },
    },
    actions: {
      refresh: 'Refresh',
      edit: 'Edit',
      copyContent: 'Copy content',
      download: 'Download',
      delete: 'Delete',
    },
    loading: 'Loading documents…',
    stats: {
      total: '{{count}} item(s)',
    },
    scope: {
      badge: 'Scope: {{scope}}',
      values: {
        project: 'Project',
        user: 'User',
        local: 'Local',
        plugin: 'Plugin',
      },
    },
    size: {
      badge: 'Size: {{size}}',
    },
    confirmDelete: 'Are you sure you want to delete "{{title}}"?',
    sidebar: {
      defaultTitle: 'Settings',
      toggle: {
        expand: 'Expand sidebar',
        collapse: 'Collapse sidebar',
      },
      searchPlaceholder: 'Search...',
      scope: {
        all: 'All scopes',
      },
      loading: 'Loading items…',
      empty: 'No items match the current filters.',
    },
  },
  outputStyles: {
    pageTitle: 'Output Styles',
    actions: {
      create: 'Add output style',
    },
    empty: {
      title: 'No output styles yet',
      description: 'Create output styles to reuse consistent formatting.',
    },
    dialog: {
      title: {
        create: 'Add output style',
        edit: 'Edit output style',
      },
      description: {
        create: 'Define a new output style configuration.',
        edit: 'Adjust the existing output style.',
      },
      fields: {
        scope: {
          label: 'Scope',
        },
        title: {
          label: 'Style name',
          placeholder: 'Enter style name',
          helper: 'Style names must be unique. Use letters, numbers, or hyphens.',
        },
        fileName: {
          label: 'File name',
          placeholder: 'Enter file name',
          helper: 'File names must be unique. Use letters, numbers, or hyphens.',
        },
        description: {
          label: 'Description',
          placeholder: 'Optional description',
        },
        content: {
          label: 'Style content',
          estimatedSize: 'Estimated size: {{size}}',
        },
      },
      validation: {
        identifier: 'Please enter a style identifier.',
        title: 'Please enter a style name.',
        fileName: 'Please enter a file name.',
        content: 'Content cannot be empty.',
      },
      actions: {
        cancel: 'Cancel',
        save: 'Save changes',
        create: 'Create item',
      },
    },
  },

  settings: {
    header: {
      title: 'Settings',
    },
    scope: {
      local: 'Local',
      user: 'User',
      project: 'Project',
    },
    actions: {
      refresh: 'Refresh',
      save: 'Save settings',
      saving: 'Saving...',
    },
    dirty: 'Unsaved changes',
    unsavedChangesConfirm: 'Discard unsaved settings changes?',
    parseError: 'The editor contains invalid JSON.',
    saveSuccess: 'Settings saved.',
    saveFailed: 'Unable to save settings.',
  },

  permissions: {
    header: {
      title: 'Basic settings',
    },
    tabs: {
      basic: 'General',
      plugins: 'Plugins',
      rules: 'Rules',
      mcp: 'MCP Settings',
    },
    stats: {
      label: 'Rule overview',
      total: '{{count}} rule(s)',
      allow: '{{count}} allow',
      deny: '{{count}} deny',
    },
    actions: {
      refresh: 'Refresh',
      save: 'Save settings',
      saving: 'Saving...',
    },
    plugins: {
      title: 'Plugin configuration',
      emptyTitle: 'No marketplace installed yet',
      emptyDescription: 'Install a marketplace to enable plugin management.',
      helper: 'Expand a marketplace to browse and enable its plugins.',
      count: '{{count}} plugin(s)',
    },
    rules: {
      title: 'Permission management',
    },
    scope: {
      label: 'Configuration scope',
      options: {
        project: 'Project',
        user: 'User',
        local: 'Local',
      },
    },
    search: {
      placeholder: 'Search rules...',
    },
    modes: {
      title: 'Permission modes',
      fieldLabel: 'Select permission mode',
      default: {
        label: 'Default',
        description: 'Standard behavior - prompt for permission when first using each tool',
      },
      acceptEdits: {
        label: 'Accept Edits',
        description: 'Automatically accept file edit permissions for the conversation',
      },
      plan: {
        label: 'Plan',
        description: 'Plan mode - Claude can analyze but cannot modify files or execute commands',
      },
      bypassPermissions: {
        label: 'Bypass Permissions',
        description: 'Skip all permission prompts (requires secure environment - see warning below)',
      },
    },
    model: {
      title: 'Model configuration',
      label: 'Model override (optional)',
      placeholder: 'e.g. claude-3-sonnet-20240229',
      helper: 'Leave blank to use the default model configured in the Claude SDK.',
    },
    outputStyle: {
      title: 'Output Style',
      label: 'Select output style',
      placeholder: 'None',
      none: 'None',
      helper: 'Choose the default output style for Claude Code, leave empty to use no specific style',
    },
    basic: {
      apiKeyHelper: {
        title: 'Authentication helper',
        description: 'Provide a shell script that returns a one-time API key before each session starts.',
        label: 'API key helper script',
        placeholder: '/bin/generate_temp_api_key.sh',
        helper: 'The script will be executed inside /bin/sh and its stdout will be used as the credential.',
      },
      cleanup: {
        label: 'Chat retention window (days)',
        placeholder: '30',
        helper: 'Older conversations will be removed based on their last activity date. Leave blank to keep the runtime default.',
      },
      modelDescription: 'Define the default reasoning model and output style Claude Code should use when no override is supplied.',
      collaboration: {
        title: 'Collaboration defaults',
      },
      includeCoAuthoredBy: {
        label: 'Append "co-authored-by Claude" to commits',
        description: 'Automatically include the co-authored-by trailer in Git commits and pull requests generated by Claude.',
      },
      disableAllHooks: {
        label: 'Disable all Claude Code hooks',
        description: 'Turn off every configured hook for this scope. Individual hook settings will be preserved but ignored.',
      },
      env: {
        title: 'Session environment variables',
        description: 'Define environment variables that will be injected into every Claude Code execution context.',
        add: 'Add environment variable',
        empty: 'No environment variables configured yet.',
        keyLabel: 'Variable name',
        valueLabel: 'Value',
        keyPlaceholder: 'e.g. NODE_ENV',
        valuePlaceholder: 'e.g. development',
      },
    },
    allowRules: {
      title: 'Allow rules',
      count: '{{count}} rule(s)',
      placeholder: 'Enter allow rule...',
      empty: 'No allow rules yet',
      emptyFiltered: 'No allow rules match the current filters',
    },
    denyRules: {
      title: 'Deny rules',
      count: '{{count}} rule(s)',
      placeholder: 'Enter deny rule...',
      empty: 'No deny rules yet',
      emptyFiltered: 'No deny rules match the current filters',
    },
    askRules: {
      title: 'Ask rules',
      placeholder: 'Enter rule that requires confirmation...',
      empty: 'No ask rules yet',
    },
    directoryRules: {
      title: 'Additional directories',
      placeholder: 'Enter additional directory path...',
      empty: 'No additional directories configured',
    },
    mcp: {
      autoApprove: {
        title: 'Auto-approve project MCP servers',
        description: 'Automatically trust every server defined in the project .mcp.json so teammates do not need to approve them individually.',
        helper: 'Enable only for trusted repositories and keep Git history for auditing.',
      },
      mcpjson: {
        title: '.mcp.json review rules',
        enabled: {
          label: 'Server IDs to auto-approve',
          helper: 'List server names that should always be accepted. Wildcards (for example git-*) are supported.',
          placeholder: 'e.g. github, git-*',
          empty: 'No servers are auto-approved yet.',
        },
        disabled: {
          label: 'Server IDs to auto-reject',
          helper: 'Servers listed here will always be rejected when loading the .mcp.json file.',
          placeholder: 'e.g. filesystem',
          empty: 'No servers are auto-rejected yet.',
        },
      },
      policies: {
        title: 'User configurable MCP servers',
        helper: 'Expose allow/deny policies through managed-settings.json for larger teams or managed environments.',
        allowed: {
          title: 'Allow list',
          placeholder: 'Enter server names users may configure...',
          empty: 'No allow list entries yet.',
        },
        denied: {
          title: 'Deny list',
          placeholder: 'Enter server names that must be blocked...',
          empty: 'No deny list entries yet.',
        },
      },
    },
    status: {
      runtimeLoading: 'Workspace runtime is initializing...',
      runtimeMissing: 'Workspace runtime endpoint is not available yet. Please try again shortly.',
      runtimeUnavailable: 'Workspace runtime is unavailable: {{message}}',
      loading: 'Loading basic settings...',
      loadFailed: 'Failed to load basic settings. Please try again later.',
    },
    messages: {
      allowExists: 'This allow rule already exists.',
      denyExists: 'This deny rule already exists.',
      askExists: 'This ask rule already exists.',
      directoryExists: 'This directory is already in the list.',
      invalidCleanupPeriod: 'Please enter a non-negative number of days for cleanup.',
      saveSuccess: 'Settings saved successfully.',
      saveError: 'Save failed. Please try again later.',
      mcpJsonServerExists: 'This MCP server ID already exists in the list.',
      mcpAllowedExists: 'Allow list already contains this MCP server.',
      mcpDeniedExists: 'Deny list already contains this MCP server.',
    },
  },
  memory: {
    pageTitle: 'Memory',
    empty: {
      title: 'No memory files yet',
      description: 'Select a memory file to view and edit its content.',
    },
    dialog: {
      title: {
        edit: 'Edit memory file',
      },
      description: {
        edit: 'Update the content of an existing Claude Memory markdown file.',
      },
      fields: {
        fileName: {
          label: 'File name',
          helper: 'Only single-level Markdown files are supported.',
        },
        content: {
          label: 'Memory content',
          estimatedSize: 'Estimated size: {{size}}',
        },
      },
      validation: {
        content: 'Content cannot be empty.',
      },
      actions: {
        cancel: 'Cancel',
        save: 'Save changes',
      },
    },
  },
};

export default claudeCode;
