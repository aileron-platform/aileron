const agentSettings = {
  claude: {
    agentsMd: 'CLAUDE.md',
    hooks: {
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
    },
  },
  gemini: {
    instructionFile: 'GEMINI.md',
    hooks: {
      events: {
        BeforeTool: {
          name: 'BeforeTool: Runs before tool execution',
          option: 'BeforeTool: Run before tool execution',
        },
        AfterTool: {
          name: 'AfterTool: Runs after tool execution',
          option: 'AfterTool: Run after tool execution',
        },
        BeforeAgent: {
          name: 'BeforeAgent: Runs before agent processing',
          option: 'BeforeAgent: Run before agent processing',
        },
        AfterAgent: {
          name: 'AfterAgent: Runs after agent processing',
          option: 'AfterAgent: Run after agent processing',
        },
        BeforeModel: {
          name: 'BeforeModel: Runs before model invocation',
          option: 'BeforeModel: Run before model invocation',
        },
        AfterModel: {
          name: 'AfterModel: Runs after model response',
          option: 'AfterModel: Run after model response',
        },
        BeforeToolSelection: {
          name: 'BeforeToolSelection: Runs before tool selection',
          option: 'BeforeToolSelection: Run before tool selection',
        },
        SessionStart: {
          name: 'SessionStart: Runs when session starts',
          option: 'SessionStart: Run when session starts',
        },
        SessionEnd: {
          name: 'SessionEnd: Runs when session ends',
          option: 'SessionEnd: Run when session ends',
        },
        PreCompress: {
          name: 'PreCompress: Runs before history compression',
          option: 'PreCompress: Run before history compression',
        },
        Notification: {
          name: 'Notification: Runs on notification',
          option: 'Notification: Run on notification',
        },
      },
    },
  },
  opencode: {
    agentsMd: 'AGENTS.md',
  },
  codex: {
    agentsMd: 'AGENTS.md',
  },
  common: {
    loading: 'Loading...',
    subViews: {
      geminiMd: 'GEMINI.md',
      agentsMd: 'AGENTS.md',
      mcp: 'Model Context Protocol',
      hooks: 'Hooks',
      slashCommands: 'Slash Commands',
      skills: 'Skills',
    },
    scope: {
      project: 'Project',
      user: 'User',
      global: 'Global',
    },
    comingSoon: {
      title: 'Coming Soon',
      description: '{{feature}} will be available for {{toolName}} soon.',
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
        staleTemplate: 'Template installation updated this file externally. Your unsaved content has not been overwritten; refresh to load the latest version.',
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
        templateUpdated: {
          description: 'Template installation updated this file. Your unsaved content is preserved; save it or refresh manually to load the latest version.',
        },
      },
      confirmDiscard: 'You have unsaved changes. Discard them?',
      footer: { scope: 'Scope: {{scope}}' },
    },
    hooks: {
      header: { title: 'Hooks settings' },
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
      stats: { title: 'Overview', hooks: '{{count}} hook(s)' },
      search: { placeholder: 'Search hooks...' },
      scope: {
        badge: {
          project: 'Project',
          user: 'User',
          local: 'Local',
          plugin: 'Plugin',
        },
      },
      events: {
        PreToolUse: { name: 'PreToolUse', option: 'PreToolUse' },
        PostToolUse: { name: 'PostToolUse', option: 'PostToolUse' },
        UserPromptSubmit: { name: 'UserPromptSubmit', option: 'UserPromptSubmit' },
        Notification: { name: 'Notification', option: 'Notification' },
        Stop: { name: 'Stop', option: 'Stop' },
        SubagentStop: { name: 'SubagentStop', option: 'SubagentStop' },
        PreCompact: { name: 'PreCompact', option: 'PreCompact' },
        SessionStart: { name: 'SessionStart', option: 'SessionStart' },
        SessionEnd: { name: 'SessionEnd', option: 'SessionEnd' },
      },
      matchers: {
        title: 'Matcher configuration',
        matcherLabel: 'Matcher',
        actionsCount: '{{count}} action(s)',
        commandLabel: 'Command',
        timeoutValue: '{{value}}s',
        noCommand: 'No command provided',
        moreActions: '{{count}} more action(s)...',
        summary: { matchers: '{{count}} matcher(s)', commands: '{{count}} action(s)' },
      },
      list: { empty: 'No hooks match the current filters.' },
      messages: {
        loadFailed: 'Failed to load hook settings.',
        updateFailed: 'Failed to update hook settings.',
        deleteFailed: 'Failed to delete hook.',
      },
      dialog: {
        title: { edit: 'Edit hook', create: 'Add hook' },
        description: 'Configure hook scope, trigger events, and execution commands.',
        scope: {
          label: 'Scope',
          labelWithAsterisk: 'Scope *',
          placeholder: 'Choose scope',
          options: { project: 'Project', user: 'User', local: 'Local' },
        },
        event: { label: 'Event type *', placeholder: 'Choose event' },
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
        actions: { cancel: 'Cancel', save: 'Save changes', create: 'Add hook' },
        validation: {
          invalidHook: 'Each matcher requires at least one valid hook configuration.',
          duplicateEvent: 'This event type already exists. Please edit the existing hook or choose a different event type.',
          duplicateEventWarning: 'Duplicate event type detected',
          duplicateEventSuggestion: 'Consider editing the existing hook instead of creating a duplicate event.',
        },
      },
    },
    mcp: {
      header: {
        title: 'Model Context Protocol settings',
        actions: { import: 'Import config', create: 'Add server' },
      },
      stats: {
        title: 'Overview',
        total: '{{count}} server(s)',
        running: '{{count}} running',
        stopped: '{{count}} stopped',
      },
      search: { placeholder: 'Search servers...' },
      server: {
        status: { running: 'Running', stopped: 'Stopped', error: 'Error', enabled: 'Enabled', disabled: 'Disabled' },
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
      list: { empty: 'No MCP servers match the current filters.', loading: 'Loading MCP servers...' },
      status: { runtimeUnavailable: 'Workspace runtime is unavailable: {{message}}' },
      actions: { showEnvValues: 'Show values', hideEnvValues: 'Hide values' },
      plugin: { readonly: 'Plugin managed' },
      confirm: { delete: 'Delete MCP server "{{name}}"?' },
      messages: {
        runtimeNotReady: 'Workspace runtime is not ready.',
        loadFailed: {
          title: 'Failed to load MCP servers',
          description: 'Unable to load MCP server settings.',
        },
        editForbidden: {
          title: 'Plugin server is read-only',
          description: 'Plugin-managed MCP servers cannot be edited here.',
        },
        deleteForbidden: {
          title: 'Plugin server is read-only',
          description: 'Plugin-managed MCP servers cannot be deleted here.',
        },
        createSuccess: { title: 'MCP server created' },
        updateSuccess: { title: 'MCP server updated' },
        deleteSuccess: { title: 'MCP server deleted' },
        operationFailed: {
          title: 'MCP operation failed',
          description: 'The MCP server operation failed.',
        },
        deleteFailed: {
          title: 'Failed to delete MCP server',
          description: 'Unable to delete MCP server.',
        },
        toggleEnabled: { title: 'MCP server enabled' },
        toggleDisabled: { title: 'MCP server disabled' },
        toggleFailed: { description: 'Unable to update MCP server status.' },
        importSuccess: {
          title: 'MCP servers imported',
          description: 'Imported {{created}} created, {{updated}} updated, {{skipped}} skipped.',
        },
        importFailed: {
          title: 'MCP import failed',
          description: 'Unable to import MCP server configuration.',
        },
      },
      import: { descriptionFromJson: 'Server imported from JSON' },
      dialogs: {
        server: {
          title: { create: 'Add MCP server', edit: 'Edit MCP server' },
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
                project: { title: 'Project', description: 'Workspace-level configuration' },
                user: { title: 'User', description: 'User-level configuration' },
                local: { title: 'Local', description: 'Local-only configuration' },
              },
            },
            transport: {
              label: 'Transport *',
              options: {
                stdio: { title: 'Stdio (standard input/output)', description: 'Execute via command line' },
                sse: { title: 'SSE (Server-Sent Events)', description: 'Connect through server-sent events' },
                http: { title: 'Streamable HTTP', description: 'Connect through HTTP API' },
              },
            },
            command: { label: 'Command *', placeholder: 'e.g. npx' },
            commandArgs: {
              label: 'Command arguments',
              add: 'Add argument',
              placeholder: 'Argument {{index}}',
              empty: 'No command arguments',
            },
            url: {
              label: 'Server URL *',
              placeholder: { sse: 'e.g. https://api.example.com/sse', http: 'e.g. https://api.example.com/mcp' },
              hint: { sse: 'Full SSE endpoint URL', http: 'Full HTTP/HTTPS URL' },
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
          actions: { create: 'Add server', save: 'Save changes' },
        },
        import: {
          title: 'Upload Configuration File',
          description: 'Import existing MCP server configurations to current workspace',
          info: { upload: 'Please upload configuration file', description: 'to import existing MCP server configurations.' },
          fields: {
            file: { label: 'Select configuration file', dragText: 'Drag files here or click to select', formatInfo: 'Supports JSON format, max 5MB' },
            scope: { label: 'Import scope', helper: 'Choose the scope where imported server configurations will be saved' },
          },
          progress: { importing: 'Importing configuration...' },
          result: {
            title: 'Import result',
            success: 'Successfully imported',
            failed: 'Import failed',
            successRate: 'Success rate',
            details: 'Detailed results',
            noServers: 'No importable MCP server configurations found. Please ensure the configuration file exists and contains MCP server configurations.',
          },
          warning: { title: 'Note', message: 'If a server name already exists, that server will be skipped during import.' },
          errors: { invalidFile: 'Please select a JSON format configuration file', fileTooLarge: 'File size cannot exceed 5MB', fileReadError: 'File read failed', noFile: 'Please select a configuration file first' },
          actions: { removeFile: 'Remove file', startImport: 'Start import', importing: 'Importing...', confirm: 'Import server' },
          tabs: { form: 'Create from form', json: 'JSON configuration' },
          form: {
            fields: {
              name: { label: 'Server name *', placeholder: 'e.g. filesystem' },
              scope: { label: 'Scope *' },
              command: { label: 'Command *', placeholder: 'e.g. npx @modelcontextprotocol/server-filesystem' },
              args: { label: 'Command arguments', placeholder: 'Separate arguments with spaces' },
            },
          },
          json: {
            fields: {
              name: { label: 'Server name *', placeholder: 'e.g. filesystem' },
              scope: { label: 'Scope *' },
              config: { label: 'JSON configuration *' },
            },
            helper: 'The configuration will be imported as JSON. Ensure it matches the Model Context Protocol server schema.',
          },
        },
      },
    },
    slashCommands: {
      pageTitle: 'Slash command settings',
      actions: { create: 'Add slash command' },
      empty: {
        title: 'No slash commands yet',
        description: 'Select or create a command from the left to get started.',
      },
      dialog: {
        title: { create: 'Add slash command', edit: 'Edit slash command' },
        description: { create: 'Create a custom slash command.', edit: 'Update the settings and content of this command.' },
        tabs: { basic: 'Basic settings', editor: 'Content editor' },
        fields: {
          scope: { label: 'Scope' },
          identifier: { label: 'Command name', placeholder: 'Enter command name', helper: 'Command names must be unique. Use letters, numbers, or hyphens.' },
          title: { label: 'Display title', placeholder: 'Enter display title' },
          fileName: { label: 'File name', placeholder: 'Enter file name' },
          namespace: { label: 'Namespace', placeholder: 'Optional namespace', helper: 'Organize related commands with namespaces.' },
          description: { label: 'Description', placeholder: 'Optional description', helper: 'Briefly describe what this command does.' },
          content: { label: 'Command content', estimatedSize: 'Estimated size: {{size}}' },
        },
        validation: { identifier: 'Please enter a command name.', title: 'Please enter a title.', fileName: 'Please enter a file name.', content: 'Content cannot be empty.' },
        actions: { cancel: 'Cancel', save: 'Save changes', create: 'Create item' },
      },
    },
    skills: {
      header: { title: 'Editor', description: 'Browse files.', count: '{{count}} files' },
      noSelection: 'Select a skill file from the list to preview its content.',
      title: 'Skills',
      searchPlaceholder: 'Search skills or files',
      scope: { label: 'Scope', project: 'Project', user: 'User', plugin: 'Plugin' },
      plugin: { label: 'Plugin', all: 'All plugins' },
    },
    scripts: {
      header: { title: 'Editor', description: 'Browse scripts.', count: '{{count}} files' },
      noSelection: 'Select a script file from the list to preview its content.',
      title: 'Scripts',
      searchPlaceholder: 'Search scripts or files',
      scope: { label: 'Scope', project: 'Project', user: 'User', plugin: 'Plugin' },
      plugin: { label: 'Plugin', all: 'All plugins' },
    },
    documents: {
      meta: {
        'slash-commands': { title: 'Slash command settings' },
        subagents: { title: 'Subagent settings' },
      },
      actions: { refresh: 'Refresh', edit: 'Edit', copyContent: 'Copy content', download: 'Download', delete: 'Delete' },
      loading: 'Loading documents…',
      stats: { total: '{{count}} item(s)' },
      scope: {
        badge: 'Scope: {{scope}}',
        values: { project: 'Project', user: 'User', local: 'Local', plugin: 'Plugin' },
      },
      size: { badge: 'Size: {{size}}' },
      confirmDelete: 'Are you sure you want to delete "{{title}}"?',
      sidebar: {
        defaultTitle: 'Settings',
        toggle: { expand: 'Expand sidebar', collapse: 'Collapse sidebar' },
        searchPlaceholder: 'Search...',
        scope: { all: 'All scopes' },
        loading: 'Loading items…',
        empty: 'No items match the current filters.',
      },
    },
    subagents: {
      pageTitle: 'Subagent settings',
      actions: { create: 'Add subagent' },
      empty: {
        title: 'No subagents yet',
        description: 'Create specialized subagents to collaborate on tasks.',
      },
      dialog: {
        title: { create: 'Add subagent', edit: 'Edit subagent' },
        description: {
          create: 'Configure a new subagent to assist the team.',
          edit: 'Update the details of this subagent.',
        },
        fields: {
          scope: { label: 'Scope' },
          identifier: {
            label: 'Subagent ID',
            placeholder: 'Enter subagent ID',
            helper: 'IDs must be unique. Letters, numbers, and separators are allowed.',
          },
          title: { label: 'Subagent name', placeholder: 'Enter subagent name' },
          fileName: { label: 'File name', placeholder: 'Enter file name' },
          description: { label: 'Description', placeholder: 'Optional description' },
          content: {
            label: 'Subagent description',
            estimatedSize: 'Estimated size: {{size}}',
            helper: 'Describe the subagent behavior, tools, and expertise.',
          },
        },
        validation: {
          identifier: 'Please enter a subagent ID.',
          title: 'Please enter a subagent name.',
          fileName: 'Please enter a file name.',
          content: 'Content cannot be empty.',
        },
        actions: { cancel: 'Cancel', save: 'Save changes', create: 'Create item' },
      },
    },
  },
};

export default agentSettings;
