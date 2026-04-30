const template = {
  center: {
    loading: 'Loading...',
    onboarding: {
      loading: 'Checking Template Center repository...',
      title: 'Set up Template Center registry',
      description: 'Clone an existing registry or initialize the current registry with Git before entering Template Center.',
      unknownError: 'Unknown error',
      statusError: {
        title: 'Unable to check repository status',
        description: 'Template Center needs repository status before it can load normal workflows.',
      },
      actions: {
        retry: 'Retry',
      },
      validation: {
        cloneUrlRequired: 'Repository URL is required.',
      },
      clone: {
        title: 'Clone existing registry',
        description: 'Use a Git repository that already contains Template Center registry files.',
        blockedTitle: 'Clone is unavailable',
        blockedDescription: 'Local registry files already exist, so clone is disabled to avoid replacing them.',
        blockedReason: 'Initialize the current registry to keep and track existing local files.',
        urlLabel: 'Repository URL',
        urlPlaceholder: 'git@github.com:username/template-registry.git',
        branchLabel: 'Branch',
        branchPlaceholder: 'main',
        branchHelper: 'Leave blank to use the repository default branch.',
        progressTitle: 'Clone progress',
        actions: {
          clone: 'Clone registry',
          cloning: 'Cloning...',
        },
      },
      init: {
        title: 'Initialize current registry',
        description: 'Keep existing local files and start tracking the registry with Git.',
        actions: {
          init: 'Initialize registry',
          initializing: 'Initializing...',
        },
      },
      toasts: {
        cloneStarted: {
          title: 'Clone started',
          description: 'Template Center is cloning the registry in the background.',
        },
        cloneFailed: {
          title: 'Clone failed',
          description: 'Unable to clone registry: {{error}}',
        },
        initSuccess: {
          title: 'Registry initialized',
          description: 'Template Center registry is now tracked by Git.',
        },
        initFailed: {
          title: 'Initialization failed',
          description: 'Unable to initialize registry: {{error}}',
        },
      },
    },
    header: {
      title: 'Template Center',
      description: 'Browse and manage all templates with quick install, export, and import.',
      stats: 'Total {{total}} templates · Showing {{visible}}',
    },
    actions: {
      import: 'Import template',
      create: 'New template',
      refresh: 'Refresh',
      settings: 'Template center settings',
    },
    filters: {
      searchLabel: 'Search templates',
      searchPlaceholder: 'Enter keywords...',
      featureLabel: 'Feature filters',
      cliLabel: 'CLI type',
      allCli: 'All CLI types',
      cliOptions: {
        claudeCode: 'ClaudeCode',
        codex: 'Codex',
        gemini: 'Gemini',
        opencode: 'OpenCode',
      },

      clear: 'Clear',
      categoryLabel: 'Template categories',
      allTemplates: 'All templates',
      allFeatures: 'All features',
      featureOptions: {
        mcp: 'MCP',
        commands: 'Commands',
        hooks: 'Hooks',
        agentsMd: 'AGENTS.md',
        agentMd: 'AGENT.md',
        agents: 'Agents',
        outputStyle: 'Output Style',
        scripts: 'Scripts',
        skills: 'Skills',
      },
    },
    accessibility: {
      resizePane: 'Resize panel width',
    },
    list: {
      title: 'Template list',
      description: 'Total {{total}} templates. Filter or create as needed.',
      stats: {
        visible: 'Showing {{visible}} / {{total}}',
        page: 'Page {{current}} / {{total}}',
      },
      loading: 'Loading templates...',
      error: {
        title: 'Unable to load template data.',
        retry: 'Try again',
      },
      empty: {
        title: 'No templates match your filters',
        reset: 'Clear filters',
      },
    },
    pagination: {
      pageCount: 'Page {{current}} / {{total}}',
      previous: 'Previous',
      next: 'Next',
      perPage: 'Per page',
      perPageOption: '{{count}}',
    },
    dialogs: {
      delete: {
        title: 'Delete template',
        description: 'Are you sure you want to delete template "{{name}}"? This action cannot be undone.',
        cancel: 'Cancel',
        confirm: 'Delete',
      },
    },
    settings: {
      tabs: {
        versionControl: 'Version Control',
        gitUser: 'Git User',
        sshKeys: 'SSH Keys',
      },
      versionControl: {
        rebuildProgressTitle: 'Template rebuild progress',
        confirmDiscard: 'Discard changes to "{{path}}"? This action cannot be undone.',
        confirmDiscardMultiple: 'Discard changes to {{count}} files? This action cannot be undone.',
        mode: {
          title: 'Version Control',
          fileChanges: 'File Changes',
          commitHistory: 'History',
        },
        registryStale: {
          description: 'Registry content may have changed. Rebuild the template index to sync the latest state.',
        },
        setupRequired: {
          title: 'Git repository setup required',
          description: 'Initialize the current template registry or clone an existing registry before using version control.',
          action: 'Open repository setup',
        },
        remoteMissing: {
          description: 'No origin remote is configured yet. Local Git actions are available, but fetch, pull, and push require a remote URL.',
          inline: 'Origin is not configured. Remote sync actions are disabled.',
        },
        status: {
          branch: 'Branch',
          noBranch: 'No branch',
          sync: 'Sync status',
          aheadBehind: 'Ahead {{ahead}} / behind {{behind}}',
          changes: 'Changes',
          changeCounts: 'Staged {{staged}} · unstaged {{unstaged}} · untracked {{untracked}}',
          conflicts: 'Conflicts',
          hasConflicts: 'Conflicts found',
          noConflicts: 'No conflicts',
        },
        actions: {
          rebuild: 'Rebuild index',
        },
        toasts: {
          loadFailed: {
            title: 'Failed to load Git data',
            description: 'Unable to load Template Center version-control data',
          },
          operationFailed: {
            title: 'Git operation failed',
            description: 'Unable to complete Git operation',
          },
          commitSuccess: {
            title: 'Commit successful',
          },
          fetchSuccess: {
            title: 'Fetch successful',
          },
          pullSuccess: {
            title: 'Pull successful',
          },
          pushSuccess: {
            title: 'Push successful',
          },
          checkoutSuccess: {
            title: 'Branch switched',
          },
          rebuildFailed: {
            title: 'Failed to rebuild index',
            description: 'Unable to start template index rebuild',
          },
        },
      },
    },
    settingsDialog: {
      title: 'Configure template center',
      description: 'Manage synchronization sources and metadata for the template center.',
      git: {
        repositorySetup: {
          title: 'Repository setup',
          description: 'Initialize the current template registry as Git, or clone an existing remote registry into an empty template center.',
          localContentWarning: 'Local template files already exist. Clone is disabled to prevent replacing them; initialize the current registry instead.',
          cloneDisabledHelper: 'Clone is available only when the template center has no local files. Use initialize to keep and track the current files.',
          initializedAlertTitle: 'Git repository initialized',
          actions: {
            init: 'Initialize repository',
            initializing: 'Initializing...',
          },
        },
        remote: {
          title: 'Remote repository',
          description: 'Configure the existing Git repository origin used by fetch, pull, and push.',
          urlLabel: 'Origin URL',
          helper: 'This updates the origin remote in the repository Git configuration.',
          missingOrigin: 'Origin is not configured. Add a remote URL to enable fetch, pull, and push.',
          noBranch: 'No branch',
          validation: {
            required: 'Origin URL is required',
          },
          actions: {
            save: 'Save remote',
            saving: 'Saving...',
          },
        },
        userConfig: {
          title: 'Git User Information',
          description: 'Configure the global Git user name and email used for commits.',
          userNameLabel: 'Git User Name',
          userNamePlaceholder: 'Enter the Git user name',
          userEmailLabel: 'Git Email Address',
          userEmailPlaceholder: 'Enter the Git email address',
          helper: 'The values are stored via git config --global and apply to all workspaces.',
          validation: {
            required: 'Git user name and email are required',
          },
          actions: {
            save: 'Save Git Settings',
            saving: 'Saving...',
          },
        },
        cloneRepo: {
          title: 'Clone Git Repository',
          description: 'Clone a remote Git repository into the template center, or update an existing one.',
          cloneProgressTitle: 'Clone Progress',
          successAlertTitle: 'Repository cloned successfully',
          remoteLabel: 'Remote',
          branchStatusLabel: 'Branch',
          urlLabel: 'Git Repository URL',
          urlPlaceholder: 'e.g., git@github.com:username/repo.git or https://github.com/username/repo.git',
          branchLabel: 'Branch name (optional)',
          branchPlaceholder: 'e.g., main or develop (leave empty for default branch)',
          branchHelper: 'Specify the branch to clone. Leave empty to use the repository\'s default branch.',
          helper: 'Cloning will download the remote content into the template center. If the same repository already exists, it will be updated instead.',
          actions: {
            clone: 'Clone Repo',
            cloning: 'Cloning...',
          },
        },
        sshKeys: {
          title: 'SSH Keys Management',
          description: 'Manage SSH key pairs for Git operations.',
          publicKeyLabel: 'Public Key',
          privateKeyLabel: 'Private Key',
          fingerprintLabel: 'Fingerprint',
          lastRotatedLabel: 'Last Updated',
          showPrivateKey: 'Show Private Key',
          hidePrivateKey: 'Hide Private Key',
          notGenerated: 'Not generated yet',
          copy: 'Copy',
          copyToClipboard: 'Copy to clipboard',
          copied: 'Copied',
          copiedDescription: 'Content has been copied to clipboard',
          copyFailed: 'Copy failed',
          copyFailedDescription: 'Unable to copy to clipboard',
          keepPrivateKeySafe: '⚠️ Please keep your private key safe and do not share with others',
          addPublicKeyToGit: '💡 Add this public key to your Git service (GitHub, GitLab, etc.) SSH Keys settings',
          unsavedChanges: '⚠️ You have unsaved changes',
          regenerateWarning: '⚠️ Regenerating will overwrite existing SSH Keys',
          actions: {
            generate: 'Generate New SSH Key Pair',
            regenerate: 'Regenerate SSH Key Pair',
            generating: 'Generating...',
            save: 'Save Changes',
            saving: 'Saving...',
          },
          usageInstructions: {
            title: 'Usage Instructions',
            steps: [
              'Click "Generate SSH Key Pair" button to generate keys',
              'Copy the public key and add it to your Git service provider (GitHub, GitLab, etc.)',
              'Fill in the Git Repository URL (using SSH format) in basic settings',
              'You can now use SSH keys for Git operations',
            ],
          },
          toasts: {
            loadFailed: {
              title: 'Load Failed',
              description: 'Unable to load SSH Keys',
            },
            generating: {
              title: 'Generating SSH Key Pair...',
              description: 'Please wait',
            },
            generateSuccess: {
              title: 'Success',
              description: 'SSH Key Pair generated and saved successfully',
            },
            generateFailed: {
              title: 'Generation Failed',
              description: 'Unable to generate SSH Key Pair',
            },
            saveSuccess: {
              title: 'Save Successful',
              description: 'SSH Keys updated successfully',
            },
            saveFailed: {
              title: 'Save Failed',
              description: 'Unable to save SSH Keys',
            },
          },
        },
      },
      unknownError: 'Unknown error',
      actions: {
        back: 'Back to Template Center',
      },
      toasts: {
        commitSuccess: {
          title: 'Commit successful',
          description: 'Changes have been committed and pushed to remote.',
        },
        commitFailed: {
          title: 'Commit failed',
          description: 'Error committing changes: {{error}}',
        },
        pullSuccess: {
          title: 'Pull successful',
          description: 'Successfully pulled latest changes from remote.',
        },
        pullFailed: {
          title: 'Pull failed',
          description: 'Error pulling from remote: {{error}}',
        },
        syncLocalToRemote: {
          title: 'Sync started',
          description: 'Local settings are being synced to the remote repository.',
        },
        syncRemoteToLocal: {
          title: 'Sync started',
          description: 'Remote repository content is being synced to local settings.',
        },
        gitUserConfigSaved: {
          title: 'Git user updated',
          description: 'Successfully updated Git user name and email.',
        },
        gitUserConfigFailed: {
          title: 'Failed to update Git user',
          description: 'Unable to update Git user information: {{error}}',
        },
        remoteUrlSaved: {
          title: 'Remote URL saved',
          description: 'Origin remote has been updated.',
        },
        remoteUrlFailed: {
          title: 'Failed to save remote URL',
          description: 'Unable to save remote URL: {{error}}',
        },
        initRepoSuccess: {
          title: 'Repository initialized',
          description: 'Template Center is now tracked by Git.',
        },
        initRepoFailed: {
          title: 'Repository initialization failed',
          description: 'Unable to initialize repository: {{error}}',
        },
        cloneRepoSuccess: {
          title: 'Clone successful',
          description: 'Successfully cloned or updated remote repository.',
        },
        cloneRepoStarted: {
          title: 'Clone task submitted',
          description: 'Clone operation is running in the background, please wait...',
        },
        cloneRepoFailed: {
          title: 'Clone failed',
          description: 'Unable to clone repository: {{error}}',
        },
        failed: {
          title: 'Action failed',
          description: 'An error occurred while applying settings. Please try again later.',
        },
        rebuildStarted: {
          title: 'Rebuild task submitted',
          description: 'Template database is being rebuilt in the background, please wait...',
        },
        rebuildFailed: {
          title: 'Rebuild failed',
          description: '{{error}}',
        },
        unknownError: 'Unknown error',
      },
    },
    createDialog: {
      title: 'Create template',
      description: 'Enter a template ID using kebab-case (lowercase letters, numbers, and hyphen only, e.g. my-template).',
      nameLabel: 'Template ID',
      placeholder: 'my-template',
      validation: {
        kebabCase: 'Use kebab-case starting with a lowercase letter (e.g. my-template).',
      },
      actions: {
        cancel: 'Cancel',
        create: 'Create',
        creating: 'Creating...'
      },
      errors: {
        generic: 'Failed to create the template. Please try again later.',
        invalidPayload: 'The template payload is invalid. Check required fields.',
        unauthorized: 'Authentication required. Please sign in again.',
        duplicate: 'Template ID already exists. Choose another ID.',
      },
    },
    toasts: {
      deleteSuccess: {
        title: 'Template deleted',
        description: 'Template "{{name}}" has been removed.',
      },
      deleteFailed: {
        title: 'Failed to delete template',
        description: 'An error occurred while deleting the template. Please try again.',
      },
      exportSuccess: {
        title: 'Export complete',
        description: 'Template "{{name}}" has been exported.',
      },
      exportFailed: {
        title: 'Failed to export template',
        description: 'An error occurred while exporting the template.',
      },
      importSuccess: {
        title: 'Import complete',
        description: 'Template "{{name}}" has been imported.',
      },
      importFailed: {
        title: 'Failed to import template',
        description: 'Unable to import the selected file.',
      },
      installSuccess: {
        title: 'Installation complete',
        description: 'Template "{{template}}" installed to {{workspace}}.',
      },
      installFailed: {
        title: 'Failed to install template',
        description: 'An error occurred while installing the template. Please try again.',
      },
    },
    errors: {
      loadFailed: 'Unable to load template data.',
      unsupportedImport: 'Only JSON or mwtemplate files are supported right now.',
      invalidFileType: 'Please upload a ZIP file.',
    },
    card: {
      features: {
        mcp: 'MCP',
        commands: 'Commands',
        hooks: 'Hooks',
        agentsMd: 'AGENTS.md',
        agents: 'Agents',
        outputStyle: 'Output Style',
        scripts: 'Scripts',
        skills: 'Skills',
      },
      actions: {
        edit: 'Edit',
        export: 'Export',
        delete: 'Delete',
        install: 'Install',
        exporting: 'Exporting...',
      },
    },
    install: {
      title: 'Install {{name}}',
      description: 'Select the target workspace and components to include.',
      workspace: {
        label: 'Workspace',
        placeholder: 'Select a workspace',
      },
      components: {
        label: 'Components',
        selectedCount: '{{selected}} / {{total}}',
      },
      options: {
        mcp: {
          label: 'MCP services',
          description: 'Model Context Protocol servers and connection settings',
        },
        commands: {
          label: 'Commands',
          description: 'Installable commands and command templates for different CLIs',
        },
        hooks: {
          label: 'Hooks',
          description: 'Event triggers and automation flows',
        },
        agentsMd: {
          label: 'AGENTS.md',
          description: 'Primary instruction document and agent guidance',
        },
        agents: {
          label: 'Agents',
          description: 'Agent roles, subagents, and collaboration definitions',
        },
        outputStyle: {
          label: 'Output Style',
          description: 'Output style and formatting preferences',
        },
        scripts: {
          label: 'Template scripts',
          description: 'Bundled scripts and assets',
        },
        skills: {
          label: 'Skills',
          description: 'Skill files and behavioral definitions',
        },
      },
      actions: {
        cancel: 'Cancel',
        confirm: 'Install to {{workspace}}',
      },
      preview: {
        title: 'Install Preview',
        summary: '{{files}} files / {{warnings}} warnings / {{unsupported}} unsupported / {{degradation}} degradation',
        target: 'Target: {{target}}',
        loading: 'Loading compile preview...',
        loadFailed: 'Unable to load install preview',
        none: 'No additional warnings or degradation for this target.',
        sections: {
          warnings: 'Warnings',
          unsupported: 'Unsupported',
          degradation: 'Degradation',
        },
      },
    },
    import: {
      title: 'Import template',
      description: 'Upload a .json or .mwtemplate file to import template settings.',
      selectedFile: 'Selected file: {{name}}',
      actions: {
        cancel: 'Cancel',
        confirm: 'Import',
        importing: 'Importing...',
      },
    },
  },
  editor: {
    loading: 'Loading editor...',
    creating: 'Creating template...',
    header: {
      create: 'Create template',
      edit: 'Edit template: {{name}}',
    },
    toolbar: {
      back: 'Back',
      save: 'Save changes',
      saving: 'Saving...'
    },
    collection: {
      actions: {
        add: 'Add',
      },
      itemTitle: 'Configuration item',
    },
    fileManagement: {
      collection: {
        actions: {
          add: 'Add',
        },
        itemTitle: 'Configuration item',
      },
      header: {
        title: 'Files',
      },
      search: {
        placeholder: 'Search files or folders',
        contentPlaceholder: 'Search file names or contents...',
        button: 'Search',
        clear: 'Clear search',
        results: '{{count}} results found',
      },
      labels: {
        file: 'file',
        folder: 'folder',
        root: 'root',
      },
      actions: {
        create: {
          trigger: 'New',
          upload: 'Upload files',
          folder: 'Create folder',
          file: 'New text file',
        },
        multiSelect: {
          enable: 'Select multiple',
          disable: 'Exit multi-select',
        },
        refresh: 'Reload',
        cancel: 'Cancel',
        delete: 'Delete',
      },
      sidebar: {
        createFile: 'New text file',
        createFolder: 'Create folder',
        upload: 'Upload files',
        refresh: 'Reload',
      },
      multiSelect: {
        summary: 'Selected {{count}} items',
        selectAll: 'Select all',
        unselectAll: 'Clear selection',
      },
      tree: {
        itemCount: '{{count}} items',
        selectedCount: '{{count}} selected',
        empty: 'No files yet. Use the toolbar or right-click to add one.',
        filteredEmpty: 'No items match your filter.',
      },
      viewer: {
        emptyState: 'Select a file to view its contents.',
        noTemplate: 'Please select or create a template first',
        noFile: 'Select a file to start editing',
      },
      editor: {
        actions: {
          save: 'Save',
          cancel: 'Cancel',
          edit: 'Edit',
          copy: 'Copy',
          download: 'Download',
        },
        markdownPlaceholder: 'Enter Markdown content...'
      },
      contextMenu: {
        upload: 'Upload files',
        createFolder: 'Create folder',
        createFile: 'New text file',
        copy: 'Copy',
        paste: 'Paste',
        rename: 'Rename',
        delete: 'Delete',
        deleteMultiple: 'Delete {{count}} items',
      },
      dialogs: {
        createFolder: {
          title: 'Create folder',
          placeholder: 'Folder name',
          confirm: 'Create',
        },
        createFile: {
          title: 'New text file',
          placeholder: 'File name',
          confirm: 'Create',
        },
        rename: {
          title: 'Rename',
          placeholder: 'New name',
          confirm: 'Rename',
        },
        delete: {
          title: 'Delete item',
          description: 'Delete "{{name}}"?',
          folderExtra: 'This will remove the folder and all of its contents.',
          confirm: 'Delete',
        },
      },
      toasts: {
        loadFailed: {
          title: 'Failed to load',
          description: 'Unable to load the file list.',
        },
        save: {
          success: {
            title: 'Saved',
            description: 'Saved "{{name}}".',
          },
          error: {
            title: 'Save failed',
            description: 'Unable to save the file.',
          },
        },
        copyContent: {
          success: {
            title: 'Copied',
            description: 'File content copied to clipboard.',
          },
        },
        create: {
          success: {
            title: 'Created',
            description: 'Created {{type}} "{{name}}".',
          },
          error: {
            title: 'Creation failed',
            description: 'Unable to create the {{type}}. Please try again later.',
          },
        },
        rename: {
          success: {
            title: 'Renamed',
            description: 'Renamed "{{oldName}}" to "{{newName}}".',
          },
          error: {
            title: 'Rename failed',
            description: 'Unable to rename "{{name}}". Please try again later.',
          },
        },
        delete: {
          success: {
            title: 'Deleted',
            description: 'Deleted "{{name}}".',
          },
          error: {
            title: 'Delete failed',
            description: 'Unable to delete "{{name}}". Please try again later.',
          },
        },
        batchDelete: {
          success: {
            title: 'Batch delete complete',
            description: 'Successfully deleted {{count}} item(s).',
          },
          partial: {
            title: 'Partial delete complete',
            description: 'Deleted {{succeeded}} / {{total}} item(s).',
          },
          error: {
            title: 'Batch delete failed',
            description: 'Unable to delete selected items. Please try again later.',
          },
        },
        upload: {
          success: {
            title: 'Upload complete',
            description: 'Uploaded {{count}} file(s).',
          },
          error: {
            title: 'Upload failed',
            description: 'Unable to upload files right now.',
          },
        },
        copy: {
          success: {
            title: 'Copy complete',
            description: 'Copied "{{name}}" to "{{path}}".',
          },
          error: {
            title: 'Copy failed',
            description: 'Unable to copy "{{name}}". Please try again later.',
          },
        },
        paste: {
          error: {
            title: 'Paste failed',
            description: 'Paste operation failed. Please try again later.',
          },
        },
        move: {
          success: {
            title: 'Move complete',
            description: 'Moved "{{name}}" to "{{target}}".',
          },
          error: {
            title: 'Move failed',
            description: 'Unable to move the item.',
          },
        },
        nodeCopy: {
          success: {
            title: 'Copied',
            description: 'Copied "{{name}}".',
          },
        },
      },
    },
    toasts: {
      invalid: {
        title: 'Required fields missing',
        description: 'Please fill in all required fields before saving.',
      },
      createSuccess: {
        title: 'Template created',
        description: 'Template "{{name}}" has been created.',
      },
      createFailed: {
        title: 'Failed to create',
        description: 'Unable to create template. Please try again later.',
      },
      updateSuccess: {
        title: 'Template updated',
        description: 'Template "{{name}}" has been updated.',
      },
      saveSuccess: {
        title: 'Saved successfully',
        description: 'Changes have been saved.',
      },
      saveFailed: {
        title: 'Failed to save',
        description: 'Please try again later.',
      },
      deleteSuccess: {
        title: 'Deleted',
        description: 'Item has been deleted.',
      },
      deleteFailed: {
        title: 'Delete failed',
        description: 'Unable to delete item. Please try again later.',
      },
      error: {
        title: 'Error',
        description: 'Missing template information. Refresh and try again.',
      },
    },
    tabs: {
      basic: 'Basic info',
      agentsMd: 'AGENTS.md',
      hooks: 'Hooks',
      mcp: 'MCP',
      agents: 'Agents',
      commands: 'Commands',
      outputStyle: 'Output Style',
      skills: 'Skills',
      scripts: 'Scripts',
      docs: 'Docs',
    },
    docs: {
      actions: {
        save: 'Save',
        saving: 'Saving...',
      },
    },
    basicInfo: {
      fields: {
        templateId: {
          label: 'Template ID',
          placeholder: 'e.g. java-unittest',
          hint: 'kebab-case format, lowercase letters, numbers and hyphens only, cannot be changed after creation',
        },
        name: {
          label: 'Template name',
          placeholder: 'Enter template name',
        },
        version: {
          label: 'Version',
          placeholder: 'e.g. 1.0.0',
        },
        author: {
          name: {
            label: 'Author name',
            placeholder: 'Enter author name',
          },
          email: {
            label: 'Author email',
            placeholder: 'author@example.com',
          },
          url: {
            label: 'Author URL',
            placeholder: 'https://github.com/author',
          },
        },
        description: {
          label: 'Description',
          placeholder: 'Describe the purpose and use cases of this template',
        },
        category: {
          label: 'Category',
          placeholder: 'Select template category',
        },
        initCommands: {
          label: 'Initialization Commands',
          placeholder: 'Enter bash commands (multi-line)\nExample:\nnpm install\nnpm run build',
          hint: 'These commands will be executed automatically when the template is installed, useful for installing dependencies, initializing environment, etc.',
        },
        keywords: {
          label: 'Keywords',
          placeholder: 'Press Enter to add a keyword',
          remove: 'Remove',
          add: 'Add keyword',
        },
      },
    },
    mcp: {
      empty: {
        title: 'No MCP services yet',
        description: 'Add an MCP service to extend template capabilities.',
      },
      actions: {
        add: 'Add MCP service',
      },
      card: {
        nameFallback: 'MCP Server',
        actions: {
          copyTooltip: 'Copy configuration',
          showEnvValues: 'Show environment variable values',
          hideEnvValues: 'Hide environment variable values',
        },
        toast: {
          title: 'Configuration copied',
          description: 'MCP server "{{name}}" configuration copied to clipboard.',
        },
        sections: {
          headers: 'HTTP Headers',
          command: {
            urlLabel: 'URL',
            commandLabel: 'Command',
            args: 'Arguments: {{args}}',
          },
          environment: {
            title: 'Environment variables',
          },
        },
      },
      dialog: {
        title: {
          create: 'Add MCP server',
          edit: 'Edit MCP server',
        },
        description: {
          create: 'Configure a new Model Context Protocol server.',
          edit: 'Update the MCP server configuration.',
        },
        actions: {
          create: 'Create',
          save: 'Save changes',
        },
        validation: {
          nameRequired: 'Server name is required.',
          descriptionRequired: 'Description is required.',
          commandRequired: 'Command is required for stdio transport.',
          urlRequired: 'Server URL is required for HTTP or SSE transport.',
          urlInvalid: 'Please provide a valid URL.',
        },
        transport: {
          label: 'Transport *',
          placeholder: 'Select a transport type',
          options: {
            stdio: {
              label: 'Stdio (standard input/output)',
              description: 'Runs via command line execution.',
            },
            http: {
              label: 'HTTP (HTTP API)',
              description: 'Connects through an HTTP/HTTPS endpoint.',
            },
            sse: {
              label: 'SSE (Server-Sent Events)',
              description: 'Streams events over an SSE endpoint.',
            },
          },
        },
        fields: {
          name: {
            label: 'Server name *',
            placeholder: 'Enter server name',
          },
          description: {
            label: 'Description *',
            placeholder: 'Enter server description',
          },
          command: {
            label: 'Command *',
            placeholder: 'e.g. python -m my_mcp_server',
          },
          url: {
            label: 'Server URL *',
            placeholderHttp: 'e.g. https://api.example.com/mcp',
            placeholderSse: 'e.g. https://api.example.com/sse',
            hintHttp: 'Full HTTP/HTTPS endpoint.',
            hintSse: 'Full SSE endpoint.',
          },
          args: {
            label: 'Command arguments',
            add: 'Add argument',
            placeholder: 'Argument {{index}}',
            empty: 'No arguments added',
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
            hint: 'Headers for HTTP/SSE connections such as Authorization, Content-Type, etc.',
          },
        },
      },
    },
    commands: {
      sidebar: {
        title: 'Commands',
        searchPlaceholder: 'Search…',
        empty: 'No commands match your filters yet.',
      },
      empty: {
        title: 'No commands yet',
        description: 'Create a new command to guide Claude’s behaviour.',
      },
      actions: {
        add: 'Add command',
        copy: 'Copy content',
        download: 'Download',
        edit: 'Edit',
        delete: 'Delete',
      },
      list: {
        sizeLabel: 'Size: {{size}}',
      },
      logs: {
        copyFailed: 'Failed to copy slash command content:',
      },
      detail: {
        descriptionFallback: 'No description provided.',
      },
      dialog: {
        title: {
          create: 'Add slash command',
          edit: 'Edit slash command',
        },
        description: {
          create: 'Create a custom slash command for Claude.',
          edit: 'Update the slash command details and content.',
        },
        validation: {
          nameRequired: 'Command name is required.',
          contentRequired: 'Content cannot be empty.',
        },
        actions: {
          create: 'Create command',
          save: 'Save changes',
        },
        fields: {
          name: {
            label: 'Command name *',
            placeholder: 'Enter command name',
            helper: 'Must be unique. Use lowercase letters and hyphens.',
          },
          namespace: {
            label: 'Namespace',
            placeholder: 'Enter namespace (optional)',
            helper: 'Groups related commands together.',
          },
          content: {
            label: 'Command content *',
            sizeHint: 'Estimated size: {{size}}',
          },
        },
      },
    },
    hooks: {
      empty: {
        title: 'No hooks yet',
        description: 'Create a hook to automate actions on specific events.',
      },
      actions: {
        add: 'Add hook',
        remove: 'Remove',
        editTooltip: 'Edit hook {{event}}',
        deleteTooltip: 'Delete hook {{event}}',
        editSrLabel: 'Edit hook',
        deleteSrLabel: 'Delete hook',
      },
      card: {
        nameFallback: 'Untitled hook',
        triggerLabel: 'Trigger event:',
        matchersCount: '{{count}} matchers',
        rulesCount: '{{count}} matchers',
        matcherLabel: 'Matcher:',
        actionsCount: '{{count}} actions',
        moreActions: '{{count}} more actions…',
        eventLabel: 'Event',
        matchersAndActions: 'Hook matchers and actions',
        matcherNumber: 'Matcher {{number}}',
        actions: {
          editTooltip: 'Edit hook {{event}}',
          deleteTooltip: 'Delete hook {{event}}',
          editSrLabel: 'Edit hook',
          deleteSrLabel: 'Delete hook',
          remove: 'Remove',
        },
        execution: {
          type: {
            command: 'Command',
            script: 'Script',
            undefined: 'Unknown type',
          },
          empty: 'No content',
        },
        matchers: {
          title: 'Matchers and actions',
          matcherLabel: 'Matcher',
          actionsCount: '{{count}} actions',
          commandLabel: 'Command',
          noCommand: 'No content',
          moreActions: '{{count}} more actions…',
          summary: {
            matchers: '{{count}} matchers',
            commands: '{{count}} commands',
          },
        },
        summary: {
          matchers: '{{count}} matchers',
          actions: '{{count}} actions',
          commands: '{{count}} commands',
          events: '{{count}} events',
        },
        scope: {
          project: 'Project',
        },
        stats: {
          events: '{{count}} events',
        },
      },
      dialog: {
        title: {
          create: 'Add hook',
          edit: 'Edit hook',
          editMerged: 'Edit event hooks',
        },
        description: 'Define hook scope, trigger events, and execution commands.',
        'description.merged': 'Edit all hook rules for this event. You can modify, add, or remove matcher configurations.',
        actions: {
          create: 'Create hook',
          save: 'Save changes',
        },
        validation: {
          missingExecution: 'Each matcher requires at least one valid execution command.',
          duplicateEvent: 'This event type already exists. Please edit the existing hook or choose a different event type.',
          duplicateEventWarning: 'Duplicate event type detected',
          duplicateEventSuggestion: 'Consider editing the existing hook instead of creating a duplicate event.',
        },
        fields: {
          name: {
            label: 'Hook name *',
            placeholder: 'Enter hook name',
          },
          event: {
            label: 'Event *',
            placeholder: 'Select an event',
          },
        },
        matchers: {
          title: 'Matcher configuration',
          add: 'Add matcher',
          patternLabel: 'Matcher pattern',
          patternPlaceholder: 'Tool name pattern (e.g. Write|Edit or *)',
          patternHelp: {
            overview: 'Matches tool names (case-sensitive, PostToolUse only).',
            literal: 'Literal: Write matches only the Write tool.',
            regex: 'Regex: Edit|Write or Notebook.*',
            wildcard: '* matches all tools or leave blank.',
          },
        },
        executions: {
          title: 'Execution configuration',
          add: 'Add execution',
          timeoutLabel: 'Timeout (seconds)',
          timeoutPlaceholder: '30',
          timeoutHelp: 'Maximum command runtime before cancellation.',
          commandLabel: 'Command *',
          commandPlaceholder: 'Enter command to execute',
          commandHelp: 'Environment variables such as $CLAUDE_PROJECT_DIR are supported.',
          remove: 'Remove execution',
        },
      },
      events: {
        preToolUse: {
          label: 'PreToolUse: Runs before tool calls (can block them)',
          description: 'Run before tool invocation (can cancel execution).',
        },
        postToolUse: {
          label: 'PostToolUse: Runs after tool calls complete',
          description: 'Run after tool invocation completes.',
        },
        userPromptSubmit: {
          label: 'UserPromptSubmit: Runs when the user submits a prompt, before Claude processes it',
          description: 'Run when a user submits a prompt before Claude processes it.',
        },
        notification: {
          label: 'Notification: Runs when Claude Code sends notifications',
          description: 'Run when Claude Code emits a notification.',
        },
        stop: {
          label: 'Stop: Runs when Claude Code finishes responding',
          description: 'Run when Claude Code finishes responding.',
        },
        subagentStop: {
          label: 'SubagentStop: Runs when subagent tasks complete',
          description: 'Run when a sub-agent completes its task.',
        },
        preCompact: {
          label: 'PreCompact: Runs before Claude Code is about to run a compact operation',
          description: 'Run before Claude Code performs a compaction step.',
        },
        sessionStart: {
          label: 'SessionStart: Runs when Claude Code starts a new session or resumes an existing session',
          description: 'Run when a new session starts or resumes.',
        },
        sessionEnd: {
          label: 'SessionEnd: Runs when Claude Code session ends',
          description: 'Run when a session ends.',
        },
      },
    },
    agents: {
      sidebar: {
        title: 'Agents',
        searchPlaceholder: 'Search agents…',
        empty: 'No agents match your filters',
      },
      actions: {
        add: 'Add agent',
        copy: 'Copy content',
        download: 'Download',
        edit: 'Edit',
        delete: 'Delete',
      },
      list: {
        sizeLabel: 'Size: {{size}}',
      },
      detail: {
        nameFallback: 'Untitled agent',
        descriptionFallback: 'No description provided.',
      },
      empty: {
        title: 'No agents yet',
        description: 'Create a specialized agent to extend template capabilities.',
      },
      logs: {
        copyFailed: 'Failed to copy agent content:',
      },
      toasts: {
        copySuccess: {
          title: 'Content copied',
          description: 'Agent "{{name}}" content copied to clipboard.',
        },
        copyFailed: {
          title: 'Copy failed',
          description: 'Unable to copy agent content. Please try again.',
        },
        downloadSuccess: {
          title: 'Download started',
          description: 'Downloading agent "{{name}}" as a Markdown file.',
        },
        createSuccess: {
          title: 'Created',
          description: 'Agent "{{name}}" has been created.',
        },
        updateSuccess: {
          title: 'Updated',
          description: 'Agent "{{name}}" has been updated.',
        },
        deleteSuccess: {
          title: 'Deleted',
          description: 'Agent "{{name}}" has been deleted.',
        },
      },
      dialog: {
        title: {
          create: 'Add agent',
          edit: 'Edit agent',
        },
        description: {
          create: 'Create a new agent to collaborate on tasks.',
          edit: 'Update the file name and content for this agent.',
        },
        fields: {
          fileName: {
            label: 'File name *',
            placeholder: 'Enter file name, e.g. data-analyst.md',
            helper: 'Use a descriptive name that reflects the role or expertise.',
          },
          content: {
            label: 'Agent content *',
            sizeHint: 'Estimated size: {{size}}',
            helper: 'Describe behaviour, tools, and expertise for this agent.',
          },
        },
        validation: {
          fileName: 'Please enter a file name.',
          content: 'Content cannot be empty.',
        },
        actions: {
          create: 'Create agent',
          save: 'Save changes',
        },
      },
    },
    outputStyle: {
      sidebar: {
        title: 'Output Style',
        searchPlaceholder: 'Search output styles…',
        empty: 'No output styles match your filters',
      },
      actions: {
        add: 'Add output style',
        copy: 'Copy content',
        download: 'Download',
        edit: 'Edit',
        delete: 'Delete',
      },
      list: {
        sizeLabel: 'Size: {{size}}',
        nameFallback: 'Untitled output style',
      },
      detail: {
        descriptionFallback: 'No description provided.',
      },
      empty: {
        title: 'No output styles yet',
        description: 'Add output styles to customize AI response formats.',
      },
      logs: {
        copyFailed: 'Failed to copy output style content:',
      },
      toasts: {
        copySuccess: {
          title: 'Content copied',
          description: 'Output style "{{name}}" content copied to clipboard.',
        },
        copyFailed: {
          title: 'Copy failed',
          description: 'Unable to copy output style content. Please try again.',
        },
        downloadSuccess: {
          title: 'Download started',
          description: 'Downloading output style "{{name}}" as Markdown file.',
        },
      },
      errors: {
        copyFailed: 'Failed to copy output style content',
      },
      dialog: {
        title: {
          create: 'Add output style',
          edit: 'Edit output style',
        },
        description: {
          create: 'Create a new output style to customize AI response formats.',
          edit: 'Update the file name and content for this output style.',
        },
        fields: {
          fileName: {
            label: 'File name *',
            placeholder: 'Enter file name, e.g. concise-format.md',
            helper: 'Use a descriptive name that reflects the output style.',
          },
          content: {
            label: 'Output style content *',
            sizeHint: 'Estimated size: {{size}}',
            helper: 'Describe the format and rules for this output style.',
          },
        },
        validation: {
          fileName: 'Please enter a file name.',
          content: 'Content cannot be empty.',
        },
        actions: {
          cancel: 'Cancel',
          create: 'Create output style',
          update: 'Update',
          submitting: 'Processing...',
        },
      },
    },
    agentsMd: {
      editor: {
        placeholder: 'Edit AGENTS.md content - the primary instruction document and agent guidance (Markdown supported).',
      },
      status: {
        loading: 'Loading...',
        saving: 'Saving...',
        error: 'Error',
        retry: 'Retry',
      },
      actions: {
        retry: 'Retry',
      },
      toasts: {
        loadFailed: {
          title: 'Load failed',
          description: 'Unable to load AGENTS.md content.',
        },
        saveSuccess: {
          title: 'Saved',
          description: 'AGENTS.md content has been updated.',
        },
        saveFailed: {
          title: 'Save failed',
          description: 'Unable to save AGENTS.md content.',
        },
      },
      errors: {
        loadFailed: 'Unable to load AGENTS.md content, please try again later.',
        saveFailed: 'Unable to save AGENTS.md content, please try again later.',
      },
    },
    files: {
      loading: 'Loading scripts…',
      header: {
        title: 'Script manager',
        badge: '{{count}} scripts',
      },
      actions: {
        add: 'Add',
        addTooltip: 'Add new script',
        copyTooltip: 'Copy script content',
        downloadTooltip: 'Download script',
        cancelEditTooltip: 'Cancel editing',
      },
      filters: {
        searchPlaceholder: 'Search scripts…',
        types: {
          all: 'All',
          files: 'Scripts',
          folders: 'Folders',
        },
      },
      tree: {
        empty: 'No scripts have been added yet',
        deleteTooltip: 'Delete script',
      },
      resize: {
        label: 'Drag to resize panels',
      },
      detail: {
        titleFallback: 'Script content',
        editorPlaceholder: 'Enter script content…',
        emptyFile: 'Script is empty',
        folderHint: 'This is a directory',
        emptySelection: 'Select a script to view its contents',
      },
      logs: {
        loadFailed: 'Failed to load mock scripts:',
        copyFailed: 'Failed to copy script content:',
        saveFailed: 'Failed to save script:',
        createFailed: 'Failed to create script:',
        deleteFailed: 'Failed to delete script:',
      },
      toasts: {
        loadFailed: {
          title: 'Load failed',
          description: 'Unable to load the script list.',
        },
        copySuccess: {
          title: 'Content copied',
          description: 'Script "{{name}}" copied to clipboard.',
        },
        copyFailed: {
          title: 'Copy failed',
          description: 'Unable to copy script content. Please try again.',
        },
        downloadSuccess: {
          title: 'Download started',
          description: 'Downloading "{{name}}" to your device.',
        },
        saveSuccess: {
          title: 'Saved',
          description: 'Script content updated.',
        },
        saveFailed: {
          title: 'Save failed',
          description: 'Unable to save script content.',
        },
        createSuccess: {
          title: 'Created',
          description: '{{type}} has been created.',
        },
        createFailed: {
          title: 'Creation failed',
          description: 'Unable to create {{type}}.',
        },
        deleteSuccess: {
          title: 'Deleted',
          description: 'Script has been removed.',
        },
        deleteFailed: {
          title: 'Delete failed',
          description: 'Unable to delete script.',
        },
      },
      dialog: {
        title: 'Create script',
        description: 'Create a new script or directory.',
        typeLabel: 'Type',
        typeOptions: {
          file: 'Script',
          directory: 'Directory',
        },
        nameLabel: 'Name',
        namePlaceholder: {
          file: 'Script name (e.g. script.sh)',
          directory: 'Directory name',
        },
        actions: {
          create: 'Create',
        },
      },
    },
    validation: {
      required: 'Required',
      select: 'Please select an option',
      commandName: 'Command name is required',
      commandContent: 'Command content is required',
      hookName: 'Hook name is required',
      hookEvent: 'Hook event is required',
      agentFile: 'File name is required',
      agentContent: 'Agent content is required',
      filePath: 'Script path is required',
    },
  },
  detail: {
    loading: 'Loading template details...',
    notFound: 'The requested template could not be found.',
    actions: {
      backToCenter: 'Back to template center',
      back: 'Back',
      edit: 'Edit',
      goToInstall: 'Go to install',
    },
    header: {
      version: 'Version {{version}}',
      author: 'Author {{author}}',
      category: 'Category {{category}}',
    },
    tabs: {
      basicInfo: 'Basic Info',
      agentsMd: 'AGENTS.md',
      hooks: 'Hooks',
      mcp: 'MCP',
      agents: 'Agents',
      commands: 'Commands',
      outputStyle: 'Output Style',
      skills: 'Skills',
      scripts: 'Scripts',
      targetPreview: 'Target Preview',
    },
    targetPreview: {
      description: 'Inspect compiled output files and degradation details for each target CLI.',
      targetLabel: 'Target CLI',
      loading: 'Loading compile preview...',
      emptyFiles: 'No compiled output files for this target yet.',
      sections: {
        files: 'Compiled Output',
        warnings: 'Warnings',
        unsupported: 'Unsupported',
        degradation: 'Degradation',
      },
      file: {
        sourceLabel: 'Source',
        contentPreviewLabel: 'Content Preview',
      },
      states: {
        none: 'No items.',
      },
      errors: {
        loadFailed: 'Unable to load the target compile preview. Please try again later.',
      },
    },
    fileViewer: {
      loading: 'Loading files…',
      loadingContent: 'Loading file content…',
      searchPlaceholder: 'Search files or folders',
      empty: 'No files available yet.',
      emptySearch: 'No files match your search criteria.',
      noSelection: 'Select a file to preview its content.',
      actions: {
        refresh: 'Reload',
      },
      errors: {
        loadTree: 'Unable to load the file list. Please try again later.',
      },
    },
    sidebar: {
      info: {
        title: 'Template information',
        categoryLabel: 'Category',
        versionLabel: 'Version',
      },
      features: {
        title: 'Sections',
      },
      keywords: {
        title: 'Keywords',
      },
    },
    basicInfo: {
      title: 'Basic Information',
      description: 'View detailed template information and statistics',
      sections: {
        general: {
          title: 'General Information',
          description: 'Basic identification information for this template',
        },
        author: {
          title: 'Author Information',
          description: 'Information about the template creator',
        },
        keywords: {
          title: 'Keyword Tags',
          description: 'Keywords for search and categorization',
        },
        features: {
          title: 'Feature Statistics',
          description: 'Count of features included in this template',
        },
        timestamps: {
          title: 'Timestamp Information',
          description: 'Creation and update timestamps',
        },
      },
      fields: {
        name: 'Template Name',
        templateId: 'Template ID',
        version: 'Version',
        cliType: 'CLI Type',
        category: 'Category',
        description: 'Description',
        noDescription: 'No description provided',
        initCommands: 'Initialization Commands',
        authorName: 'Author Name',
        authorEmail: 'Author Email',
        noKeywords: 'No keywords set',
        createdAt: 'Created At',
        updatedAt: 'Updated At',
      },
      stats: {
        mcpServers: 'MCP Servers',
        commands: 'Commands',
        hooks: 'Hooks',
        agents: 'Agents',
        agentsMd: 'AGENTS.md',
        scripts: 'Script Files',
      },
    },
    mcp: {
      downloadFileName: 'mcp-servers.json',
      header: {
        title: 'MCP server configuration',
        description: 'Model Context Protocol servers connected to this template.',
      },
      badge: '{{count}} MCP servers',
      empty: {
        title: 'No MCP servers configured',
        description: 'This template does not include any MCP server definitions yet.',
      },
      actions: {
        download: 'Download configuration',
      },
      toasts: {
        copySuccess: {
          title: 'Configuration copied',
          description: 'MCP server "{{name}}" has been copied to your clipboard.',
        },
        downloadSuccess: {
          title: 'Configuration downloaded',
          description: 'MCP server configuration has been downloaded as a JSON file.',
        },
      },
      card: {
        transport: 'Transport:',
        url: 'Server URL:',
        command: 'Command:',
        args: 'Arguments:',
        env: 'Environment:',
        copyTooltip: 'Copy configuration',
        toast: {
          title: 'Configuration copied',
          description: 'MCP server "{{name}}" configuration copied to clipboard.',
        },
        sections: {
          url: 'URL',
          command: 'Command',
          env: 'Environment variables',
        },
      },
    },
    hooks: {
      downloadFileName: 'hooks-config.json',
      header: {
        title: 'Hook configuration',
        description: 'Manage automation hooks, triggers, and execution commands.',
      },
      badge: '{{count}} hooks',
      actions: {
        download: 'Download configuration',
        copyTooltip: 'Copy configuration',
      },
      empty: {
        title: 'No hooks configured',
        description: 'This template does not include any hooks yet.',
      },
      toasts: {
        downloadSuccess: {
          title: 'Configuration downloaded',
          description: 'Hook configuration has been downloaded as a JSON file.',
        },
        copySuccess: {
          title: 'Configuration copied',
          description: 'Hook "{{name}}" has been copied to your clipboard.',
        },
      },
      events: {
        postToolUse: 'After tool use',
        preToolUse: 'Before tool use',
        notification: 'Notification',
        sessionStart: 'Session start',
        stop: 'Session stop',
      },
      matchers: {
        title: 'Matcher configuration',
        matchLabel: 'Match:',
        actionsCount: '{{count}} actions',
        commandLabel: 'Command',
        emptyCommand: 'No content',
        moreActions: '{{count}} more actions…',
      },
      summary: {
        matchers: '{{count}} matchers',
        actions: '{{count}} actions',
      },
    },
    agentsMd: {
      downloadFileName: 'AGENTS.md',
      header: {
        title: 'AGENTS.md configuration',
        description: 'Global instructions and behaviour configuration for this template.',
      },
      status: {
        configured: 'Configured',
        missing: 'Not configured',
        loading: 'Loading...',
        saving: 'Saving...',
        error: 'Error',
      },
      empty: {
        title: 'AGENTS.md is not configured yet',
        description: 'This template does not include an AGENTS.md configuration file.',
      },
      actions: {
        copy: 'Copy',
        download: 'Download',
        edit: 'Edit',
        create: 'Create AGENTS.md',
        copySuccess: {
          title: 'Copied',
          description: 'AGENTS.md content copied to clipboard.',
        },
        copyFailed: {
          title: 'Copy failed',
          description: 'Unable to copy AGENTS.md content.',
        },
        downloadSuccess: {
          title: 'Download started',
          description: 'AGENTS.md downloaded as Markdown file.',
        },
      },
      toasts: {
        copySuccess: {
          title: 'Copied',
          description: 'AGENTS.md content copied to clipboard.',
        },
        copyFailed: {
          title: 'Copy failed',
          description: 'Unable to copy AGENTS.md content.',
        },
        downloadSuccess: {
          title: 'Download started',
          description: 'AGENTS.md downloaded as Markdown file.',
        },
      },
    },
    agents: {
      accessibility: {
        collapseSidebar: 'Collapse primary sidebar',
      },
      sidebar: {
        title: 'Agents',
        searchPlaceholder: 'Search agents...',
        empty: 'No agents match your filters',
      },
      actions: {
        copy: 'Copy content',
        download: 'Download',
      },
      list: {
        sizeLabel: 'Size: {{size}}',
        nameFallback: 'Unnamed agent',
      },
      detail: {
        descriptionFallback: 'No description provided.',
        noContent: 'No content available',
      },
      empty: {
        title: 'No agents yet',
        description: 'Select or create an agent from the sidebar.',
      },
      errors: {
        copyFailed: 'Failed to copy agent content.',
      },
      toasts: {
        copySuccess: {
          title: 'Content copied',
          description: 'Agent content copied to clipboard.',
        },
        downloadSuccess: {
          title: 'Download started',
          description: 'Downloading agent as Markdown file.',
        },
      },
    },
    outputStyle: {
      accessibility: {
        collapseSidebar: 'Collapse primary sidebar',
      },
      sidebar: {
        title: 'Output Style',
        searchPlaceholder: 'Search output styles...',
        empty: 'No output styles match your filters',
      },
      actions: {
        copy: 'Copy content',
        download: 'Download',
      },
      list: {
        sizeLabel: 'Size: {{size}}',
        nameFallback: 'Unnamed output style',
      },
      detail: {
        descriptionFallback: 'No description provided.',
        noContent: 'No content available',
      },
      empty: {
        title: 'No output styles yet',
        description: 'Select or create an output style from the sidebar.',
      },
      errors: {
        copyFailed: 'Failed to copy output style content.',
      },
      toasts: {
        copySuccess: {
          title: 'Content copied',
          description: 'Output style content copied to clipboard.',
        },
        downloadSuccess: {
          title: 'Download started',
          description: 'Downloading output style as Markdown file.',
        },
      },
    },
    commands: {
      accessibility: {
        collapseSidebar: 'Collapse primary sidebar',
      },
      sidebar: {
        title: 'Commands',
        searchPlaceholder: 'Search commands...',
        scopeLabel: 'Filter by scope',
        scopes: {
          all: 'All scopes',
          project: 'Project',
          user: 'User',
          local: 'Local',
        },
        empty: 'No commands match your filters',
      },
      actions: {
        copy: 'Copy content',
        download: 'Download',
      },
      list: {
        sizeLabel: 'Size: {{size}}',
        nameFallback: 'Unnamed command',
      },
      detail: {
        descriptionFallback: 'No description provided.',
      },
      empty: {
        title: 'No commands yet',
        description: 'Select or create a command from the sidebar to review its details.',
      },
      errors: {
        copyFailed: 'Failed to copy command content.',
      },
    },
    files: {
      sidebar: {
        title: 'Scripts',
        searchPlaceholder: 'Search script path or name...',
        empty: 'No scripts available',
      },
      actions: {
        copy: 'Copy',
        download: 'Download',
      },
      detail: {
        noContent: 'This script has no content.',
        selectPrompt: 'Select a script from the left to view its content.',
      },
      errors: {
        copyFailed: 'Failed to copy file content.',
      },
    },
  },
  errors: {
    templateNotFound: 'Template not found',
    workspaceNotFound: 'Workspace not found',
  },
  common: {
    uncategorized: 'Uncategorized',
    targets: {
      claudeCode: 'Claude Code',
      codex: 'Codex',
      gemini: 'Gemini',
      opencode: 'OpenCode',
    },
    features: {
      mcp: 'MCP',
      commands: 'Commands',
      hooks: 'Hooks',
      agentsMd: 'AGENTS.md',
      agents: 'Agents',
      outputStyle: 'Output Style',
      scripts: 'Scripts',
      skills: 'Skills',
    },
  },
};

export default template;
