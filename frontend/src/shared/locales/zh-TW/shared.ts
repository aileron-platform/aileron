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
      remoteSettings: {
        label: '遠端設定',
      },
    },
    branchDialog: {
      title: '建立分支',
      description: '從目前儲存庫狀態或指定起點建立分支。',
      nameLabel: '分支名稱',
      namePlaceholder: '分支名稱',
      startPointLabel: '起點',
      startPointPlaceholder: '起點',
      stashChanges: '切換前暫存本機變更',
      cancel: '取消',
      create: '建立分支',
      creating: '建立中...',
    },
    remoteDialog: {
      title: '遠端設定',
      description: '設定此儲存庫的遠端與初始化流程。',
      initialized: {
        title: 'Git 儲存庫已初始化',
        branch: '分支：{{branch}}',
        noBranch: '無分支',
      },
      setup: {
        localContentWarning: '本機已有內容。只有在可安全完成時才能 clone。',
        actions: {
          init: '初始化儲存庫',
          initializing: '初始化中...',
        },
      },
      remote: {
        missingOrigin: '尚未設定 origin 遠端。儲存遠端 URL 前無法使用遠端同步操作。',
        urlLabel: '遠端 URL',
        urlPlaceholder: 'git@example.com:team/repo.git',
        helper: '此 URL 會儲存為 origin 遠端，供 fetch、pull、push 使用。',
        actions: {
          save: '儲存遠端',
          saving: '儲存中...',
        },
      },
      clone: {
        urlLabel: '儲存庫 URL',
        branchLabel: '分支',
        branchPlaceholder: 'main',
        branchHelper: '留空會使用遠端預設分支。',
        helper: '將遠端儲存庫 clone 到此儲存位置。',
        disabledHelper: '此位置已有內容，因此無法 clone。',
        actions: {
          clone: 'Clone 儲存庫',
          cloning: 'Clone 中...',
        },
        progressTitle: 'Clone 進度',
      },
    },
    main: {
      selectFile: '選擇檔案以檢視變更',
      selectCommitFile: '選擇檔案以檢視變更',
    },
    mode: {
      fileChanges: '檔案變更',
      commitHistory: '變更記錄',
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
      empty: '沒有變更記錄',
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
