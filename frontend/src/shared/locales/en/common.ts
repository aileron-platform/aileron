const common = {
  welcome: 'Welcome, {{name}}',
  loading: 'Loading...',
  authChecking: 'Verifying user...',
  notFound: 'Page not found',
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
      noWorkspaceErrorMessage: '尚未建立任何工作區',
      invalidWorkspaceErrorMessage: '找不到有效的工作區',
      noWorkspaceHint: 'Please create a workspace to get started',
      createWorkspace: 'Create New Workspace',
      deleteWorkspace: 'Delete Workspace',
      deleteConfirmMessage: 'Are you sure you want to delete this workspace? This will permanently delete all related data and cannot be undone.',
      troubleshoot: 'If the problem persists, please check the workspace service status',
    }
  },

  // Session Viewer
  sessionViewer: {
    title: 'Conversation History',
    description: 'View complete AI conversation',
    messagesTitle: 'Messages',
    loading: 'Loading conversation...',
    noMessages: 'No messages in this conversation',
    refresh: 'Reload',
    retry: 'Retry',
    stats: {
      messages: 'Messages',
      tokens: 'Tokens',
      duration: 'Duration',
      cost: 'Cost',
    },
    status: {
      idle: 'Idle',
      running: 'Running',
      completed: 'Completed',
      failed: 'Failed',
      aborted: 'Aborted',
    },
    source: {
      user: 'User',
      task: 'Automation Task',
      system: 'System',
    },
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

  // Task progress
  taskProgress: {
    title: 'Task progress',
    progress: 'Progress',
    startedAt: 'Started at',
    completedAt: 'Completed at',
    status: {
      completed: '✓ Completed',
      failed: '✗ Failed',
      running: '⏳ Running',
      pending: '⏱ Pending',
      cancelled: '⊗ Cancelled',
    },
    syncedCount: 'Synced {{count}} items',
    close: 'Close',
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
      folderWarning: '⚠️ All files inside the folder will also be deleted',
    },
    // Batch delete
    batchDelete: {
      title: 'Confirm Batch Delete',
      description: 'This action cannot be undone',
      summary: 'About to delete {{count}} items:',
      fileCount: '{{count}} files',
      folderCount: '{{count}} folders',
      folderWarning: '⚠️ All files inside the folders will also be deleted',
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
