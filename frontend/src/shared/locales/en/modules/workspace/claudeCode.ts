const claudeCode = {
  documents: {
    meta: {
      'slash-commands': { title: 'Slash command settings' },
      'output-styles': { title: 'Output style settings' },
      subagents: { title: 'Subagent settings' },
      memory: { title: 'Memory settings' },
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
  slashCommands: {
    pageTitle: 'Slash command settings',
    actions: {
      create: 'Add slash command',
    },
    empty: {
      title: 'No slash commands yet',
      description: 'Select or create a command from the left to configure Claude\'s behavior.',
    },
    dialog: {
      title: {
        create: 'Add slash command',
        edit: 'Edit slash command',
      },
      description: {
        create: 'Create a custom slash command for Claude.',
        edit: 'Update the settings and content of this command.',
      },
      tabs: {
        basic: 'Basic settings',
        editor: 'Content editor',
      },
      fields: {
        scope: {
          label: 'Scope',
        },
        identifier: {
          label: 'Command name',
          placeholder: 'Enter command name',
          helper: 'Command names must be unique. Use letters, numbers, or hyphens.',
        },
        title: {
          label: 'Display title',
          placeholder: 'Enter display title',
        },
        fileName: {
          label: 'File name',
          placeholder: 'Enter file name',
        },
        namespace: {
          label: 'Namespace',
          placeholder: 'Optional namespace',
          helper: 'Organize related commands with namespaces.',
        },
        description: {
          label: 'Description',
          placeholder: 'Optional description',
          helper: 'Briefly describe what this command does.',
        },
        content: {
          label: 'Command content',
          estimatedSize: 'Estimated size: {{size}}',
        },
      },
      validation: {
        identifier: 'Please enter a command name.',
        title: 'Please enter a title.',
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
  outputStyles: {
    pageTitle: 'Output style settings',
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
  subagents: {
    pageTitle: 'Subagent settings',
    actions: {
      create: 'Add subagent',
    },
    empty: {
      title: 'No subagents yet',
      description: 'Create specialized subagents to collaborate on tasks.',
    },
    dialog: {
      title: {
        create: 'Add subagent',
        edit: 'Edit subagent',
      },
      description: {
        create: 'Configure a new subagent to assist the team.',
        edit: 'Update the details of this subagent.',
      },
      fields: {
        scope: {
          label: 'Scope',
        },
        identifier: {
          label: 'Subagent ID',
          placeholder: 'Enter subagent ID',
          helper: 'IDs must be unique. Letters, numbers, and separators are allowed.',
        },
        title: {
          label: 'Subagent name',
          placeholder: 'Enter subagent name',
        },
        fileName: {
          label: 'File name',
          placeholder: 'Enter file name',
        },
        description: {
          label: 'Description',
          placeholder: 'Optional description',
        },
        content: {
          label: 'Subagent description',
          estimatedSize: 'Estimated size: {{size}}',
          helper: 'Describe the subagent\'s behavior, tools, and expertise.',
        },
      },
      validation: {
        identifier: 'Please enter a subagent ID.',
        title: 'Please enter a subagent name.',
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
  skills: {
    header: {
      title: 'Skill library preview',
      description: 'Browse structured examples of Claude skills and integrations.',
      count: '{{count}} files',
    },
    searchPlaceholder: 'Search skills or files',
    emptySearch: 'No skill files match the current filter.',
    empty: 'No sample skills are available.',
    noSelection: 'Select a skill file from the list to preview its content.',
    emptyFile: 'This skill file is currently empty.',
    sidebar: {
      placeholder: 'The skill tree is now displayed in the main panel.',
    },
    scope: {
      label: 'Scope:',
      project: 'Project',
      user: 'User',
      plugin: 'Plugin',
    },
    plugin: {
      label: 'Plugin:',
      all: 'All Plugins',
    },
    tree: {
      header: {
        title: 'Skill files',
      },
      actions: {
        multiSelect: {
          enable: 'Enable multi-select',
          disable: 'Disable multi-select',
        },
        refresh: 'Refresh',
      },
      multiSelect: {
        summary: '{{count}} skill file(s) selected',
        selectAll: 'Select all',
        unselectAll: 'Clear selection',
        download: 'Download ({{count}})',
      },
      status: {
        selected: '{{count}} item(s) selected',
        clearSelection: 'Clear selection',
      },
    },
    actions: {
      edit: 'Edit',
      save: 'Save',
      cancel: 'Cancel',
      copy: {
        success: 'Copied',
        description: 'File content copied to clipboard',
        error: 'Copy failed',
        errorDescription: 'Unable to copy file content',
      },
      download: {
        success: 'Download successful',
        description: 'File downloaded',
      },
      saveInfo: {
        info: 'Save function',
        description: 'This is sample data, saving is not supported',
      },
    },
    editor: {
      markdownPlaceholder: 'Enter Markdown content...',
    },
    fileOperations: {
      uploadFailed: 'Upload failed',
      pasteFileFailed: 'Paste file failed',
      renamePrompt: 'Rename {{name}}:',
      renameFailed: 'Rename failed',
      renameFailedAlert: 'Rename failed, please try again later',
      refreshFailed: 'Refresh failed',
      createFileFailed: 'Create file failed',
      createFolderFailed: 'Create folder failed',
      deleteFailed: 'Delete failed',
      batchDeleteFailed: 'Batch delete failed',
      moveFolderToSubfolderAlert: 'Cannot move a folder into itself or its own subfolder',
      moveFailed: 'Move file failed',
      moveFailedAlert: 'Move file failed, please try again later',
      pasteStarted: 'Paste operation started',
      pasteTargetPath: 'Target path',
      pasteCallApi: 'Calling copy API',
      pasteSuccess: 'Copy successful, reloading file tree',
      pasteTreeReloaded: 'File tree reloaded',
      pasteFailed: 'Paste failed',
      pasteFailedAlert: 'Paste failed, please try again later',
      pathCopied: 'Path copied',
      copyPathFailed: 'Copy path failed',
    },
  },

  scripts: {
    header: {
      title: 'Script library preview',
      description: 'Browse structured examples of Claude scripts and integrations.',
      count: '{{count}} files',
      refresh: 'Refresh',
      refreshing: 'Loading...',
    },
    searchPlaceholder: 'Search scripts or files',
    emptySearch: 'No script files match the current filter.',
    empty: 'No sample scripts are available.',
    noSelection: 'Select a script file from the list to preview its content.',
    emptyFile: 'This script file is currently empty.',
    sidebar: {
      placeholder: 'The script tree is now displayed in the main panel.',
    },
    scope: {
      label: 'Scope:',
      project: 'Project',
      user: 'User',
    },
    tree: {
      header: {
        title: 'Scripts',
      },
      actions: {
        multiSelect: {
          enable: 'Enable multi-select',
          disable: 'Disable multi-select',
        },
        refresh: 'Refresh',
      },
      multiSelect: {
        summary: '{{count}} script file(s) selected',
        selectAll: 'Select all',
        unselectAll: 'Clear selection',
        download: 'Download ({{count}})',
      },
      status: {
        selected: '{{count}} item(s) selected',
        clearSelection: 'Clear selection',
      },
    },
    actions: {
      edit: 'Edit',
      save: 'Save',
      cancel: 'Cancel',
      copy: {
        success: 'Copied',
        description: 'File content copied to clipboard',
        error: 'Copy failed',
        errorDescription: 'Unable to copy file content',
      },
      download: {
        success: 'Download successful',
        description: 'File downloaded',
      },
      saveInfo: {
        info: 'Save function',
        description: 'This is sample data, saving is not supported',
      },
    },
    notifications: {
      loadFailed: 'Failed to load file',
      saveSuccess: 'Save successful',
      saveSuccessDescription: 'File saved successfully',
      saveFailed: 'Save failed',
      copied: 'Copied',
      copiedDescription: 'Content copied to clipboard',
      copyFailed: 'Copy failed',
      downloaded: 'Downloaded',
      downloadedDescription: 'File downloaded',
    },
    editor: {
      markdownPlaceholder: 'Enter Markdown content...',
    },
    fileOperations: {
      uploadFailed: 'Upload failed',
      pasteFileFailed: 'Paste file failed',
      renamePrompt: 'Rename {{name}}:',
      renameFailed: 'Rename failed',
      renameFailedAlert: 'Rename failed, please try again later',
      refreshFailed: 'Refresh failed',
      createFileFailed: 'Create file failed',
      createFolderFailed: 'Create folder failed',
      deleteFailed: 'Delete failed',
      batchDeleteFailed: 'Batch delete failed',
      moveFolderToSubfolderAlert: 'Cannot move a folder into itself or its own subfolder',
      moveFailed: 'Move file failed',
      moveFailedAlert: 'Move file failed, please try again later',
      pasteStarted: 'Paste operation started',
      pasteTargetPath: 'Target path',
      pasteCallApi: 'Calling copy API',
      pasteSuccess: 'Copy successful, reloading file tree',
      pasteTreeReloaded: 'File tree reloaded',
      pasteFailed: 'Paste failed',
      pasteFailedAlert: 'Paste failed, please try again later',
      pathCopied: 'Path copied',
      copyPathFailed: 'Copy path failed',
    },
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
  agentsMd: {
    scope: { label: 'Scope' },
    actions: { save: 'Save settings', refresh: 'Reload' },
    status: {
      runtimeLoading: 'Workspace runtime is initializing...',
      runtimeMissing: 'Workspace runtime endpoint is not available yet. Please try again shortly.',
      runtimeUnavailable: 'Workspace runtime is unavailable: {{message}}',
      loading: 'Loading {{fileName}}...',
      fallbackNotice: 'You are viewing the default template. Save to create a new {{fileName}}.',
    },
    notifications: {
      saveSuccess: {
        title: '{{fileName}} saved',
        description: 'Content synced to the workspace runtime successfully.',
      },
      saveFailed: {
        title: 'Failed to save {{fileName}}',
        description: 'Please try again or verify the workspace runtime status.',
      },
      loadFailed: {
        title: 'Failed to load {{fileName}}',
        description: 'Unable to load the configuration file. Using the default template.',
      },
      runtimeUnavailable: {
        title: 'Workspace runtime not ready',
        description: 'Check the runtime status and try again.',
      },
    },
    confirmDiscard: 'You have unsaved changes. Discard them?',
    footer: { scope: 'Scope: {{scope}}' },
  },
  mcp: {
    header: {
      title: 'Model Context Protocol settings',
      actions: {
        import: 'Import config',
        create: 'Add server',
      },
    },
    stats: {
      title: 'Overview',
      total: '{{count}} server(s)',
      running: '{{count}} running',
      stopped: '{{count}} stopped',
    },
    search: {
      placeholder: 'Search servers...',
    },
    server: {
      status: {
        running: 'Running',
        stopped: 'Stopped',
        error: 'Error',
      },
      scope: {
        label: 'Scope',
        all: 'All',
        project: 'Project',
        user: 'User',
        local: 'Local',
        plugin: 'Plugin',
      },
    },
    serverDetails: {
      transportType: 'Transport',
      serverUrl: 'Server URL',
      command: 'Command',
      commandArgs: 'Arguments',
      env: 'Environment variables',
      headers: 'HTTP Headers',
    },
    list: {
      empty: 'No MCP servers match the current filters.',
    },
    import: {
      descriptionFromJson: 'Server imported from JSON',
    },
    dialogs: {
      server: {
        title: {
          create: 'Add MCP server',
          edit: 'Edit MCP server',
        },
        description: 'Configure MCP server connection settings.',
        fields: {
          name: {
            label: 'Server name *',
            placeholder: 'e.g. filesystem',
            hint: 'Only letters, numbers, underscores, and hyphens are allowed',
          },
          scope: {
            label: 'Scope *',
            options: {
              project: {
                title: 'Project',
                description: 'Workspace-level configuration',
              },
              user: {
                title: 'User',
                description: 'User-level configuration',
              },
              local: {
                title: 'Local',
                description: 'Local-only configuration',
              },
            },
          },
          transport: {
            label: 'Transport *',
            options: {
              stdio: {
                title: 'Stdio (standard input/output)',
                description: 'Execute via command line',
              },
              sse: {
                title: 'SSE (Server-Sent Events)',
                description: 'Connect through server-sent events',
              },
              http: {
                title: 'Streamable HTTP',
                description: 'Connect through HTTP API',
              },
            },
          },
          command: {
            label: 'Command *',
            placeholder: 'e.g. npx',
          },
          commandArgs: {
            label: 'Command arguments',
            add: 'Add argument',
            placeholder: 'Argument {{index}}',
            empty: 'No command arguments',
          },
          url: {
            label: 'Server URL *',
            placeholder: {
              sse: 'e.g. https://api.example.com/sse',
              http: 'e.g. https://api.example.com/mcp',
            },
            hint: {
              sse: 'Full SSE endpoint URL',
              http: 'Full HTTP/HTTPS URL',
            },
          },
          env: {
            label: 'Environment variables',
            add: 'Add variable',
            keyPlaceholder: 'Variable name',
            valuePlaceholder: 'Variable value',
            empty: 'No environment variables',
          },
          headers: {
            label: 'HTTP Headers',
            add: 'Add header',
            keyPlaceholder: 'Header name',
            valuePlaceholder: 'Header value',
            empty: 'No HTTP headers',
          },
        },
        actions: {
          create: 'Add server',
          save: 'Save changes',
        },
      },
      import: {
        title: 'Upload Claude Desktop Configuration File',
        description: 'Import existing MCP server configurations to current workspace',
        info: {
          upload: 'Please upload Claude Desktop configuration file',
          description: 'to import existing MCP server configurations.'
        },
        fields: {
          file: {
            label: 'Select configuration file',
            dragText: 'Drag files here or click to select',
            formatInfo: 'Supports JSON format, max 5MB'
          },
          scope: {
            label: 'Import scope',
            helper: 'Choose the scope where imported server configurations will be saved'
          }
        },
        progress: {
          importing: 'Importing configuration from Claude Desktop...'
        },
        result: {
          title: 'Import result',
          success: 'Successfully imported',
          failed: 'Import failed',
          successRate: 'Success rate',
          details: 'Detailed results',
          noServers: 'No importable MCP server configurations found. Please ensure the Claude Desktop configuration file exists and contains MCP server configurations.'
        },
        warning: {
          title: 'Note',
          message: 'If a server name already exists, that server will be skipped during import.'
        },
        errors: {
          invalidFile: 'Please select a JSON format configuration file',
          fileTooLarge: 'File size cannot exceed 5MB',
          fileReadError: 'File read failed',
          noFile: 'Please select a configuration file first'
        },
        actions: {
          removeFile: 'Remove file',
          startImport: 'Start import',
          importing: 'Importing...',
          confirm: 'Import server'
        },
        tabs: {
          form: 'Create from form',
          json: 'JSON configuration',
        },
        form: {
          fields: {
            name: {
              label: 'Server name *',
              placeholder: 'e.g. filesystem',
            },
            scope: {
              label: 'Scope *',
            },
            command: {
              label: 'Command *',
              placeholder: 'e.g. npx @modelcontextprotocol/server-filesystem',
            },
            args: {
              label: 'Command arguments',
              placeholder: 'Separate arguments with spaces',
            },
          },
        },
        json: {
          fields: {
            name: {
              label: 'Server name *',
              placeholder: 'e.g. filesystem',
            },
            scope: {
              label: 'Scope *',
            },
            config: {
              label: 'JSON configuration *',
            },
          },
          helper:
            'The configuration will be imported as JSON. Ensure it matches the Model Context Protocol server schema.',
        },
      },
    },
  },
  hooks: {
    header: {
      title: 'Hooks settings',
    },
    filters: {
      scope: {
        label: 'Scope',
        placeholder: 'Select scope',
        options: {
          all: 'All scopes',
          project: 'Project',
          user: 'User',
          local: 'Local',
          plugin: 'Plugin',
        },
      },
    },
    actions: {
      refresh: 'Refresh',
      create: 'Add hook',
      edit: 'Edit hook',
      delete: 'Remove hook',
    },
    stats: {
      title: 'Overview',
      hooks: '{{count}} hook(s)',
    },
    search: {
      placeholder: 'Search hooks...',
    },
    scope: {
      badge: {
        project: 'Project',
        user: 'User',
        local: 'Local',
        plugin: 'Plugin',
      },
    },
    events: {
      PreToolUse: {
        name: 'PreToolUse: Runs before tool calls (can block them)',
        option: 'PreToolUse: Run before tool invocation (can cancel execution)',
      },
      PostToolUse: {
        name: 'PostToolUse: Runs after tool calls complete',
        option: 'PostToolUse: Run after tool invocation completes',
      },
      UserPromptSubmit: {
        name: 'UserPromptSubmit: Runs when the user submits a prompt, before Claude processes it',
        option: 'UserPromptSubmit: Run when the user submits a prompt before Claude processes it',
      },
      Notification: {
        name: 'Notification: Runs when Claude Code sends notifications',
        option: 'Notification: Run when Claude Code sends a notification',
      },
      Stop: {
        name: 'Stop: Runs when Claude Code finishes responding',
        option: 'Stop: Run when Claude Code finishes responding',
      },
      SubagentStop: {
        name: 'SubagentStop: Runs when subagent tasks complete',
        option: 'SubagentStop: Run when a subagent task completes',
      },
      PreCompact: {
        name: 'PreCompact: Runs before Claude Code is about to run a compact operation',
        option: 'PreCompact: Run before Claude Code performs a compact operation',
      },
      SessionStart: {
        name: 'SessionStart: Runs when Claude Code starts a new session or resumes an existing session',
        option: 'SessionStart: Run when a session starts or resumes',
      },
      SessionEnd: {
        name: 'SessionEnd: Runs when Claude Code session ends',
        option: 'SessionEnd: Run when a session ends',
      },
    },
    matchers: {
      title: 'Matcher configuration',
      matcherLabel: 'Matcher',
      actionsCount: '{{count}} action(s)',
      commandLabel: 'Command',
      timeoutValue: '{{value}}s',
      noCommand: 'No command provided',
      moreActions: '{{count}} more action(s)...',
      summary: {
        matchers: '{{count}} matcher(s)',
        commands: '{{count}} action(s)',
      },
    },
    list: {
      empty: 'No hooks match the current filters.',
    },
    dialog: {
      title: {
        edit: 'Edit hook',
        create: 'Add hook',
      },
      description: 'Configure hook scope, trigger events, and execution commands.',
      scope: {
        label: 'Scope',
        labelWithAsterisk: 'Scope *',
        placeholder: 'Choose scope',
        options: {
          project: 'Project',
          user: 'User',
          local: 'Local',
        },
      },
      event: {
        label: 'Event type *',
        placeholder: 'Choose event',
      },
      matcher: {
        sectionTitle: 'Matcher configuration',
        add: 'Add matcher',
        patternLabel: 'Match pattern',
        patternPlaceholder: 'Tool name pattern (e.g. Write|Edit or * for all)',
        helper: {
          intro: 'Pattern for matching tool names (case sensitive for PostToolUse)',
          simple: '• Simple string: Write matches only the Write tool',
          regex: '• Regular expression: Edit|Write or Notebook.*',
          wildcard: '• * matches all tools; empty string is also allowed',
        },
        remove: 'Remove matcher',
      },
      execution: {
        sectionTitle: 'Hook execution',
        add: 'Add action',
        timeoutLabel: 'Timeout (seconds)',
        timeoutPlaceholder: '30',
        timeoutHelp: 'Maximum command execution time. Commands are cancelled when exceeding the limit.',
        commandLabel: 'Command *',
        commandPlaceholder: 'Enter the command to execute',
        commandHelp: 'Environment variables such as $CLAUDE_PROJECT_DIR are supported.',
        remove: 'Remove action',
      },
      actions: {
        cancel: 'Cancel',
        save: 'Save changes',
        create: 'Add hook',
      },
      validation: {
        invalidHook: 'Each matcher requires at least one valid hook configuration.',
        duplicateEvent: 'This event type already exists. Please edit the existing hook or choose a different event type.',
        duplicateEventWarning: 'Duplicate event type detected',
        duplicateEventSuggestion: 'Consider editing the existing hook instead of creating a duplicate event.',
      },
    },
  },
  memory: {
    pageTitle: 'Memory settings',
    actions: {
      create: 'Add memory file',
    },
    empty: {
      title: 'No memory files yet',
      description: 'Create or select a Memory file from the left to browse and edit Claude Memory content.',
    },
    dialog: {
      title: {
        create: 'Add memory file',
        edit: 'Edit memory file',
      },
      description: {
        create: 'Create a new Claude Memory markdown file.',
        edit: 'Update the content of an existing Claude Memory markdown file.',
      },
      fields: {
        fileName: {
          label: 'File name',
          placeholder: 'Enter file name',
          helper: 'Only single-level Markdown files are supported. The .md extension is added automatically.',
        },
        content: {
          label: 'Memory content',
          estimatedSize: 'Estimated size: {{size}}',
        },
      },
      validation: {
        fileName: 'Please enter a file name.',
        content: 'Content cannot be empty.',
      },
      actions: {
        cancel: 'Cancel',
        save: 'Save changes',
        create: 'Create file',
      },
    },
  },
};

export default claudeCode;
