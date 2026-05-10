const marketplace = {
  common: {
    loading: 'Loading Marketplace...',
    uncategorized: 'Uncategorized',
    noVersion: 'No version',
    unknown: 'Unknown',
    actions: {
      back: 'Back',
      cancel: 'Cancel',
      refresh: 'Refresh',
      remove: 'Remove',
      save: 'Save',
    },
    labels: {
      enabled: 'Enabled',
    },
  },
  errors: {
    packageNotFound: 'Marketplace package was not found.',
    permission: {
      denied: 'You do not have permission to use this Marketplace action.',
    },
    module: {
      title: 'Marketplace is unavailable',
      description: 'The Marketplace module could not render this view.',
      action: 'Back to packages',
    },
  },
  providers: {
    'claude-code': 'Claude Code',
    codex: 'Codex',
    gemini: 'Gemini',
  },
  features: {
    mcp: 'MCP servers',
    commands: 'Commands',
    hooks: 'Hooks',
    agentsMd: 'AGENTS.md',
    claudeMd: 'CLAUDE.md',
    geminiMd: 'GEMINI.md',
    agents: 'Agents',
    subagents: 'Subagents',
    slashCommands: 'Slash Commands',
    outputStyle: 'Output styles',
    skills: 'Skills',
  },
  viewer: {
    readOnly: 'Read-only',
    emptyState: 'No file selected',
    copyPath: 'Copy path',
  },
  packageTypes: {
    plugin: 'Plugin',
    extension: 'Extension',
  },
  sourceTypes: {
    created: 'Created',
    imported: 'Imported',
    unknown: 'Unknown',
  },
  validation: {
    severity: {
      error: 'Error',
      warning: 'Warning',
      info: 'Info',
      none: 'Valid',
    },
    invalid_manifest_shape: 'Provider manifest shape is invalid.',
    package_identity_mismatch: 'Package identity does not match the provider manifest.',
    metadata_conflict: 'Catalog metadata differs from package manifest metadata.',
    invalid_package_id: 'Marketplace package id is invalid.',
    path_escape: 'Marketplace package path escapes the package root.',
    root_metadata_stripped: 'Marketplace root metadata is managed in Marketplace Settings and was not saved from the package editor.',
  },
  center: {
    header: {
      title: 'Marketplace',
      description: 'Manage provider-native packages, imports, installs, and registry settings.',
      stats: 'Total {{total}} packages · Showing {{visible}}',
    },
    actions: {
      import: 'Import package',
      create: 'New package',
      refresh: 'Refresh',
      settings: 'Marketplace settings',
    },
    filters: {
      searchLabel: 'Search packages',
      searchPlaceholder: 'Search id, name, tags, or resources...',
      cliLabel: 'CLI type',
      providerLabel: 'Provider',
      allProviders: 'All providers',
      featureLabel: 'Feature filters',
      allFeatures: 'All features',
      categoryLabel: 'Package categories',
      allCategories: 'All packages',
      clear: 'Clear',
      validationLabel: 'Validation',
      allSeverity: 'All severities',
      sourceLabel: 'Source',
      allSources: 'All sources',
    },
    viewModes: {
      grid: 'Grid view',
      list: 'List view',
    },
    list: {
      title: 'Package list',
      loading: 'Loading packages...',
      stats: {
        visible: 'Showing {{visible}} / {{total}}',
        page: 'Page {{current}} / {{total}}',
      },
      error: {
        title: 'Unable to load Marketplace packages.',
        retry: 'Retry',
      },
      empty: {
        title: 'No packages match your filters',
        reset: 'Clear filters',
      },
    },
    pagination: {
      pageCount: 'Page {{current}} / {{total}}',
      previous: 'Previous',
      next: 'Next',
      perPage: 'Per page',
      perPageOption: '{{count}} per page',
    },
    accessibility: {
      resizePane: 'Resize package filters',
    },
    card: {
      actions: {
        edit: 'Edit',
        export: 'Export',
        install: 'Install',
        delete: 'Delete',
      },
    },
  },
  fileTree: {
    error: {
      read: 'Unable to read this Marketplace file.',
      binaryRead: 'Binary Marketplace files cannot be opened as text.',
      create: 'Unable to create this Marketplace file.',
      write: 'Unable to save this Marketplace file.',
      delete: 'Unable to delete this Marketplace file.',
      rename: 'Unable to rename this Marketplace file.',
      upload: 'Unable to upload this Marketplace file.',
      download: 'Marketplace file downloads are not supported yet.',
      readOnly: 'This Marketplace file is read-only.',
    },
  },
  detail: {
    header: {
      version: 'Version {{version}}',
      provider: '{{provider}}',
      category: '{{category}}',
    },
    actions: {
      back: 'Back',
      backToCenter: 'Back to Marketplace',
      edit: 'Edit',
      export: 'Export',
      install: 'Install',
      delete: 'Delete',
    },
    tabs: {
      basicInfo: 'Basic info',
      readme: 'README',
      manifest: 'Manifest',
      resources: 'Resources',
      targetPreview: 'Target preview',
      files: 'View files',
    },
    featureEmpty: 'No content in this section.',
    sidebar: {
      info: {
        title: 'Package information',
        categoryLabel: 'Category',
        versionLabel: 'Version',
        providerLabel: 'Provider',
      },
      features: {
        title: 'Package sections',
      },
    },
    basicInfo: {
      title: 'Package information',
      packageId: 'Package ID',
      registryPath: 'Registry path',
      provider: 'Provider',
      packageType: 'Package type',
      version: 'Version',
      validation: 'Validation',
      family: 'Source family',
      variants: 'Provider variants',
      sections: {
        general: {
          title: 'General',
          description: 'Provider-native package identity and registry metadata.',
        },
        features: {
          title: 'Feature summary',
          description: 'Available package sections detected from the provider-native layout.',
        },
      },
    },
    viewer: {
      searchPlaceholder: 'Search files...',
      refresh: 'Refresh',
      collapseSidebar: 'Collapse file list',
      expandSidebar: 'Expand file list',
      resizeSidebar: 'Resize file list',
      fileNameFallback: 'Untitled file',
      descriptionFallback: 'No description',
      copy: 'Copy',
      download: 'Download',
      copySuccess: 'Content copied',
      copyFailed: 'Unable to copy content',
      toml: {
        description: 'Description',
        prompt: 'Prompt',
        developerInstructions: 'Developer instructions',
        raw: 'Raw TOML',
      },
    },
    agentsMd: {
      placeholder: 'Write AGENTS.md guidance...',
      downloadFileName: 'AGENTS.md',
      actions: {
        copy: 'Copy',
        download: 'Download',
        copySuccess: 'AGENTS.md copied',
        copyFailed: 'Unable to copy AGENTS.md',
        downloadSuccess: 'AGENTS.md downloaded',
      },
    },
    hooks: {
      header: {
        title: 'Package hooks',
      },
      badge: '{{count}} hooks',
      actions: {
        download: 'Download hooks',
      },
      downloadFileName: 'hooks.json',
      empty: {
        title: 'No hooks',
        description: 'This package does not define hooks.',
      },
      toasts: {
        downloadSuccess: 'Hooks downloaded',
      },
      card: {
        matchersTitle: 'Matchers',
        matcherLabel: 'Matcher',
        actionsCount: '{{count}} actions',
        executionTypeCommand: 'Command',
        executionTypes: {
          command: 'Command',
          http: 'HTTP',
          mcp_tool: 'MCP tool',
          prompt: 'Prompt',
          agent: 'Agent',
        },
        sequential: 'Sequential',
        timeoutSeconds: '{{count}}s',
        timeoutMilliseconds: '{{count}}ms',
        statusMessage: 'Status: {{value}}',
        shell: 'Shell: {{value}}',
        async: 'Async',
        asyncRewake: 'Rewake',
        ifLabel: 'if',
        emptyCommand: 'No command',
        emptyUrl: 'No URL',
        moreActions: '+{{count}} more actions',
        summary: {
          matchers: '{{count}} matchers',
          commands: '{{count}} commands',
        },
      },
    },
    mcp: {
      header: {
        title: 'Package MCP servers',
      },
      badge: '{{count}} servers',
      actions: {
        download: 'Download MCP',
      },
      downloadFileName: 'mcp.json',
      empty: {
        title: 'No MCP servers',
        description: 'This package does not define MCP servers.',
      },
      toasts: {
        copySuccess: 'MCP config copied',
        downloadSuccess: 'MCP config downloaded',
      },
      card: {
        copyTooltip: 'Copy MCP config',
        showEnvValues: 'Show environment values',
        hideEnvValues: 'Hide environment values',
        sections: {
          command: 'Command',
          url: 'URL',
          env: 'Environment',
          headers: 'Headers',
        },
      },
    },
    readme: {
      title: 'README',
      description: 'Rendered from package README.md with sanitized Markdown.',
      empty: 'No README content.',
    },
    validation: {
      title: 'Validation',
      description: 'Provider-native validation results for this package.',
      metadataConflict: 'Catalog metadata differs from the package manifest.',
    },
    metadata: {
      title: 'Metadata',
      catalog: 'Catalog entry',
      manifest: 'Package manifest',
    },
    resources: {
      title: 'Indexed resources',
    },
    activity: {
      title: 'Activity',
      description: 'Recent package-scoped import, install, and delete records.',
      empty: 'No package activity yet.',
    },
  },
  onboarding: {
    title: 'Marketplace setup',
    description: 'Initialize or clone the local registry before browsing packages.',
    setupTitle: 'Set up local registry',
    setupDescription: 'Marketplace stores provider-native packages under a system-managed shared registry root.',
    rootPath: 'Registry root: {{path}}',
    actions: {
      initialize: 'Initialize registry',
      initializeDescription: 'Create provider-separated roots locally.',
      clone: 'Clone registry',
      cloneDescription: 'Clone an existing registry into the managed root.',
    },
  },
  import: {
    title: 'Import packages',
    description: 'Scan an external provider marketplace repository and choose packages to copy locally.',
    fields: {
      provider: 'Provider',
      sourceKind: 'Source type',
      source: 'Repository URL',
      localFile: 'Upload package archive',
      newPackageId: 'New package ID',
      newPackageIdPlaceholder: 'package-id-copy',
    },
    sourceKinds: {
      git: 'Git repository',
      local: 'Local upload',
    },
    providers: {
      all: 'All providers',
    },
    localFile: {
      empty: 'No archive selected',
    },
    actions: {
      scan: 'Scan source',
      import: 'Import selected',
      settings: 'SSH settings',
      chooseFile: 'Choose archive',
      selectAll: 'Select all',
      clearSelection: 'Clear selection',
    },
    candidates: {
      title: 'Candidates',
      empty: 'Scan a source to list import candidates.',
      duplicate: 'Duplicate',
      family: 'Family: {{family}}',
    },
    variantStatuses: {
      'new-family': 'New family',
      'add-variant': 'Add provider variant',
      'duplicate-variant': 'Existing provider variant',
      'unrelated-duplicate': 'Unrelated duplicate',
      invalid: 'Invalid',
    },
    duplicateActions: {
      skip: 'Skip',
      overwrite: 'Overwrite',
      importAsNew: 'Import as new id',
    },
    validation: {
      duplicate: 'A local package with the same provider and id already exists.',
      sourceRequired: 'Import source is required.',
      invalidSourceKind: 'Import source kind is invalid.',
      invalidRepositoryUrl: 'Import repository URL is invalid.',
      invalidRef: 'Import ref is invalid.',
      localPathNotFound: 'Import local path was not found.',
      localPathNotAllowed: 'Import local path is not allowed.',
      rawPrivateKeyUnsupported: 'Raw private key material is not accepted in Marketplace import.',
      httpsTokenUnsupported: 'HTTPS token authentication is not supported for Marketplace import in this version.',
      sshKeyRequired: 'Generate a Marketplace SSH key before importing from an SSH repository.',
      cloneFailed: 'Marketplace import source checkout failed.',
      invalidUploadArchive: 'Upload a valid ZIP archive.',
    },
    result: {
      summary: 'Imported {{imported}}, skipped {{skipped}}, failed {{failed}}, duplicates {{duplicates}}, warnings {{warnings}}.',
      failedDetails: 'Failed items',
      failedDetailsDescription: 'Failed items: {{details}}',
      failedDetailItem: '{{displayName}} ({{packageId}}): {{message}}',
    },
  },
  install: {
    title: 'Install package',
    description: 'Install this package by executing the {{commandName}} command in the target workspace runtime.',
    commandNames: {
      'claude-code': 'Claude',
      codex: 'Codex',
      gemini: 'Gemini',
    },
    fields: {
      provider: 'Provider',
      package: 'Package',
      workspace: 'Target workspace',
    },
    workspaceSelect: {
      placeholder: 'Select a workspace',
      loading: 'Loading workspaces...',
      currentWorkspace: 'Current workspace',
    },
    preflight: {
      loading: 'Checking {{commandName}} command availability...',
      ready: '{{commandName}} command is available ({{version}}).',
      unavailable: '{{commandName}} command is unavailable: {{code}}.',
      unknownVersion: 'version unknown',
    },
    commandPreview: 'Command preview',
    output: {
      title: 'Redacted output',
      stdout: 'stdout',
      stderr: 'stderr',
      truncated: 'Output was truncated.',
    },
    actions: {
      install: 'Install',
    },
    result: {
      success: 'Package installed successfully.',
      failed: 'Install failed with error code: {{code}}',
      timeout: 'Install timed out before the {{commandName}} command completed. Error code: {{code}}',
      validation: 'Install was blocked by provider validation. Error code: {{code}}',
      cliUnavailable: '{{commandName}} command is unavailable in the target workspace. Error code: {{code}}',
      cliVersionUnsupported: '{{commandName}} command version is not supported. Error code: {{code}}',
      cliCapabilityMissing: '{{commandName}} command does not support the required install capability. Error code: {{code}}',
      runtimeUnavailable: 'Workspace runtime is unavailable. Error code: {{code}}',
    },
  },
  export: {
    title: 'Export package',
    description: 'Create a provider-native .zip archive that can be imported by Marketplace.',
    fields: {
      archive: 'Archive',
      root: 'Archive root',
    },
    compatibilityNotice: 'The archive includes the provider metadata required for Marketplace import scanning.',
    actions: {
      export: 'Export .zip',
    },
    result: {
      ready: 'Export archive is ready.',
      failed: 'Export failed with error code: {{code}}',
    },
  },
  delete: {
    title: 'Delete package',
    description: 'Hard-delete the local Marketplace package using the current package revision.',
    warning: 'This removes the package directory and provider marketplace entry when applicable.',
    fields: {
      package: 'Package',
      revision: 'Revision',
      confirm: 'Type {{id}} to confirm',
    },
    actions: {
      delete: 'Delete package',
    },
    result: {
      success: 'Package deleted.',
      failed: 'Delete failed with error code: {{code}}',
    },
  },
  activity: {
    actions: {
      import: 'Import',
      install: 'Install',
      delete: 'Delete',
    },
    status: {
      success: 'Success',
      failed: 'Failed',
    },
  },
  editor: {
    createTitle: 'Create Marketplace package',
    editTitle: 'Edit Marketplace package',
    dirty: 'Unsaved changes',
    unsaved: {
      leaveConfirm: 'You have unsaved Marketplace package changes. Discard them and leave?',
      title: 'Unsaved changes',
      description: 'Save changes, discard them, or cancel navigation.',
    },
    saveStatus: {
      success: 'Saved',
      validationError: 'Validation failed',
      revisionConflict: 'Revision conflict',
    },
    actions: {
      save: 'Save',
      discard: 'Discard',
    },
    providerStep: {
      title: 'Create Marketplace package',
      description: 'Select the provider format before editing package fields.',
      heading: 'Choose a provider format',
      help: 'The selected provider determines the native scaffold, visible editor sections, validation, export, and install command.',
      sectionsLabel: 'Editor sections',
      options: {
        'claude-code': {
          description: 'Create a Claude Code plugin package.',
        },
        codex: {
          description: 'Create a Codex plugin package.',
        },
        gemini: {
          description: 'Create a Gemini extension package.',
        },
      },
    },
    common: {
      rename: {
        action: 'Rename',
        title: 'Rename path',
        description: 'Update the package-relative file path. Content editing stays separate.',
        pathLabel: 'File path',
        pathPlaceholder: 'agents/review-agent.md',
      },
    },
    fields: {
      provider: 'Provider',
      providerHint: 'Provider determines the native package layout and editor sections.',
      packageId: 'Package ID',
      packageIdPlaceholder: 'review-assistant',
      packageIdHint: 'Used as the provider-native folder and package identifier.',
      packageIdPreviewFallback: 'package-id',
      displayName: 'Display name',
      displayNamePlaceholder: 'Review Assistant',
      description: 'Description',
      descriptionPlaceholder: 'Describe what this package installs or enables.',
      registryPath: 'Registry path',
    },
    defaults: {
      packageName: 'package-id',
      codexMarketplaceName: 'local-codex-marketplace',
      claudeMarketplaceName: 'local-claude-marketplace',
      ownerName: 'Local user',
      description: 'Describe this package.',
    },
    requiredTabs: {
      form: 'Form',
      json: 'JSON',
    },
    requiredFields: {
      title: 'Required fields',
      description: 'Edit required provider fields once. JSON mode shows the provider-native output documents.',
    },
    tabs: {
      basic: 'Basic info',
      agentsMd: 'AGENTS.md',
      pluginManifest: 'Plugin manifest',
      extensionManifest: 'Extension manifest',
      packageMetadata: 'Package metadata',
      readme: 'README',
      skills: 'Skills',
      commands: 'Commands',
      slashCommand: 'Slash Commands',
      agents: 'Agents',
      subagents: 'Subagents',
      hooks: 'Hooks',
      mcp: 'MCP',
      outputStyle: 'Output styles',
      files: 'File management',
      claudeMd: 'CLAUDE.md',
      geminiMd: 'GEMINI.md',
      tomlCommands: 'TOML commands',
      policies: 'Policies',
    },
    packageSections: {
      listing: {
        title: 'Package listing fields',
        description: 'Fields used to generate this package listing. The full marketplace manifest is not editable here.',
      },
      manifest: {
        description: 'Provider-native manifest content for the package.',
      },
      commonMetadata: {
        title: 'Common plugin metadata',
      },
      interfaceMetadata: {
        title: 'Interface metadata',
        description: 'Codex interface metadata stored in the provider-native plugin manifest.',
        summaryFallback: 'Describe how this plugin appears in Codex.',
      },
      codexPolicy: {
        title: 'Codex marketplace policy',
        description: 'Current package policy projection stored in the Codex marketplace entry.',
      },
      geminiAdvanced: {
        title: 'Gemini advanced manifest fields',
        description: 'Structured extension settings that remain inside gemini-extension.json.',
      },
      providerGuidance: {
        title: 'Provider guidance',
        description: 'Gemini guidance installed with the extension.',
        placeholder: 'Write GEMINI.md guidance...',
      },
      readme: {
        description: 'README content shown in package detail and marketplace previews.',
        placeholder: 'Write README content...',
      },
      fields: {
        packageId: 'Package ID',
        packageName: 'Package name',
        provider: 'Provider',
        category: 'Category',
        source: 'Source',
        tags: 'Tags',
        strict: 'Strict',
        manifestId: 'Manifest ID',
        manifestName: 'Manifest name',
        version: 'Version',
        file: 'File',
        marketplaceName: 'Marketplace name',
        ownerName: 'Owner name',
        rootMetadataHint: 'Root marketplace metadata is edited in Marketplace settings.',
        description: 'Description',
        authorName: 'Author name',
        authorEmail: 'Author email',
        authorUrl: 'Author URL',
        homepage: 'Homepage',
        repository: 'Repository',
        license: 'License',
        keywords: 'Keywords',
        policyInstallation: 'policy.installation',
        policyAuthentication: 'policy.authentication',
        displayName: 'displayName',
        shortDescription: 'shortDescription',
        longDescription: 'longDescription',
        developerName: 'developerName',
        interfaceCategory: 'interface.category',
        capabilities: 'capabilities',
        websiteURL: 'websiteURL',
        privacyPolicyURL: 'privacyPolicyURL',
        termsOfServiceURL: 'termsOfServiceURL',
        defaultPrompt: 'defaultPrompt',
        brandColor: 'brandColor',
        composerIcon: 'composerIcon',
        logo: 'logo',
        screenshots: 'screenshots',
        contextFileName: 'contextFileName',
        excludeTools: 'excludeTools',
        migratedTo: 'migratedTo',
        planDirectory: 'plan.directory',
        settings: 'settings[]',
        themes: 'themes[]',
        mcpServers: 'mcpServers',
      },
    },
    required: {
      json: {
        tabs: {
          entry: 'Marketplace entry',
          plugin: 'Plugin settings',
          extension: 'Extension settings',
        },
        infoLabel: 'Show JSON details for {{document}}',
        popovers: {
          entry: 'Edits only this package entry from marketplace.json. Root marketplace metadata and sibling entries are managed outside this package editor.',
          plugin: 'Edits this package plugin.json required settings. Valid JSON updates the required-field form immediately.',
          extension: 'Edits this package gemini-extension.json settings. Valid JSON updates the required-field form immediately.',
        },
        fileBadge: {
          thisEntryOnly: 'this entry only',
        },
        parseError: 'Invalid JSON. The text is kept, but form fields still show the last valid values.',
      },
    },
    agentsMd: {
      title: 'AGENTS.md',
      description: 'Workspace guidance installed with the package.',
      placeholder: 'Write AGENTS.md guidance...',
      status: {
        loading: 'Loading AGENTS.md...',
      },
      actions: {
        copy: 'Copy',
        download: 'Download',
      },
    },
    featureSections: {
      count: '{{count}} items',
      actions: {
        add: 'Add',
      },
      skills: {
        emptyTitle: 'No skills',
        emptyDescription: 'Add package skills when Marketplace file APIs are connected.',
      },
      agents: {
        emptyTitle: 'No agents',
        emptyDescription: 'Add package agents when Marketplace file APIs are connected.',
      },
      commands: {
        emptyTitle: 'No commands',
        emptyDescription: 'Add package commands when Marketplace file APIs are connected.',
      },
      mcp: {
        emptyTitle: 'No MCP servers',
        emptyDescription: 'Add MCP server definitions when Marketplace file APIs are connected.',
      },
      hooks: {
        emptyTitle: 'No hooks',
        emptyDescription: 'Add hook definitions when Marketplace file APIs are connected.',
      },
      outputStyle: {
        emptyTitle: 'No output styles',
        emptyDescription: 'Add output style documents when Marketplace file APIs are connected.',
      },
      files: {
        emptyTitle: 'No files',
        emptyDescription: 'Browse package files when Marketplace file APIs are connected.',
      },
    },
    fileManager: {
      skills: {
        title: 'Skills',
      },
      packageFiles: {
        title: 'Files',
        rootLabel: 'Package root',
      },
      search: {
        placeholder: 'Search files...',
      },
      sidebar: {
        refresh: 'Refresh',
        upload: 'Upload',
        createFile: 'Create file',
        createFolder: 'Create folder',
      },
      actions: {
        save: 'Save',
        create: {
          trigger: 'Create',
        },
      },
      viewer: {
        noFile: 'No file selected',
      },
    },
    documentViewer: {
      unsavedFile: 'Unsaved',
      search: {
        placeholder: 'Search files...',
      },
      actions: {
        add: 'Add',
        refresh: 'Refresh',
        delete: 'Delete',
        copy: 'Copy',
        download: 'Download',
        more: 'More actions',
      },
      editor: {
        placeholder: 'Write Markdown content...',
        tomlPlaceholder: 'Write TOML content...',
      },
      formats: {
        markdown: 'Markdown',
        toml: 'TOML',
      },
      create: {
        title: 'Add {{resource}}',
        description: 'Create a {{format}} resource in this Marketplace package.',
        defaultTitle: 'New Markdown resource',
        defaultDescription: 'Created in the Marketplace editor.',
        fields: {
          path: {
            label: 'File path',
            placeholder: 'commands/new-command.md',
            helper: 'Use a provider-native relative path. {{extension}} is added automatically when omitted.',
          },
          content: {
            label: 'Content',
          },
        },
        validation: {
          pathRequired: 'File path is required.',
          contentRequired: 'Content is required.',
        },
        actions: {
          create: 'Create',
        },
      },
      empty: {
        filtered: 'No files match your search.',
      },
      agents: {
        title: 'Subagents',
        empty: 'No subagents',
      },
      commands: {
        title: 'Slash Commands',
        empty: 'No slash commands',
      },
      outputStyle: {
        title: 'Output styles',
        empty: 'No output styles',
      },
      policies: {
        title: 'Policies',
        empty: 'No policies',
      },
    },
    mcp: {
      card: {
        sections: {
          command: 'Command',
          arguments: 'Arguments',
          environment: 'Environment',
        },
      },
      dialog: {
        title: 'Edit MCP server',
        titleCreate: 'Add MCP server',
        description: 'Update the MCP server definition stored in this Marketplace package.',
        descriptionCreate: 'Create an MCP server definition for this Marketplace package.',
        create: {
          defaultTitle: 'New MCP server',
          defaultDescription: 'Created in the Marketplace editor.',
        },
        actions: {
          save: 'Save server',
        },
        transport: {
          label: 'Transport type',
          options: {
            stdio: {
              label: 'Standard I/O',
              description: 'Run a local command over stdio.',
            },
            sse: {
              label: 'Server-Sent Events',
              description: 'Connect to a remote SSE endpoint.',
            },
            http: {
              label: 'Streamable HTTP',
              description: 'Connect to a remote HTTP endpoint.',
            },
          },
        },
        validation: {
          nameRequired: 'Server name is required.',
          descriptionRequired: 'Description is required.',
          commandRequired: 'Command is required for stdio transport.',
          urlRequired: 'URL is required for remote transport.',
        },
        fields: {
          name: {
            label: 'Name',
            placeholder: 'repository-context',
          },
          description: {
            label: 'Description',
            placeholder: 'Describe what this server provides',
          },
          command: {
            label: 'Command',
            placeholder: 'node',
          },
          args: {
            label: 'Arguments',
            add: 'Add argument',
            empty: 'No arguments',
            placeholder: 'Argument {{index}}',
          },
          url: {
            label: 'URL',
            placeholderSse: 'https://example.com/sse',
            placeholderHttp: 'https://example.com/mcp',
            hintSse: 'Use the SSE endpoint exposed by the MCP server.',
            hintHttp: 'Use the streamable HTTP endpoint exposed by the MCP server.',
          },
          headers: {
            label: 'Headers',
            add: 'Add header',
            keyPlaceholder: 'Header',
            valuePlaceholder: 'Value',
            empty: 'No headers',
            hint: 'Header values may contain environment placeholders.',
          },
          env: {
            label: 'Environment variables',
            add: 'Add variable',
            keyPlaceholder: 'NAME',
            valuePlaceholder: 'value',
            empty: 'No environment variables',
          },
        },
      },
    },
    hooks: {
      card: {
        matchersTitle: 'Matchers',
        matcherLabel: 'Matcher',
        actionsCount: '{{count}} actions',
        executionTypeCommand: 'Command',
        sequential: 'Sequential',
        summary: {
          matchers: '{{count}} matchers',
          commands: '{{count}} commands',
        },
      },
      dialog: {
        title: 'Edit hook',
        titleCreate: 'Add hook',
        description: {
          'claude-code': 'Configure Claude Code command hook events, matchers, and execution options.',
          codex: 'Configure Codex hooks.json events, matchers, command execution, and status messages.',
          gemini: 'Configure Gemini hooks/hooks.json events, sequential execution, command name, and millisecond timeout.',
        },
        create: {
          defaultTitle: 'New hook',
          defaultDescription: 'Created in the Marketplace editor.',
        },
        actions: {
          save: 'Save hook',
        },
        validation: {
          commandRequired: 'At least one command is required for every matcher.',
        },
        fields: {
          name: {
            label: 'Name',
            placeholder: 'review-pre-submit',
          },
          event: {
            label: 'Event',
            placeholder: 'Select hook event',
          },
        },
        matchers: {
          title: 'Matchers',
          add: 'Add matcher',
          patternLabel: 'Matcher pattern',
          patternPlaceholder: '*',
          sequentialLabel: 'Run hooks sequentially',
          sequentialHelp: 'Gemini can run hook actions sequentially instead of in parallel for this matcher group.',
          patternHelp: {
            'claude-code': {
              overview: 'Use a matcher to limit which Claude Code tool or event target runs this hook.',
              literal: 'Literal tool names are supported.',
              regex: 'Regex patterns can match multiple tools.',
              wildcard: 'Use * to match everything.',
            },
            codex: {
              overview: 'Use a matcher to limit which Codex tool, permission, or session source runs this hook.',
              literal: 'Literal tool names such as Bash or apply_patch are supported.',
              regex: 'Regex patterns can match multiple tools.',
              wildcard: 'Use * or an empty matcher to match everything.',
            },
            gemini: {
              overview: 'Use a matcher to limit which Gemini CLI tool or agent event runs this hook.',
              literal: 'Literal tool or agent names are supported.',
              regex: 'Regex patterns can match multiple targets.',
              wildcard: 'Use * to match everything.',
            },
          },
        },
        executions: {
          title: 'Commands',
          add: 'Add command',
          types: {
            command: {
              label: 'Command',
            },
            http: {
              label: 'HTTP',
            },
            mcp_tool: {
              label: 'MCP tool',
            },
            prompt: {
              label: 'Prompt',
            },
            agent: {
              label: 'Agent',
            },
          },
          timeoutLabel: {
            'claude-code': 'Timeout seconds',
            codex: 'Timeout seconds',
            gemini: 'Timeout milliseconds',
          },
          timeoutHelp: {
            'claude-code': 'Claude Code command handlers use seconds.',
            codex: 'Codex hook commands use seconds and default to the CLI behavior when omitted.',
            gemini: 'Gemini hook commands use milliseconds and default to 60000.',
          },
          conditionLabel: 'Condition',
          conditionPlaceholder: 'event.tool_name == "Bash"',
          conditionHelp: 'Optional Claude Code if expression that gates this handler.',
          commandLabel: {
            'claude-code': 'Command',
            codex: 'Command',
            gemini: 'Command',
          },
          commandPlaceholder: {
            'claude-code': 'npm test',
            codex: 'npm test',
            gemini: 'gemini context load',
          },
          commandHelp: {
            'claude-code': 'Claude Code plugin editor supports command hooks in this form. Advanced handler types can be managed from package files.',
            codex: 'Codex runs command hooks from the workspace context.',
            gemini: 'Gemini runs command hooks from the extension or workspace context.',
          },
          nameLabel: 'Hook name',
          namePlaceholder: 'workspace-context',
          nameHelp: 'Gemini hook action name stored in hooks/hooks.json.',
          descriptionLabel: 'Description',
          descriptionPlaceholder: 'Describe what this hook does.',
          descriptionHelp: 'Optional Gemini hook action description.',
          statusMessageLabel: 'Status message',
          statusMessagePlaceholder: 'Running checks',
          statusMessageHelp: 'Optional progress text shown while the hook runs.',
          asyncLabel: 'Run asynchronously',
          asyncRewakeLabel: 'Rewake after async completion',
          shellLabel: 'Shell',
          shellPlaceholder: 'Select shell',
          shellOptions: {
            bash: 'Bash',
            powershell: 'PowerShell',
          },
          remove: 'Remove command',
        },
        codexFeatureFlag: 'Codex plugin hooks require features.codex_hooks to be enabled in the target Codex configuration layer.',
      },
      events: {
        PreToolUse: { label: 'PreToolUse', description: 'Runs before a tool call.' },
        PostToolUse: { label: 'PostToolUse', description: 'Runs after a tool call.' },
        PermissionRequest: { label: 'PermissionRequest', description: 'Runs when Codex requests permission.' },
        UserPromptSubmit: { label: 'UserPromptSubmit', description: 'Runs when the user submits a prompt.' },
        Notification: { label: 'Notification', description: 'Runs when a notification is emitted.' },
        Stop: { label: 'Stop', description: 'Runs when the main agent stops.' },
        SubagentStop: { label: 'SubagentStop', description: 'Runs when a subagent stops.' },
        PreCompact: { label: 'PreCompact', description: 'Runs before context compaction.' },
        PreCompress: { label: 'PreCompress', description: 'Runs before Gemini context compression.' },
        SessionStart: { label: 'SessionStart', description: 'Runs when a session starts.' },
        SessionEnd: { label: 'SessionEnd', description: 'Runs when a session ends.' },
        BeforeTool: { label: 'BeforeTool', description: 'Runs before a Gemini tool call.' },
        AfterTool: { label: 'AfterTool', description: 'Runs after a Gemini tool call.' },
        BeforeAgent: { label: 'BeforeAgent', description: 'Runs before a Gemini subagent runs.' },
        AfterAgent: { label: 'AfterAgent', description: 'Runs after a Gemini subagent runs.' },
        BeforeModel: { label: 'BeforeModel', description: 'Runs before Gemini sends a model request.' },
      },
    },
    featureMeta: {
      labels: {
        transport: 'Transport',
        env: 'Environment',
        matcher: 'Matcher',
        timeout: 'Timeout',
        type: 'Type',
        sequential: 'Sequential',
      },
    },
    scaffold: {
      skills: {
        reviewChecklist: {
          title: 'Review checklist',
          description: 'Guides structured review passes with findings, risk, and test coverage.',
        },
        riskMap: {
          title: 'Risk map',
          description: 'Maps changed files to likely product and runtime risks.',
        },
      },
      agents: {
        reviewAgent: {
          title: 'Review agent',
          description: 'Focused package agent for bug, regression, and missing-test analysis.',
        },
      },
      commands: {
        reviewSummary: {
          title: 'Review summary',
          description: 'Generates a concise review summary from staged changes.',
        },
        reviewTests: {
          title: 'Review tests',
          description: 'Suggests targeted verification commands for the current diff.',
        },
      },
      mcp: {
        repositoryContext: {
          title: 'Repository context',
          description: 'Provides repository metadata and diff context to the CLI runtime.',
        },
      },
      hooks: {
        reviewPreSubmit: {
          title: 'Review pre-submit',
          description: 'Runs review checks before submit-oriented tool calls.',
        },
      },
      outputStyle: {
        reviewFindings: {
          title: 'Review findings',
          description: 'Formats review output with findings first and summary second.',
        },
      },
      policies: {
        safeShell: {
          title: 'Safe shell policy',
          description: 'Blocks destructive shell command patterns for Gemini CLI.',
        },
      },
      files: {
        packageIcon: {
          title: 'Package icon',
          description: 'SVG icon asset shown in package catalog surfaces.',
        },
        license: {
          title: 'License',
          description: 'License file bundled with the provider-native package.',
        },
      },
    },
  },
  settings: {
    title: 'Marketplace settings',
    description: 'Manage registry metadata, version control, remotes, Git identity, SSH keys, and activity.',
    tabs: {
      general: 'General',
      versionControl: 'Version Control',
      remote: 'Remote',
      gitUser: 'Git User',
      sshKeys: 'SSH Keys',
      activity: 'Activity',
    },
    general: {
      title: 'General',
      description: 'Registry metadata for Marketplace provider exports.',
      displayName: 'Registry display name',
      maintainerName: 'Maintainer name',
      maintainerEmail: 'Maintainer email',
      rootPath: 'Registry root path',
      status: 'Registry status',
      statusReady: 'Ready',
      descriptionField: 'Registry description',
      rootMetadataTitle: 'Root marketplace metadata',
      rootMetadataDescription: 'These fields generate the root marketplace.json metadata for provider-specific exports.',
      generatedPreviewTitle: 'Generated marketplace.json preview',
      generatedPreviewDescription: 'Preview the root metadata shape written for each provider export.',
      previews: {
        claude: {
          title: 'Claude Code marketplace.json',
        },
        codex: {
          title: 'Codex marketplace.json',
        },
      },
    },
    versionControl: {
      title: 'Registry Version Control',
      description: 'Review provider-separated registry changes before committing or syncing.',
      actions: {
        fetch: 'Fetch',
        pull: 'Pull',
        push: 'Push',
        stage: 'Stage',
        unstage: 'Unstage',
        commit: 'Commit staged changes',
      },
      status: {
        title: 'Repository status',
        description: 'Current branch, remote, and staged change summary.',
        staged: '{{count}} staged',
        unstaged: '{{count}} unstaged',
      },
      changes: {
        title: 'Changed files',
        staged: 'Staged',
        unstaged: 'Unstaged',
      },
      diff: {
        title: 'Diff preview',
      },
      commit: {
        title: 'Commit',
        description: 'Commit staged Marketplace registry files.',
        placeholder: 'Describe the registry change...',
      },
      history: {
        title: 'History',
        description: 'Recent registry commits.',
      },
      errors: {
        conflict: 'Pull stopped because registry files have conflicts. Resolve conflicts outside Marketplace, then refresh.',
        unsupportedBranch: 'This repository requires an unsupported branch operation. Marketplace first version only supports current-branch fetch, pull, push, status, diff, commit, and history.',
        permissionDenied: 'You can view Marketplace registry changes, but you do not have permission to stage, commit, or update the registry.',
      },
      setupRequired: {
        title: 'Git repository setup required',
        description: 'Initialize or clone a Marketplace registry before using version control.',
        action: 'Open repository setup',
      },
    },
    git: {
      repository: {
        title: 'Repository',
        description: 'Marketplace registry Git remote and branch settings.',
        status: 'Repository settings are shown as placeholder data until Marketplace APIs are connected.',
        remoteUrl: 'Remote URL',
        branch: 'Branch',
      },
      user: {
        title: 'Git user',
        description: 'Identity used when Marketplace registry changes are committed.',
        name: 'User name',
        email: 'User email',
        save: 'Save Git settings',
      },
    },
    activity: {
      title: 'Activity',
      description: 'Registry-scoped import, install, and delete records.',
      empty: 'No Marketplace activity records yet.',
    },
  },
};

export default marketplace;
