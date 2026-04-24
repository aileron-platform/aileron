const shared = {
  versionControl: {
    actions: {
      menu: {
        label: 'Git actions',
      },
      branch: {
        label: 'Branches',
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
    },
    main: {
      selectFile: 'Select a file to view changes',
      selectCommitFile: 'Select a file to view changes',
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
