const shared = {
  versionControl: {
    actions: {
      menu: {
        label: 'Git 操作',
      },
      branch: {
        label: '分支',
        create: '建立分支',
      },
      refresh: {
        label: '重整',
      },
      fetch: {
        label: 'Fetch',
      },
      pull: {
        label: '拉取',
      },
      push: {
        label: '推送',
      },
    },
    main: {
      selectFile: '選擇檔案以檢視變更',
      selectCommitFile: '選擇檔案以檢視變更',
    },
    fileChanges: {
      loading: '載入中...',
      stagedTitle: '已暫存的變更',
      unstagedTitle: '未暫存的變更',
      empty: '沒有檔案變更',
      stageAllTooltip: '暫存所有檔案',
      unstageAllTooltip: '取消所有暫存',
      loadingMore: '載入中...',
    },
    commitForm: {
      placeholder: '提交訊息',
      submit: '提交',
      submitting: '提交中...',
    },
    commitHistory: {
      title: '變更記錄',
      empty: '沒有提交歷史',
      selectPrompt: '請先選擇一個 commit',
      commitCount_other: '{{count}} commits',
      filters: {
        allBranches: '所有分支',
        searchPlaceholder: '搜尋 commit',
        searchAriaLabel: '搜尋 commit',
      },
      time: {
        daysAgo_other: '{{count}} 天前',
        hoursAgo_other: '{{count}} 小時前',
        minutesAgo_other: '{{count}} 分鐘前',
        justNow: '剛剛',
      },
    },
    commitFiles: {
      title: '檔案變更',
      empty: '此提交沒有檔案變更',
      fileCount_other: '{{count}} 個檔案',
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
  },
};

export default shared;
