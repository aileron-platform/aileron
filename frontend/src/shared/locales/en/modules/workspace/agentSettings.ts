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
    common: {
      actions: {
        refresh: 'Refresh',
        save: 'Save',
      },
      layer: 'Layer',
      layers: {
        project: 'Project',
        user: 'Personal',
      },
      empty: 'Not configured',
      errors: {
        loadFailed: 'Unable to load Codex settings.',
      },
    },
    agentsMd: {
      title: 'AGENTS.md',
      confirmDiscard: 'Discard unsaved changes?',
      footer: '{{path}} · {{sizeBytes}} / {{maxBytes}} bytes',
      notifications: {
        saveSuccess: 'AGENTS.md saved',
        saveFailed: 'Unable to save AGENTS.md',
      },
      caveatTitles: {
        override: 'Override file active',
        fallback: 'Fallback instructions active',
        size_limit: 'Instruction size limit',
      },
      caveats: {
        override: '{{path}} takes precedence over AGENTS.md for this project.',
        fallback: '{{path}} is the active fallback instruction source because AGENTS.md is missing.',
        sizeLimit: 'This file is {{sizeBytes}} bytes and the configured limit is {{maxBytes}} bytes.',
      },
    },
    rules: {
      title: 'Rules',
      filesTitle: '.rules files',
      loading: 'Loading rules…',
      empty: {
        title: 'No rules files found',
        description: 'Create a .rules file to control which commands Codex can run outside the sandbox.',
      },
      confirmDelete: 'Are you sure you want to delete "{{title}}"?',
      fileName: 'File: {{fileName}}',
      fileNamePlaceholder: 'default.rules',
      commandPlaceholder: 'Sample command, for example git status',
      defaultContent: 'prefix_rule(\n    pattern = ["git", ["status", "diff", "log"]],\n    decision = "allow",\n    justification = "Read-only git inspection",\n)\n',
      actions: {
        create: 'Add rules file',
        validate: 'Validate',
      },
      dialog: {
        title: { create: 'Add rules file', edit: 'Edit rules file' },
        description: {
          create: 'Create a Codex .rules file for an editable layer.',
          edit: 'Update this Codex .rules file.',
        },
        fields: {
          scope: { label: 'Layer' },
          fileName: {
            label: 'File name',
            helper: 'Use a relative path that ends with .rules.',
          },
          content: {
            label: 'Rules content',
            estimatedSize: 'Estimated size: {{size}}',
          },
        },
        validation: {
          fileName: 'Enter a relative .rules file name without parent traversal.',
          content: 'Rules content cannot be empty.',
        },
        actions: { cancel: 'Cancel', save: 'Save changes', create: 'Create rules file' },
      },
      notifications: {
        saved: 'Rules file saved',
        deleted: 'Rules file deleted',
        saveFailed: 'Unable to save rules file',
        validateFailed: 'Unable to validate rules file',
      },
      validation: {
        valid: 'Validation passed with exit code {{exitCode}}.',
        invalid: 'Validation failed with exit code {{exitCode}}.',
      },
      validationDialog: {
        title: 'Validate rules',
        description: 'Check how this .rules file evaluates a sample command.',
        fields: {
          command: {
            label: 'Sample command',
            helper: 'The command is sent to Codex exec policy validation as arguments.',
          },
        },
        actions: {
          close: 'Close',
          validate: 'Run validation',
        },
      },
    },
    hooks: {
      title: 'Hooks',
      header: { title: 'Hooks' },
      jsonTitle: 'hooks.json',
      loading: 'Loading hooks…',
      featureWarning: {
        title: 'Hooks feature disabled',
        description: 'Codex will not load hooks until features.codex_hooks is enabled for an editable config layer.',
      },
      filters: {
        scope: {
          label: 'Scope',
          options: {
            all: 'All scopes',
            project: 'Project',
            user: 'User',
            plugin: 'Plugin',
            built_in: 'Built-in',
          },
        },
      },
      actions: {
        refresh: 'Refresh',
        create: 'Add hook',
        edit: 'Edit hook',
        delete: 'Remove hook',
        enableFeature: 'Enable codex_hooks',
      },
      stats: { hooks: '{{count}} hook(s)' },
      search: { placeholder: 'Search hooks...' },
      scope: {
        badge: {
          project: 'Project',
          user: 'User',
          plugin: 'Plugin',
          built_in: 'Built-in',
        },
      },
      sources: {
        hooks_json: 'hooks.json',
        inline_config: 'Read-only inline config',
        plugin: 'Read-only plugin',
        built_in: 'Read-only built-in',
        project: 'Read-only project',
        user: 'Read-only personal',
      },
      events: {
        SessionStart: { name: 'SessionStart', option: 'SessionStart' },
        PreToolUse: { name: 'PreToolUse', option: 'PreToolUse' },
        PostToolUse: { name: 'PostToolUse', option: 'PostToolUse' },
        PermissionRequest: { name: 'PermissionRequest', option: 'PermissionRequest' },
        UserPromptSubmit: { name: 'UserPromptSubmit', option: 'UserPromptSubmit' },
        Stop: { name: 'Stop', option: 'Stop' },
      },
      matchers: {
        title: 'Matcher configuration',
        matcherLabel: 'Matcher',
        actionsCount: '{{count}} action(s)',
        commandLabel: 'Command',
        timeoutValue: '{{value}}s',
        statusMessageValue: 'Status: {{value}}',
        noCommand: 'No command provided',
        summary: { matchers: '{{count}} matcher(s)', commands: '{{count}} action(s)' },
      },
      list: { empty: 'No hooks match the current filters.' },
      dialog: {
        title: { edit: 'Edit hook', create: 'Add hook' },
        description: 'Configure Codex hook scope, lifecycle event, matcher, and command.',
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
          patternPlaceholder: 'Tool name pattern or *',
          helper: {
            intro: 'Pattern for matching Codex tool or permission events.',
            simple: '• Simple string: Write matches only the Write tool',
            regex: '• Regular expression: Edit|Write or Notebook.*',
            wildcard: '• * matches all tools; empty string is also allowed',
            ignored: 'Codex ignores matchers for this event.',
            sessionSource: 'Pattern for matching how the Codex session starts.',
            sessionExamples: 'Examples: startup, resume, clear, or startup|resume.',
            toolName: 'Pattern for matching Codex tool names.',
            toolExamples: 'Examples: Bash, apply_patch, Edit, Write, or mcp__filesystem__.*.',
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
          commandHelp: 'Codex runs hook commands from the workspace context.',
          statusMessageLabel: 'Status message',
          statusMessagePlaceholder: 'Checking command',
          statusMessageHelp: 'Optional progress text shown while Codex runs this command hook.',
          remove: 'Remove action',
        },
        actions: { cancel: 'Cancel', save: 'Save changes', create: 'Add hook' },
        validation: {
          duplicateEventWarning: 'Duplicate event type detected',
          duplicateEventSuggestion: 'Consider editing the existing hook instead of creating a duplicate event.',
        },
      },
      notifications: {
        saved: 'hooks.json saved',
        enabled: 'codex_hooks enabled',
        saveFailed: 'Unable to save hooks.json',
        invalidJson: 'hooks.json must be valid JSON',
        loadIncomplete: 'Codex hooks response is missing a scope.',
      },
    },
    plugins: {
      title: 'Plugins',
      empty: 'No local plugins found.',
      enabled: 'Enabled',
      disabled: 'Disabled',
      listed: 'Listed',
      installed: 'Installed',
      installReserved: 'Marketplace install UI is reserved for a later version. This page reads local registry, cache, and config state.',
      actions: {
        enable: 'Enable',
        disable: 'Disable',
      },
      notifications: {
        saved: 'Plugin setting saved',
      },
    },
    files: {
      filesTitle: 'Files',
      empty: 'No files found.',
      pathPlaceholder: 'Relative path',
      actions: {
        newFile: 'New file',
      },
      titles: {
        skills: 'Skills',
        subagents: 'Subagents',
        prompts: 'Prompts',
      },
      sources: {
        user: 'User',
        project: 'Project',
        plugin: 'Plugin',
        built_in: 'Built-in',
      },
      notifications: {
        saved: 'File saved',
        deleted: 'File deleted',
        saveFailed: 'Unable to save file',
      },
    },
    documents: {
      meta: {
        prompts: { title: 'Prompt settings' },
        subagents: { title: 'Subagent settings' },
        rules: { title: 'Rules settings' },
      },
      actions: { refresh: 'Refresh', edit: 'Edit', copyContent: 'Copy content', download: 'Download', delete: 'Delete' },
      loading: 'Loading documents…',
      stats: { total: '{{count}} item(s)' },
      scope: {
        values: { project: 'Project', user: 'Personal', plugin: 'Plugin', built_in: 'Built-in' },
      },
      status: { effective: 'Effective', overridden: 'Overridden' },
      toml: {
        description: 'Description',
        prompt: 'Prompt',
        developerInstructions: 'Developer instructions',
        raw: 'Raw TOML',
      },
      size: { badge: 'Size: {{size}}' },
      confirmDelete: 'Are you sure you want to delete "{{title}}"?',
      sidebar: {
        toggle: { expand: 'Expand sidebar', collapse: 'Collapse sidebar' },
        searchPlaceholder: 'Search documents...',
        scope: { all: 'All sources' },
        loading: 'Loading items…',
        empty: 'No items match the current filters.',
      },
    },
    prompts: {
      pageTitle: 'Prompts',
      actions: { create: 'Add prompt' },
      empty: {
        title: 'No prompts yet',
        description: 'Create reusable prompts for common workflows.',
      },
      dialog: {
        title: { create: 'Add prompt', edit: 'Edit prompt' },
        description: { create: 'Create a reusable prompt.', edit: 'Update this prompt.' },
        tabs: { basic: 'Basic settings', editor: 'Prompt editor' },
        fields: {
          scope: { label: 'Layer' },
          fileName: { label: 'File name', placeholder: 'prompt.md' },
          namespace: { label: 'Namespace', placeholder: 'Optional namespace', helper: 'Use folders or namespaces to organize related prompts.' },
          content: { label: 'Prompt content', estimatedSize: 'Estimated size: {{size}}' },
        },
        validation: { fileName: 'Please enter a file name.', content: 'Prompt content cannot be empty.' },
        actions: { cancel: 'Cancel', save: 'Save changes', create: 'Create prompt' },
      },
    },
    subagents: {
      pageTitle: 'Subagents',
      actions: { create: 'Add subagent' },
      empty: {
        title: 'No subagents yet',
        description: 'Create specialized subagents for repeated task patterns.',
      },
      dialog: {
        title: { create: 'Add subagent', edit: 'Edit subagent' },
        description: {
          create: 'Configure a subagent definition.',
          edit: 'Update this subagent definition.',
        },
        fields: {
          scope: { label: 'Layer' },
          name: { label: 'Name', placeholder: 'code_reviewer' },
          description: { label: 'Description', placeholder: 'Reviews code for correctness and test gaps.' },
          developerInstructions: { label: 'Developer instructions', placeholder: 'Review code like an owner.' },
          nicknameCandidates: { label: 'Nickname candidates', placeholder: 'Atlas\nDelta' },
          model: { label: 'Model', placeholder: 'gpt-5.4' },
          modelReasoningEffort: {
            label: 'Reasoning effort',
            options: {
              high: { label: 'High', description: 'Trace complex logic, assumptions, and edge cases.' },
              medium: { label: 'Medium', description: 'Balanced default for most agents.' },
              low: { label: 'Low', description: 'Use when speed matters for straightforward tasks.' },
            },
          },
          sandboxMode: {
            label: 'Sandbox mode',
            options: {
              'read-only': { label: 'Read only', description: 'Inspect files without editing or running commands unless approved.' },
              'workspace-write': { label: 'Workspace write', description: 'Read files, edit within the workspace, and run routine local commands.' },
              'danger-full-access': { label: 'Full access', description: 'Run without sandbox filesystem or network restrictions.' },
            },
          },
          rawContent: { label: 'Raw TOML', placeholder: 'name = "reviewer"\ndescription = "Reviews code"\ndeveloper_instructions = """Review code like an owner."""' },
        },
        tabs: { structured: 'Structured', raw: 'Raw TOML' },
        validation: {
          name: 'Please enter a subagent name.',
          description: 'Please enter a description.',
          developerInstructions: 'Please enter developer instructions.',
          rawContent: 'Raw TOML cannot be empty.',
        },
        fallbackTitle: 'Subagent',
        actions: { cancel: 'Cancel', save: 'Save changes', create: 'Create subagent' },
      },
      registry: {
        summary: '{{layer}} agents: max threads {{maxThreads}}, max depth {{maxDepth}}, job runtime {{jobMaxRuntime}}s',
      },
    },
    runtime: {
      title: 'Session permissions are active',
      description: 'Codex now runs through the Python SDK with per-session permission controls.',
      body: 'Sandbox, approval, and network access are configured from the chat composer before a Codex turn starts.',
    },
  },
  common: {
    loading: 'Loading...',
    subViews: {
      overview: 'Overview',
      claudeMd: 'CLAUDE.md',
      geminiMd: 'GEMINI.md',
      agentsMd: 'AGENTS.md',
      config: 'Config',
      profiles: 'Profiles',
      permissionsProfiles: 'Permissions Profiles',
      features: 'Features',
      appsConnectors: 'Apps / Connectors',
      modelProviders: 'Model Providers',
      rules: 'Rules',
      mcp: 'Model Context Protocol',
      hooks: 'Hooks',
      plugins: 'Plugins',
      slashCommands: 'Slash Commands',
      prompts: 'Prompts',
      skills: 'Skills',
      scripts: 'Scripts',
      subagents: 'Subagents',
      managedRequirements: 'Managed Requirements',
      memory: 'Memory',
      outputStyles: 'Output Styles',
      settings: 'Settings',
      unknown: 'Settings',
    },
    scope: {
      project: 'Project',
      user: 'User',
      global: 'Global',
    },
    sourceNotices: {
      readOnly: {
        title: 'Read-only source',
        description: '{{source}} is provided by the system or a plugin and cannot be edited here.',
      },
      newThread: {
        title: 'New thread required',
        description: 'Changes to this setting apply to new Codex threads. Existing threads keep their current loaded capabilities.',
      },
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
        actions: { refresh: 'Refresh', import: 'Import config', create: 'Add server' },
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
      actions: { showEnvValues: 'Show values', hideEnvValues: 'Hide values', edit: 'Edit server', delete: 'Delete server' },
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
        pluginReadOnly: {
          title: 'Plugin server is read-only',
          description: 'Plugin MCP servers are controlled by the plugin-level enabled setting.',
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
