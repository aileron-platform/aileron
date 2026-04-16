const versionControl = {
  sidebar: {
    title: {
      changes: '檔案變更清單',
      history: '變更記錄清單',
    },
    loadingTitle: '版本控制面板載入中...',
    loadingDescription: '版本控制面板載入中...',
    toggle: {
      expand: '展開側邊欄',
      collapse: '收折側邊欄',
    },
  },
  main: {
    loadingTitle: '版本控制載入中...',
    loadingDescription: '版本控制載入中...',
    changes: {
      titleWithFile: '檔案變更 Diff：{{path}}',
      titleWithoutFile: '選擇檔案以檢視變更',
    },
    history: {
      titleWithFile: '檔案變更 Diff：{{path}}',
      titleWithCommit: '選擇檔案以檢視變更',
      titleWithoutCommit: '選擇 Commit 以檢視變更',
      descriptionWithCommit: '從左側檔案清單點選檔案',
      descriptionWithoutCommit: '從左側變更記錄清單點選 commit',
    },
  },
  actions: {
    commit: {
      label: '提交',
      tooltip: '提交變更',
    },
    pull: {
      label: '拉取',
      tooltip: '拉取遠端變更',
    },
    push: {
      label: '推送',
      tooltip: '推送本地變更',
    },
    branch: {
      label: '分支',
      tooltip: '分支管理',
    },
    refresh: {
      label: '重整',
      tooltip: '重新整理版本控制狀態',
    },
  },
  gitContext: {
    label: '工作樹',
    ariaLabel: '工作樹',
    option: {
      primary: '主要工作樹 · {{name}}',
      worktree: '工作樹 · {{name}}',
    },
  },
  fileChanges: {
    loading: '載入中...',
    stagedTitle: '已暫存的變更',
    unstagedTitle: '未暫存的變更',
    stageAllTooltip: '暫存所有檔案',
    unstageAllTooltip: '取消所有暫存',
    loadMore: '載入更多',
    loadingMore: '載入中...',
  },
  commitForm: {
    placeholder: '提交訊息',
    submit: '提交',
    submitting: '提交中...',
  },
  commitHistory: {
    loading: '載入提交歷史...',
    title: '變更記錄',
    empty: '沒有提交歷史',
    filesTitle: '檔案變更',
    filesDescription: '選擇 commit 以檢視變更檔案',
    selectPrompt: '請先選擇一個 commit',
    fileCount_other: '{{count}} 個檔案',
    time: {
      daysAgo_other: '{{count}} 天前',
      hoursAgo_other: '{{count}} 小時前',
      minutesAgo_other: '{{count}} 分鐘前',
      justNow: '剛剛',
    },
  },
  commitFiles: {
    title: '檔案變更',
    subtitle_other: '{{count}} 個檔案變更',
    empty: '此提交沒有檔案變更',
    status: {
      modified: '修改',
      added: '新增',
      deleted: '刪除',
      renamed: '重新命名',
      unknown: '未知',
    },
  },
  fileItem: {
    unstageTooltip: '取消暫存',
    stageTooltip: '暫存',
    discard: '捨棄變更',
    unstage: '取消暫存',
    stage: '暫存',
    selectedCount_other: '已選擇 {{count}} 個檔案',
    stageMultiple_other: '暫存 {{count}} 個檔案',
    discardMultiple_other: '捨棄 {{count}} 個檔案的變更',
    unstageMultiple_other: '取消暫存 {{count}} 個檔案',
  },
  diff: {
    loading: '載入差異內容...',
    empty: '選擇檔案以查看差異',
    noDifference: '此檔案沒有差異',
  },
  errors: {
    loadFailed: '載入失敗',
    notInitialized: {
      title: '此工作區尚未初始化為 Git 儲存庫',
      description: '請先在工作區終端機執行 `git init`，或從現有 Git 倉庫複製檔案後再使用版本控制功能。',
    },
  },
};

export default versionControl;
