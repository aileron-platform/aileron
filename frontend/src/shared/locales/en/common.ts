const common = {
  welcome: 'Welcome, {{name}}',
  loading: 'Loading...',
  entry: {
    title: 'Opening workspace',
    descriptions: {
      identity: 'We are confirming your identity.',
      identityFailed: 'Identity confirmation did not complete. Sign in again.',
      workspace: 'We are confirming the workspace and your access.',
      workspaceFailed: 'The workspace could not be confirmed. Check access or return.',
      execution: 'We are preparing the workspace execution environment.',
      executionFailed: 'The execution environment needs attention. Use an available action or return.',
      executionPlaneDrift: 'The workspace execution environment is out of sync with the platform. Delete the workspace to clear it safely.',
    },
    stages: {
      label: 'Workspace entry stages',
      identity: 'Confirm identity',
      workspace: 'Confirm workspace',
      execution: 'Prepare execution environment',
    },
    status: {
      pending: 'Not started',
      active: 'In progress',
      complete: 'Complete',
      action_required: 'Action required',
      uncertain: 'Waiting for confirmation',
      failed: 'Incomplete',
    },
    reasonCode: 'Reason code',
    copyReasonCode: 'Copy reason code',
    reasonCodeCopied: 'Reason code copied',
    confirmRebuild: 'Rebuild this workspace execution environment?',
    executionPlaneDrift: {
      contactOwner: 'Contact the workspace owner or an administrator to delete this workspace.',
    },
    actions: {
      login: 'Sign in again',
      create: 'Create workspace',
      refresh: 'Check again',
      start: 'Start workspace',
      retry: 'Retry recovery',
      rebuild: 'Rebuild execution environment',
      return: 'Return to workspaces',
    },
  },
  notFound: 'Page not found',
  authorization: {
    accessDeniedTitle: 'Access denied',
    accessDeniedDescription: 'You do not have permission to access this feature.',
    readOnlyDescription: 'You can view this content, but you do not have permission to change it.',
  },
  errors: {
    generic: 'Something went wrong. Try again.',
  },
  save: 'Save',
  cancel: 'Cancel',
  confirm: 'Confirm',
  delete: 'Delete',
  edit: 'Edit',
  add: 'Add',
  search: 'Search',
  filter: 'Filter',
  refresh: 'Refresh',
  close: 'Close',
  back: 'Back',
  next: 'Next',
  previous: 'Previous',
  submit: 'Submit',
  reset: 'Reset',
  retry: 'Retry',
  reconnect: 'Reconnect',
  reconnecting: 'Reconnecting...',
  // Error page related
  error: {
    workspaceRuntime: {
      title: 'Workspace Connection Failed',
      connectionFailed: 'Workspace is not started or unable to connect',
      noWorkspace: 'No Workspace Created',
      noWorkspaceErrorMessage: 'No workspace has been created yet',
      invalidWorkspaceErrorMessage: 'No valid workspace was found',
      noWorkspaceHint: 'Please create a workspace to get started',
      createWorkspace: 'Create New Workspace',
      troubleshoot: 'If the problem persists, please check the workspace service status',
    }
  },

  // File tree components
  fileTree: {
    toolbar: {
      title: 'Files',
      moreActions: 'More actions',
    },
    sidebar: {
      expand: 'Expand sidebar',
      collapse: 'Collapse sidebar',
    },
    search: {
      placeholder: 'Search files or folders',
      button: 'Search',
    },
    context: {
      viewImage: 'View image',
    },
    contextMenu: {
      view: 'View',
      upload: 'Upload file',
      createFolder: 'Create folder',
      createFile: 'New file',
      open: 'Open',
      download: 'Download',
      downloadAsZip: 'Download as ZIP',
      downloadSelected: 'Download {{count}} selected items',
      viewImage: 'View image',
      extractArchive: 'Extract archive',
      copy: 'Copy',
      copyPath: 'Copy path',
      paste: 'Paste',
      rename: 'Rename',
      delete: 'Delete',
      deleteSelected: 'Delete {{count}} items',
      refresh: 'Refresh',
    },
    operations: {
      createFile: {
        success: 'Created',
        successDesc: 'File "{{name}}" created successfully.',
        error: 'Create failed',
      },
      createFolder: {
        success: 'Created',
        successDesc: 'Folder "{{name}}" created successfully.',
        error: 'Create failed',
      },
      rename: {
        success: 'Renamed',
        successDesc: 'Renamed to "{{name}}".',
        error: 'Rename failed',
      },
      delete: {
        success: 'Deleted',
        successDesc: 'Deleted "{{name}}".',
        error: 'Delete failed',
      },
      batchDelete: {
        success: 'Batch delete complete',
        successDesc: 'Deleted {{count}} items.',
        error: 'Batch delete failed',
      },
    },
    multiSelect: {
      selectAll: 'Select All',
      unselectAll: 'Unselect All',
      selectedCount: '{{count}} items selected',
      clearSelection: 'Clear selection',
    },
    empty: {
      title: 'No files',
      description: 'Use the actions above to add files or folders',
    },
    searchEmpty: {
      title: 'No matching files found',
      description: 'Try using different search keywords',
    },
    error: {
      title: 'Loading failed',
      description: 'Unable to load file tree, please try again later',
    },
  },
  fileEditor: {
    save: {
      success: 'Saved',
      successDesc: 'Saved "{{name}}".',
      error: 'Save failed',
    },
    copy: {
      success: 'Copied',
      successDesc: 'Content copied to clipboard.',
      error: 'Copy failed',
    },
    download: {
      success: 'Downloaded',
      successDesc: 'Downloaded "{{name}}".',
    },
    actions: {
      save: 'Save',
      cancel: 'Cancel',
      edit: 'Edit',
      copy: 'Copy',
      download: 'Download',
    },
    markdown: {
      placeholder: 'Enter Markdown content...',
    },
    emptyFile: 'This file is currently empty.',
    unknownError: 'Unknown error',
  },
  markdownFileViewer: {
    units: {
      chars: '{{count}} chars',
      bytes: '{{count}} bytes',
    },
  },

  hookEvents: {
    PreToolUse: { label: 'PreToolUse', description: 'Runs before a tool call.' },
    PostToolUse: { label: 'PostToolUse', description: 'Runs after a tool call.' },
    PermissionRequest: { label: 'PermissionRequest', description: 'Runs when Codex requests permission.' },
    UserPromptSubmit: { label: 'UserPromptSubmit', description: 'Runs when the user submits a prompt.' },
    Notification: { label: 'Notification', description: 'Runs when a notification is emitted.' },
    Stop: { label: 'Stop', description: 'Runs when the main agent stops.' },
    SubagentStop: { label: 'SubagentStop', description: 'Runs when a subagent stops.' },
    PreCompact: { label: 'PreCompact', description: 'Runs before context compaction.' },
    SessionStart: { label: 'SessionStart', description: 'Runs when a session starts.' },
    SessionEnd: { label: 'SessionEnd', description: 'Runs when a session ends.' },
    Setup: { label: 'Setup', description: 'Runs during Claude Code setup.' },
    UserPromptExpansion: { label: 'UserPromptExpansion', description: 'Runs when Claude expands a user prompt.' },
    PostToolUseFailure: { label: 'PostToolUseFailure', description: 'Runs after a tool call fails.' },
    PostToolBatch: { label: 'PostToolBatch', description: 'Runs after a tool batch completes.' },
    PermissionDenied: { label: 'PermissionDenied', description: 'Runs when permission is denied.' },
    StopFailure: { label: 'StopFailure', description: 'Runs when stop handling fails.' },
    SubagentStart: { label: 'SubagentStart', description: 'Runs when a subagent starts.' },
    TeammateIdle: { label: 'TeammateIdle', description: 'Runs when a teammate becomes idle.' },
    TaskCreated: { label: 'TaskCreated', description: 'Runs when a task is created.' },
    TaskCompleted: { label: 'TaskCompleted', description: 'Runs when a task completes.' },
    ConfigChange: { label: 'ConfigChange', description: 'Runs when configuration changes.' },
    CwdChanged: { label: 'CwdChanged', description: 'Runs when the working directory changes.' },
    FileChanged: { label: 'FileChanged', description: 'Runs when watched files change.' },
    InstructionsLoaded: { label: 'InstructionsLoaded', description: 'Runs when instructions are loaded.' },
    PostCompact: { label: 'PostCompact', description: 'Runs after context compaction.' },
    WorktreeCreate: { label: 'WorktreeCreate', description: 'Runs when a worktree is created.' },
    WorktreeRemove: { label: 'WorktreeRemove', description: 'Runs when a worktree is removed.' },
    Elicitation: { label: 'Elicitation', description: 'Runs during MCP elicitation.' },
    ElicitationResult: { label: 'ElicitationResult', description: 'Runs after MCP elicitation completes.' },
    MessageDisplay: { label: 'MessageDisplay', description: 'Runs when Claude Code displays a message.' },
    DirectoryAdded: { label: 'DirectoryAdded', description: 'Runs when a directory is added to the session.' },
  },

  // File operation dialogs
  fileOperations: {
    // Create file/folder
    create: {
      file: {
        title: 'New File',
        description: 'Enter file name',
        placeholder: 'e.g., index.ts',
      },
      folder: {
        title: 'New Folder',
        description: 'Enter folder name',
        placeholder: 'e.g., components',
      },
      nameLabel: 'Name',
    },
    // Rename
    rename: {
      title: 'Rename',
      description: 'Enter new name',
      nameLabel: 'New Name',
    },
    // Delete
    delete: {
      title: 'Confirm Delete',
      description: 'This action cannot be undone',
      file: 'Are you sure you want to delete file {{name}}?',
      folder: 'Are you sure you want to delete folder {{name}}?',
      folderWarning: 'All files inside the folder will also be deleted',
      unsavedTabs: '{{count}} unsaved open tabs will be affected.',
    },
    // Batch delete
    batchDelete: {
      title: 'Confirm Batch Delete',
      description: 'This action cannot be undone',
      summary: 'About to delete {{count}} items:',
      fileCount: '{{count}} files',
      folderCount: '{{count}} folders',
      folderWarning: 'All files inside the folders will also be deleted',
      deleteAll: 'Delete All',
    },
    // Buttons
    buttons: {
      cancel: 'Cancel',
      confirm: 'Confirm',
      delete: 'Delete',
    },
    // Validation errors
    validation: {
      nameRequired: 'Name cannot be empty',
      nameWithPath: 'Name cannot contain path separators (/ or \\)',
      nameWithInvalidChars: 'Name contains invalid characters',
      nameReserved: 'This name is reserved by the system',
      nameSame: 'New name is the same as the current name',
      nameExists: '{{name}} already exists. Choose a different name.',
    },
    // Success messages
    success: {
      fileCreated: 'File created successfully',
      folderCreated: 'Folder created successfully',
      fileRenamed: 'File renamed successfully',
      fileDeleted: 'File deleted successfully',
      fileMoved: 'File moved successfully',
      fileSaved: 'File saved successfully',
      fileCopied: 'File copied successfully',
      fileUploaded: 'File uploaded successfully',
      noItemsToDelete: 'No items to delete',
    },
    // Error messages
    error: {
      fileCreateFailed: 'Failed to create file',
      folderCreateFailed: 'Failed to create folder',
      fileRenameFailed: 'Failed to rename file',
      fileDeleteFailed: 'Failed to delete file',
      batchDeleteFailed: 'Failed to batch delete',
      fileCopyFailed: 'Failed to copy file',
      fileMoveFailed: 'Failed to move file',
      fileUploadFailed: 'Failed to upload file',
      fileOperationFailed: 'File operation failed',
      fileSaveFailed: 'Failed to save file',
      packageTaskFailed: 'Package task failed',
      loadTreeFailed: 'Failed to load file tree',
    },
  },

  // Slash Command picker
  slashCommand: {
    picker: {
      title: 'Select Slash Command',
      description: 'Choose a command from the library to quickly fill in your prompt.',
      searchPlaceholder: 'Search by name, description, or tags...',
      empty: 'No matching commands',
      scope: {
        all: 'All',
        project: 'Project',
        user: 'Personal',
        plugin: 'Plugin',
      },
      kind: {
        'slash-command': 'Command',
        skill: 'Skill',
      },
    },
  },

  // Markdown editor
  markdownEditor: {
    placeholder: 'Enter content...\nMarkdown syntax supported',
    actions: {
      preview: 'Preview',
      backToEdit: 'Back to edit',
    },
    toolbar: {
      bold: 'Bold',
      italic: 'Italic',
      link: 'Link',
      code: 'Code',
      image: 'Image',
      unorderedList: 'Bulleted list',
      orderedList: 'Numbered list',
      quote: 'Quote',
      undo: 'Undo',
      redo: 'Redo',
    },
    charCount: 'Characters: {{count}}',
    placeholders: {
      quote: 'Quote content',
      bold: 'Bold text',
      italic: 'Italic text',
      link: 'Link text',
      code: 'Code',
      description: 'Description',
      listItem: 'Item',
    },
  },

  // Other messages
  messages: {
    unauthorized: 'Please log in first',
    unknownError: 'Unknown error',
    cannotConnect: 'Cannot connect to preview service',
    userRejected: 'User rejected execution',
    noWorkspaceFound: 'No valid workspace found',
    noWorkspaceCreated: 'No workspace has been created yet',
    workspaceRuntimeNotStarted: 'Workspace Runtime has not started or URL not provided',
    executionNoWorkspace: 'Cannot view conversation: Execution has no associated workspace',
    cannotViewSession: 'Cannot view conversation: {{error}}',
    terminalConnectionFailed: 'Failed to create terminal connection URL',
    terminalError: 'Terminal connection error occurred',
    cannotGetUserInfo: 'Cannot get user information',
    loginFailed: 'Login failed',
    registerFailed: 'Registration failed',
    fallbackOwnerName: 'Scheduled Task',
    waitingComplete: 'Waiting to complete...',
    cannotGetSyncStatus: 'Cannot get sync status',
    syncError: 'An error occurred during synchronization',
    syncFailed: 'Synchronization failed',
  },

  // Template management error messages
  template: {
    errors: {
      loadFailed: 'Failed to load',
      createFailed: 'Failed to create',
      updateFailed: 'Failed to update',
      deleteFailed: 'Failed to delete',
      saveFailed: 'Failed to save',
      uploadFailed: 'Failed to upload',
      renameFailed: 'Failed to rename',
      moveFailed: 'Failed to move',
      copyFailed: 'Failed to copy',
      searchFailed: 'Failed to search',
      batchDeleteFailed: 'Failed to batch delete',
      loadContentFailed: 'Failed to load file content',
    },
  },
};

export default common;
