const common = {
  welcome: '歡迎，{{name}}',
  loading: '載入中...',
  entry: {
    title: '正在開啟工作區',
    descriptions: {
      identity: '正在確認您的身份。',
      identityFailed: '身份確認未完成，請重新登入。',
      workspace: '正在確認工作區與您的存取權限。',
      workspaceFailed: '目前無法確認工作區，請檢查存取權限或返回。',
      execution: '正在準備工作區執行環境。',
      executionFailed: '執行環境需要處理，請使用可用動作或返回。',
      executionPlaneDrift: '工作區執行環境與平台狀態不同步，請刪除工作區以安全地清除。',
    },
    stages: {
      label: '工作區進入階段',
      identity: '確認身份',
      workspace: '確認工作區',
      execution: '準備執行環境',
    },
    status: {
      pending: '尚未開始',
      active: '進行中',
      complete: '已完成',
      action_required: '需要處理',
      uncertain: '等待確認',
      failed: '未完成',
    },
    reasonCode: '原因代碼',
    copyReasonCode: '複製原因代碼',
    reasonCodeCopied: '已複製原因代碼',
    confirmRebuild: '確定要重建此工作區的執行環境嗎？',
    executionPlaneDrift: {
      contactOwner: '請聯絡工作區擁有者或管理員刪除此工作區。',
    },
    actions: {
      login: '重新登入',
      create: '建立工作區',
      refresh: '重新確認',
      start: '啟動工作區',
      retry: '重試恢復',
      rebuild: '重建執行環境',
      return: '返回工作區列表',
    },
  },
  notFound: '頁面不存在',
  authorization: {
    accessDeniedTitle: '沒有存取權限',
    accessDeniedDescription: '你沒有存取此功能的權限。',
    readOnlyDescription: '你可以查看此內容，但沒有變更權限。',
  },
  errors: {
    generic: '發生錯誤，請再試一次。',
  },
  save: '儲存',
  cancel: '取消',
  confirm: '確認',
  delete: '刪除',
  edit: '編輯',
  add: '新增',
  search: '搜尋',
  filter: '篩選',
  refresh: '重新整理',
  close: '關閉',
  back: '返回',
  next: '下一步',
  previous: '上一步',
  submit: '提交',
  reset: '重置',
  retry: '重試',
  reconnect: '重新連接',
  reconnecting: '重新連接中...',
  // Error page related
  error: {
    workspaceRuntime: {
      title: '工作區連接失敗',
      connectionFailed: '工作區尚未啟動或無法連接',
      noWorkspace: '尚未建立工作區',
      noWorkspaceErrorMessage: '尚未建立任何工作區',
      invalidWorkspaceErrorMessage: '找不到有效的工作區',
      noWorkspaceHint: '請先建立一個工作區來開始使用',
      createWorkspace: '建立新工作區',
      troubleshoot: '如果問題持續發生，請檢查工作區服務狀態',
    }
  },

  // File tree component
  fileTree: {
    toolbar: {
      title: '檔案',
      moreActions: '更多操作',
    },
    sidebar: {
      expand: '展開側欄',
      collapse: '收折側欄',
    },
    search: {
      placeholder: '搜尋檔案或資料夾',
      button: '搜尋',
    },
    context: {
      viewImage: '查看圖片',
    },
    contextMenu: {
      view: '查看',
      upload: '上傳檔案',
      createFolder: '新增資料夾',
      createFile: '新增檔案',
      open: '開啟',
      download: '下載',
      downloadAsZip: '下載為 ZIP',
      downloadSelected: '下載選取的 {{count}} 個項目',
      viewImage: '查看圖片',
      extractArchive: '解壓縮',
      copy: '複製',
      copyPath: '複製路徑',
      paste: '貼上',
      rename: '重新命名',
      delete: '刪除',
      deleteSelected: '刪除 {{count}} 個項目',
      refresh: '重新整理',
    },
    operations: {
      createFile: {
        success: '建立成功',
        successDesc: '檔案「{{name}}」已成功建立。',
        error: '建立失敗',
      },
      createFolder: {
        success: '建立成功',
        successDesc: '資料夾「{{name}}」已成功建立。',
        error: '建立失敗',
      },
      rename: {
        success: '重新命名成功',
        successDesc: '已重新命名為「{{name}}」。',
        error: '重新命名失敗',
      },
      delete: {
        success: '刪除成功',
        successDesc: '已刪除「{{name}}」。',
        error: '刪除失敗',
      },
      batchDelete: {
        success: '批次刪除成功',
        successDesc: '已刪除 {{count}} 個項目。',
        error: '批次刪除失敗',
      },
    },
    multiSelect: {
      selectAll: '全選',
      unselectAll: '取消全選',
      selectedCount: '已選擇 {{count}} 個項目',
      clearSelection: '清除選擇',
    },
    empty: {
      title: '沒有檔案',
      description: '點擊上方按鈕新增檔案或資料夾',
    },
    searchEmpty: {
      title: '沒有找到符合的檔案',
      description: '請嘗試使用不同的搜尋關鍵字',
    },
    error: {
      title: '載入失敗',
      description: '無法載入檔案樹，請稍後再試',
    },
  },
  fileEditor: {
    save: {
      success: '儲存成功',
      successDesc: '已儲存「{{name}}」',
      error: '儲存失敗',
    },
    copy: {
      success: '已複製',
      successDesc: '內容已複製到剪貼簿',
      error: '複製失敗',
    },
    download: {
      success: '下載成功',
      successDesc: '已下載「{{name}}」',
    },
    actions: {
      save: '儲存',
      cancel: '取消',
      edit: '編輯',
      copy: '複製',
      download: '下載',
    },
    markdown: {
      placeholder: '輸入 Markdown 內容...',
    },
    emptyFile: '這個檔案尚未填入內容。',
    unknownError: '未知錯誤',
  },
  markdownFileViewer: {
    units: {
      chars: '{{count}} 字元',
      bytes: '{{count}} 位元組',
    },
  },

  hookEvents: {
    PreToolUse: { label: 'PreToolUse', description: 'Tool call 前執行。' },
    PostToolUse: { label: 'PostToolUse', description: 'Tool call 後執行。' },
    PermissionRequest: { label: 'PermissionRequest', description: 'Codex 要求 permission 時執行。' },
    UserPromptSubmit: { label: 'UserPromptSubmit', description: '使用者送出 prompt 時執行。' },
    Notification: { label: 'Notification', description: '發出 notification 時執行。' },
    Stop: { label: 'Stop', description: '主 agent 停止時執行。' },
    SubagentStop: { label: 'SubagentStop', description: 'Subagent 停止時執行。' },
    PreCompact: { label: 'PreCompact', description: 'Context compaction 前執行。' },
    SessionStart: { label: 'SessionStart', description: 'Session 開始時執行。' },
    SessionEnd: { label: 'SessionEnd', description: 'Session 結束時執行。' },
    Setup: { label: 'Setup', description: 'Claude Code setup 時執行。' },
    UserPromptExpansion: { label: 'UserPromptExpansion', description: 'Claude 展開 user prompt 時執行。' },
    PostToolUseFailure: { label: 'PostToolUseFailure', description: 'Tool call 失敗後執行。' },
    PostToolBatch: { label: 'PostToolBatch', description: 'Tool batch 完成後執行。' },
    PermissionDenied: { label: 'PermissionDenied', description: 'Permission 被拒絕時執行。' },
    StopFailure: { label: 'StopFailure', description: 'Stop handling 失敗時執行。' },
    SubagentStart: { label: 'SubagentStart', description: 'Subagent 開始時執行。' },
    TeammateIdle: { label: 'TeammateIdle', description: 'Teammate idle 時執行。' },
    TaskCreated: { label: 'TaskCreated', description: 'Task 建立時執行。' },
    TaskCompleted: { label: 'TaskCompleted', description: 'Task 完成時執行。' },
    ConfigChange: { label: 'ConfigChange', description: '設定變更時執行。' },
    CwdChanged: { label: 'CwdChanged', description: '工作目錄變更時執行。' },
    FileChanged: { label: 'FileChanged', description: '監看檔案變更時執行。' },
    InstructionsLoaded: { label: 'InstructionsLoaded', description: 'Instructions 載入時執行。' },
    PostCompact: { label: 'PostCompact', description: 'Context compaction 後執行。' },
    WorktreeCreate: { label: 'WorktreeCreate', description: 'Worktree 建立時執行。' },
    WorktreeRemove: { label: 'WorktreeRemove', description: 'Worktree 移除時執行。' },
    Elicitation: { label: 'Elicitation', description: 'MCP elicitation 期間執行。' },
    ElicitationResult: { label: 'ElicitationResult', description: 'MCP elicitation 完成後執行。' },
    MessageDisplay: { label: 'MessageDisplay', description: 'Claude Code 顯示訊息時執行。' },
    DirectoryAdded: { label: 'DirectoryAdded', description: 'Session 新增目錄時執行。' },
  },

  // File operation dialogs
  fileOperations: {
    // Create files and folders
    create: {
      file: {
        title: '新增檔案',
        description: '請輸入檔案名稱',
        placeholder: '例如: index.ts',
      },
      folder: {
        title: '新增資料夾',
        description: '請輸入資料夾名稱',
        placeholder: '例如: components',
      },
      nameLabel: '名稱',
    },
    // Rename
    rename: {
      title: '重新命名',
      description: '請輸入新名稱',
      nameLabel: '新名稱',
    },
    // Delete
    delete: {
      title: '確認刪除',
      description: '此操作無法復原',
      file: '確定要刪除檔案 {{name}} 嗎？',
      folder: '確定要刪除資料夾 {{name}} 嗎？',
      folderWarning: '資料夾內的所有檔案也會被刪除',
      unsavedTabs: '將影響 {{count}} 個尚未儲存的已開啟分頁。',
    },
    // Batch delete
    batchDelete: {
      title: '確認批次刪除',
      description: '此操作無法復原',
      summary: '即將刪除 {{count}} 個項目：',
      fileCount: '{{count}} 個檔案',
      folderCount: '{{count}} 個資料夾',
      folderWarning: '資料夾內的所有檔案也會被刪除',
      deleteAll: '刪除全部',
    },
    // Buttons
    buttons: {
      cancel: '取消',
      confirm: '確定',
      delete: '刪除',
    },
    // Validation errors
    validation: {
      nameRequired: '名稱不能為空',
      nameWithPath: '名稱不能包含路徑分隔符號 (/ 或 \\)',
      nameWithInvalidChars: '名稱包含非法字元',
      nameReserved: '此名稱為系統保留名稱',
      nameSame: '新名稱與原名稱相同',
      nameExists: '{{name}} 已存在，請使用其他名稱。',
    },
    // Success messages
    success: {
      fileCreated: '檔案建立成功',
      folderCreated: '資料夾建立成功',
      fileRenamed: '檔案重新命名成功',
      fileDeleted: '檔案刪除成功',
      fileMoved: '檔案移動成功',
      fileSaved: '檔案儲存成功',
      fileCopied: '檔案複製成功',
      fileUploaded: '檔案上傳成功',
      noItemsToDelete: '沒有可刪除的項目',
    },
    // Error messages
    error: {
      fileCreateFailed: '檔案建立失敗',
      folderCreateFailed: '資料夾建立失敗',
      fileRenameFailed: '檔案重新命名失敗',
      fileDeleteFailed: '檔案刪除失敗',
      batchDeleteFailed: '批次刪除失敗',
      fileCopyFailed: '檔案複製失敗',
      fileMoveFailed: '檔案移動失敗',
      fileUploadFailed: '檔案上傳失敗',
      fileOperationFailed: '檔案操作失敗',
      fileSaveFailed: '檔案儲存失敗',
      packageTaskFailed: '打包任務失敗',
      loadTreeFailed: '載入檔案樹失敗',
    },
  },

  // Prompt Invocation picker
  promptInvocation: {
    picker: {
      title: '選擇 Prompt Invocation',
      description: '選擇指令或 Skill，並插入 Prompt。',
      searchPlaceholder: '輸入名稱、描述或標籤搜尋…',
      loading: '正在載入 Prompt Invocation…',
      error: '無法載入 Prompt Invocation，請稍後再試。',
      degraded: '部分來源暫時無法使用，仍可選取目前載入的項目。',
      degradedEmpty: '目前可用來源未能載入任何 Prompt Invocation。',
      empty: '沒有符合條件的 Prompt Invocation',
      scope: {
        all: '全部',
        project: '專案',
        user: '個人',
        plugin: '外掛',
      },
      kind: {
        'slash-command': '指令',
        skill: '技能',
      },
    },
  },

  // Markdown editor
  markdownEditor: {
    placeholder: '請輸入內容...\n支援 Markdown 語法',
    actions: {
      preview: '預覽',
      backToEdit: '返回編輯',
    },
    toolbar: {
      bold: '粗體',
      italic: '斜體',
      link: '連結',
      code: '程式碼',
      image: '圖片',
      unorderedList: '項目列表',
      orderedList: '編號列表',
      quote: '引用',
      undo: '復原',
      redo: '重做',
    },
    charCount: '字元數：{{count}}',
    placeholders: {
      quote: '引用內容',
      bold: '粗體文字',
      italic: '斜體文字',
      link: '連結文字',
      code: '程式碼',
      description: '描述',
      listItem: '項目',
    },
  },

  // Other messages
  messages: {
    unauthorized: '請先登入',
    unknownError: '未知錯誤',
    cannotConnect: '無法連接到預覽服務',
    userRejected: '用戶拒絕執行',
    noWorkspaceFound: '找不到有效的工作區',
    noWorkspaceCreated: '尚未建立任何工作區',
    workspaceRuntimeNotStarted: 'Workspace Runtime 尚未啟動或尚未提供 URL',
    executionNoWorkspace: '無法查看對話：執行記錄沒有關聯的工作區',
    cannotViewSession: '無法查看對話：{{error}}',
    terminalConnectionFailed: '終端連線網址建立失敗',
    terminalError: '終端連線發生錯誤',
    cannotGetUserInfo: '無法取得使用者資訊',
    loginFailed: '登入失敗',
    registerFailed: '註冊失敗',
    fallbackOwnerName: '排程任務',
    waitingComplete: '等待完成...',
    cannotGetSyncStatus: '無法取得同步狀態',
    syncError: '同步過程中發生錯誤',
    syncFailed: '同步失敗',
  },

  // Template management error messages
  template: {
    errors: {
      loadFailed: '載入失敗',
      createFailed: '建立失敗',
      updateFailed: '更新失敗',
      deleteFailed: '刪除失敗',
      saveFailed: '儲存失敗',
      uploadFailed: '上傳失敗',
      renameFailed: '重命名失敗',
      moveFailed: '移動失敗',
      copyFailed: '複製失敗',
      searchFailed: '搜尋失敗',
      batchDeleteFailed: '批次刪除失敗',
      loadContentFailed: '載入檔案內容失敗',
    },
  },
};

export default common;
