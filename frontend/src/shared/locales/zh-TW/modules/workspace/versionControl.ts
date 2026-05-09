const versionControl = {
  sidebar: {
    title: {
      changes: '檔案變更',
      history: '變更記錄',
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
  worktree: {
    menu: {
      moreActions: '更多動作',
      group: '工作樹',
      settings: '工作樹設定...',
      create: '建立工作樹...',
      comingSoon: '即將推出',
    },
    dialog: {
      title: '工作樹設定',
      description: '選擇用來放置 Git 工作樹的工作區子目錄。',
      fieldLabel: '目錄路徑',
      helper: '請使用 /workspace 底下的相對子目錄路徑，例如 branches/team-a。',
      cancel: '取消',
      save: '儲存',
      saving: '儲存中...',
    },
    validation: {
      empty: '請輸入目錄路徑。',
      separator: '請使用相對目錄路徑，不可用開頭或結尾斜線，也不可包含空路徑片段。',
      parentTraversal: '目錄名稱不可包含上層路徑片段。',
      tooLong: '目錄路徑不得超過 64 個字元。',
    },
    toast: {
      loadFailed: {
        title: '無法載入工作樹設定',
        description: '請重新開啟對話框再試一次。',
      },
      saveSuccess: {
        title: '工作樹設定已儲存',
        description: 'Runtime 會同步 .gitignore 管理區塊。',
      },
      saveFailed: {
        title: '無法儲存工作樹設定',
        description: '請檢查輸入內容後再試一次。',
      },
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
    loading: '載入變更記錄...',
    title: '變更記錄',
    empty: '沒有變更記錄',
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
    loadFailed: '載入差異內容失敗',
    binaryOrLarge: '無法顯示檔案內容',
    filePath: '檔案路徑：{{path}}',
  },
  errors: {
    loadFailed: '載入失敗',
    notInitialized: {
      title: '此工作區尚未初始化為 Git 儲存庫',
      description: '請先在工作區終端機執行 `git init`，或從現有 Git 倉庫複製檔案後再使用版本控制功能。',
    },
  },
  toasts: {
    refreshSuccess: {
      title: '版本控制已重整',
    },
    refreshFailed: {
      title: '重整失敗',
      description: '無法重整版本控制資料。',
    },
    fetchSuccess: {
      title: 'Fetch 已完成',
    },
    fetchFailed: {
      title: 'Fetch 失敗',
      description: '無法 fetch 遠端參照。',
    },
    pullSuccess: {
      title: '拉取已完成',
    },
    pullFailed: {
      title: '拉取失敗',
      description: '無法拉取遠端變更。',
    },
    pushSuccess: {
      title: '推送已完成',
    },
    pushFailed: {
      title: '推送失敗',
      description: '無法推送本地變更。',
    },
    remoteUrlSuccess: {
      title: '遠端 URL 已儲存',
    },
    remoteUrlFailed: {
      title: '遠端 URL 儲存失敗',
      description: '請確認遠端 URL 後再試一次。',
    },
    checkoutSuccess: {
      title: '已切換分支',
      description: '已切換到 {{branch}}。',
      stashedDescription: '已切換分支，並將本地變更 stash 為 {{stash}}。',
    },
    checkoutFailed: {
      title: '切換分支失敗',
      description: '無法切換到選取的分支。',
    },
    createBranchSuccess: {
      title: '已建立分支',
      description: '已建立並切換到 {{branch}}。',
      stashedDescription: '已建立並切換到 {{branch}}，且將本地變更 stash 為 {{stash}}。',
    },
    createBranchFailed: {
      title: '建立分支失敗',
      description: '無法建立分支。',
    },
    commitSuccess: {
      title: '已建立 commit',
    },
    commitFailed: {
      title: 'Commit 失敗',
      description: '無法建立 commit。',
    },
    stageFailed: {
      title: '暫存失敗',
      description: '無法暫存選取的檔案。',
    },
    unstageFailed: {
      title: '取消暫存失敗',
      description: '無法取消暫存選取的檔案。',
    },
    discardFailed: {
      title: '捨棄變更失敗',
      description: '無法捨棄選取的變更。',
    },
  },
};

export default versionControl;
