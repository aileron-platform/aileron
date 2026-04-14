const versionControl = {
  sidebar: {
    title: {
      changes: 'File change list',
      history: 'Commit history list',
    },
    loadingTitle: 'Loading version control panel...',
    loadingDescription: 'Loading version control panel...',
    toggle: {
      expand: 'Expand sidebar',
      collapse: 'Collapse sidebar',
    },
  },
  main: {
    loadingTitle: 'Loading version control...',
    loadingDescription: 'Version control is loading...',
    changes: {
      titleWithFile: 'File diff: {{path}}',
      titleWithoutFile: 'Select a file to view changes',
    },
    history: {
      titleWithFile: 'File diff: {{path}}',
      titleWithCommit: 'Select a file to view changes',
      titleWithoutCommit: 'Select a commit to view changes',
      descriptionWithCommit: 'Choose a file from the file list on the left.',
      descriptionWithoutCommit: 'Choose a commit from the history list on the left.',
    },
  },
  actions: {
    commit: {
      label: 'Commit',
      tooltip: 'Commit changes',
    },
    pull: {
      label: 'Pull',
      tooltip: 'Pull remote changes',
    },
    push: {
      label: 'Push',
      tooltip: 'Push local changes',
    },
    branch: {
      label: 'Branches',
      tooltip: 'Manage branches',
    },
    refresh: {
      label: 'Refresh',
      tooltip: 'Refresh version control status',
    },
  },
  fileChanges: {
    loading: 'Loading...',
    stagedTitle: 'Staged changes',
    unstagedTitle: 'Unstaged changes',
    stageAllTooltip: 'Stage all files',
    unstageAllTooltip: 'Unstage all files',
    loadMore: 'Load More',
    loadingMore: 'Loading...',
  },
  commitForm: {
    placeholder: 'Commit message',
    submit: 'Commit',
    submitting: 'Committing...',
  },
  commitHistory: {
    loading: 'Loading commit history...',
    title: 'Commit history',
    empty: 'No commit history',
    filesTitle: 'File changes',
    filesDescription: 'Select a commit to view changed files',
    selectPrompt: 'Select a commit first',
    fileCount_one: '{{count}} file',
    fileCount_other: '{{count}} files',
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
    subtitle_one: '{{count}} changed file',
    subtitle_other: '{{count}} changed files',
    empty: 'This commit has no file changes',
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
  },
  errors: {
    loadFailed: 'Failed to load',
    notInitialized: {
      title: 'This workspace is not yet a Git repository',
      description: 'Run `git init` in the workspace terminal, or clone an existing Git repository before using version control features.',
    },
  },
};

export default versionControl;
