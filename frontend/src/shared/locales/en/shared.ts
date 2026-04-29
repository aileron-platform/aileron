const shared = {
  versionControl: {
    actions: {
      menu: {
        label: 'Git actions',
      },
      branch: {
        label: 'Branches',
        create: 'Create branch',
      },
      refresh: {
        label: 'Refresh',
      },
      fetch: {
        label: 'Fetch',
      },
      pull: {
        label: 'Pull',
      },
      push: {
        label: 'Push',
      },
      remoteSettings: {
        label: 'Remote settings',
      },
    },
    branchDialog: {
      title: 'Create branch',
      description: 'Create a branch from the current repository state or an optional start point.',
      nameLabel: 'Branch name',
      namePlaceholder: 'Branch name',
      startPointLabel: 'Start point',
      startPointPlaceholder: 'Start point',
      stashChanges: 'Stash local changes before checkout',
      cancel: 'Cancel',
      create: 'Create branch',
      creating: 'Creating...',
    },
    remoteDialog: {
      title: 'Remote settings',
      description: 'Configure this repository remote and setup workflow.',
      initialized: {
        title: 'Git repository is initialized',
        branch: 'Branch: {{branch}}',
        noBranch: 'No branch',
      },
      setup: {
        localContentWarning: 'Local content already exists. Clone is available only when it can be completed safely.',
        actions: {
          init: 'Initialize repository',
          initializing: 'Initializing...',
        },
      },
      remote: {
        missingOrigin: 'No origin remote is configured. Remote sync actions are disabled until a remote URL is saved.',
        urlLabel: 'Remote URL',
        urlPlaceholder: 'git@example.com:team/repo.git',
        helper: 'This URL is saved as the origin remote for fetch, pull, and push.',
        actions: {
          save: 'Save remote',
          saving: 'Saving...',
        },
      },
      clone: {
        urlLabel: 'Repository URL',
        branchLabel: 'Branch',
        branchPlaceholder: 'main',
        branchHelper: 'Leave blank to use the remote default branch.',
        helper: 'Clone a remote repository into this storage location.',
        disabledHelper: 'Clone is disabled because this location already contains content.',
        actions: {
          clone: 'Clone repository',
          cloning: 'Cloning...',
        },
        progressTitle: 'Clone progress',
      },
    },
    main: {
      selectFile: 'Select a file to view changes',
      selectCommitFile: 'Select a file to view changes',
    },
    mode: {
      fileChanges: 'File Changes',
      commitHistory: 'History',
    },
    fileChanges: {
      loading: 'Loading...',
      stagedTitle: 'Staged changes',
      unstagedTitle: 'Unstaged changes',
      empty: 'No file changes',
      stageAllTooltip: 'Stage all files',
      unstageAllTooltip: 'Unstage all files',
      loadingMore: 'Loading...',
    },
    commitForm: {
      placeholder: 'Commit message',
      submit: 'Commit',
      submitting: 'Committing...',
    },
    commitHistory: {
      title: 'Commit history',
      empty: 'No commit history',
      selectPrompt: 'Select a commit first',
      commitCount_one: '{{count}} commit',
      commitCount_other: '{{count}} commits',
      filters: {
        allBranches: 'All branches',
        searchPlaceholder: 'Search commits',
        searchAriaLabel: 'Search commits',
      },
      time: {
        daysAgo_one: '{{count}} day ago',
        daysAgo_other: '{{count}} days ago',
        hoursAgo_one: '{{count}} hour ago',
        hoursAgo_other: '{{count}} hours ago',
        minutesAgo_one: '{{count}} minute ago',
        minutesAgo_other: '{{count}} minutes ago',
        justNow: 'Just now',
      },
    },
    commitFiles: {
      title: 'File changes',
      empty: 'This commit has no file changes',
      fileCount_one: '{{count}} file',
      fileCount_other: '{{count}} files',
      status: {
        modified: 'Modified',
        added: 'Added',
        deleted: 'Deleted',
        renamed: 'Renamed',
        unknown: 'Unknown',
      },
    },
    fileItem: {
      unstageTooltip: 'Unstage file',
      stageTooltip: 'Stage file',
      discard: 'Discard changes',
      unstage: 'Unstage',
      stage: 'Stage',
      selectedCount_one: '{{count}} file selected',
      selectedCount_other: '{{count}} files selected',
      stageMultiple_one: 'Stage {{count}} file',
      stageMultiple_other: 'Stage {{count}} files',
      discardMultiple_one: 'Discard changes for {{count}} file',
      discardMultiple_other: 'Discard changes for {{count}} files',
      unstageMultiple_one: 'Unstage {{count}} file',
      unstageMultiple_other: 'Unstage {{count}} files',
    },
    diff: {
      loading: 'Loading diff...',
      empty: 'Select a file to view the diff',
      noDifference: 'No differences found in this file',
      loadFailed: 'Failed to load diff',
      binaryOrLarge: 'Unable to display file content',
      filePath: 'File path: {{path}}',
    },
  },
};

export default shared;
