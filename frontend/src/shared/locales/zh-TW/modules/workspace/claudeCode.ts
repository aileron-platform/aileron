const claudeCode = {
  documents: {
    meta: {
      'slash-commands': { title: 'Slash Command 設定' },
      'output-styles': { title: 'Output Style 設定' },
      subagents: { title: 'Subagent 設定' },
      memory: { title: 'Memory 設定' },
    },
    actions: {
      refresh: '重整',
      edit: '編輯',
      copyContent: '複製內容',
      download: '下載',
      delete: '刪除',
    },
    loading: '載入資料中…',
    stats: {
      total: '共 {{count}} 項',
    },
    scope: {
      badge: '範圍：{{scope}}',
      values: {
        project: '專案',
        user: '個人',
        local: '本地',
        plugin: '外掛',
      },
    },
    size: {
      badge: '大小：{{size}}',
    },
    confirmDelete: '確定要刪除「{{title}}」嗎？',
    sidebar: {
      defaultTitle: '設定列表',
      toggle: {
        expand: '展開側欄',
        collapse: '收合側欄',
      },
      searchPlaceholder: '搜尋...',
      scope: {
        all: '所有範圍',
      },
      loading: '載入資料中…',
      empty: '尚未找到符合條件的項目',
    },
  },
  slashCommands: {
    pageTitle: 'Slash Command 設定',
    actions: {
      create: '新增 Slash Command',
    },
    empty: {
      title: '尚未建立任何 Slash Command',
      description: '請從左側選擇或建立新的指令來管理 Claude 的行為。',
    },
    dialog: {
      title: {
        create: '新增 Slash Command',
        edit: '編輯 Slash Command',
      },
      description: {
        create: '建立新的 Slash Command，讓 Claude 擁有自訂指令。',
        edit: '更新既有指令的詳細設定與內容。',
      },
      tabs: {
        basic: '基本設定',
        editor: '內容編輯',
      },
      fields: {
        scope: {
          label: '範圍',
        },
        identifier: {
          label: '命令名稱',
          placeholder: '輸入命令名稱',
          helper: '命令名稱需唯一，建議使用英文與連字號。',
        },
        title: {
          label: '顯示標題',
          placeholder: '輸入標題',
        },
        fileName: {
          label: '檔案名稱',
          placeholder: '輸入檔案名稱',
        },
        namespace: {
          label: '命名空間',
          placeholder: '輸入命名空間（可選）',
          helper: '用於組織相關命令',
        },
        description: {
          label: '指令描述',
          placeholder: '輸入描述（可選）',
          helper: '簡要說明此指令的用途與情境。',
        },
        content: {
          label: '指令內容',
          estimatedSize: '預估大小：{{size}}',
        },
      },
      validation: {
        identifier: '請輸入命令名稱。',
        title: '請輸入標題。',
        fileName: '請輸入檔案名稱。',
        content: '內容不可為空。',
      },
      actions: {
        cancel: '取消',
        save: '儲存變更',
        create: '建立項目',
      },
    },
  },
  outputStyles: {
    pageTitle: 'Output Style 設定',
    actions: {
      create: '新增 Output Style',
    },
    empty: {
      title: '尚未建立任何 Output Style',
      description: '建立輸出樣式，以套用一致的結果呈現格式。',
    },
    dialog: {
      title: {
        create: '新增 Output Style',
        edit: '編輯 Output Style',
      },
      description: {
        create: '定義新的輸出樣式配置，讓結果呈現符合需求。',
        edit: '調整既有輸出樣式的細節設定。',
      },
      fields: {
        scope: {
          label: '範圍',
        },
        title: {
          label: '樣式名稱',
          placeholder: '輸入樣式名稱',
          helper: '樣式名稱需唯一，建議使用英文與連字號。',
        },
        fileName: {
          label: '檔案名稱',
          placeholder: '輸入檔案名稱',
          helper: '檔案名稱需唯一，建議使用英文與連字號。',
        },
        description: {
          label: '樣式描述',
          placeholder: '輸入描述（可選）',
        },
        content: {
          label: '樣式內容',
          estimatedSize: '預估大小：{{size}}',
        },
      },
      validation: {
        identifier: '請輸入樣式代號。',
        title: '請輸入樣式名稱。',
        fileName: '請輸入檔案名稱。',
        content: '內容不可為空。',
      },
      actions: {
        cancel: '取消',
        save: '儲存變更',
        create: '建立項目',
      },
    },
  },
  subagents: {
    pageTitle: 'Subagent 設定',
    actions: {
      create: '新增 Subagent',
    },
    empty: {
      title: '尚未建立任何 Subagent',
      description: '建立專用的 Subagent 以協助協同開發與任務分工。',
    },
    dialog: {
      title: {
        create: '新增 Subagent',
        edit: '編輯 Subagent',
      },
      description: {
        create: '設定新的 Subagent 來協助協同工作。',
        edit: '調整現有 Subagent 的能力描述。',
      },
      fields: {
        scope: {
          label: '範圍',
        },
        identifier: {
          label: '代理代號',
          placeholder: '輸入代理代號',
          helper: '代號需唯一，可使用字母、數字與分隔符號。',
        },
        title: {
          label: '代理名稱',
          placeholder: '輸入代理名稱',
        },
        fileName: {
          label: '檔案名稱',
          placeholder: '輸入檔案名稱',
        },
        description: {
          label: '代理描述',
          placeholder: '輸入描述（可選）',
        },
        content: {
          label: '代理說明內容',
          estimatedSize: '預估大小：{{size}}',
          helper: '定義 Subagent 的行為、工具與專業領域。',
        },
      },
      validation: {
        identifier: '請輸入代理代號。',
        title: '請輸入代理名稱。',
        fileName: '請輸入檔案名稱。',
        content: '內容不可為空。',
      },
      actions: {
        cancel: '取消',
        save: '儲存變更',
        create: '建立項目',
      },
    },
  },
  skills: {
    header: {
      title: '編輯器',
      description: '瀏覽檔案。',
      count: '共 {{count}} 個檔案',
    },
    searchPlaceholder: '搜尋技能或檔案名稱',
    emptySearch: '目前沒有符合條件的技能檔案。',
    empty: '尚未建立任何技能檔案。',
    noSelection: '請從左側選擇技能檔案以檢視內容。',
    emptyFile: '這個技能檔案目前沒有內容。',
    sidebar: {
      placeholder: '技能檔案樹已整合到主內容區中。',
    },
    scope: {
      label: '範圍：',
      project: '專案',
      user: '個人',
      plugin: '外掛',
    },
    plugin: {
      label: '外掛：',
      all: '所有外掛',
    },
    tree: {
      header: {
        title: 'Skills',
      },
      actions: {
        multiSelect: {
          enable: '多選',
          disable: '取消多選',
        },
        refresh: '重新整理',
      },
      multiSelect: {
        summary: '已選 {{count}} 項技能檔案',
        selectAll: '全選',
        unselectAll: '取消全選',
        download: '下載（{{count}}）',
      },
      status: {
        selected: '已選取 {{count}} 個項目',
        clearSelection: '清除選擇',
      },
    },
    actions: {
      edit: '編輯',
      save: '儲存',
      cancel: '取消',
      copy: {
        success: '已複製',
        description: '檔案內容已複製到剪貼簿',
        error: '複製失敗',
        errorDescription: '無法複製檔案內容',
      },
      download: {
        success: '下載成功',
        description: '檔案已下載',
      },
      saveInfo: {
        info: '儲存功能',
        description: '此為範例資料，暫不支援儲存',
      },
    },
    editor: {
      markdownPlaceholder: '輸入 Markdown 內容...',
    },
    fileOperations: {
      uploadFailed: '上傳檔案失敗',
      pasteFileFailed: '貼上檔案失敗',
      renamePrompt: '重新命名 {{name}}:',
      renameFailed: '重新命名失敗',
      renameFailedAlert: '重新命名失敗，請稍後再試',
      refreshFailed: '重新整理失敗',
      createFileFailed: '新增檔案失敗',
      createFolderFailed: '新增資料夾失敗',
      deleteFailed: '刪除失敗',
      batchDeleteFailed: '批次刪除失敗',
      moveFolderToSubfolderAlert: '無法將資料夾移動到自己或自己的子目錄中',
      moveFailed: '移動檔案失敗',
      moveFailedAlert: '移動檔案失敗，請稍後再試',
      pasteStarted: '開始貼上操作',
      pasteTargetPath: '目標路徑',
      pasteCallApi: '調用複製 API',
      pasteSuccess: '複製成功，重新載入檔案樹',
      pasteTreeReloaded: '檔案樹重新載入完成',
      pasteFailed: '貼上失敗',
      pasteFailedAlert: '貼上失敗，請稍後再試',
      pathCopied: '路徑已複製',
      copyPathFailed: '複製路徑失敗',
    },
  },

  scripts: {
    header: {
      title: '腳本檔案預覽',
      description: '瀏覽範例腳本與整合工具的目錄結構。',
      count: '共 {{count}} 個檔案',
      refresh: '重整',
      refreshing: '載入中...',
    },
    searchPlaceholder: '搜尋腳本或檔案名稱',
    emptySearch: '目前沒有符合條件的腳本檔案。',
    empty: '尚未建立任何腳本檔案。',
    noSelection: '請從左側選擇腳本檔案以檢視內容。',
    emptyFile: '這個腳本檔案目前沒有內容。',
    sidebar: {
      placeholder: '腳本檔案樹已整合到主內容區中。',
    },
    scope: {
      label: '範圍：',
      project: '專案',
      user: '個人',
    },
    tree: {
      header: {
        title: 'Scripts',
      },
      actions: {
        multiSelect: {
          enable: '多選',
          disable: '取消多選',
        },
        refresh: '重新整理',
      },
      multiSelect: {
        summary: '已選 {{count}} 項腳本檔案',
        selectAll: '全選',
        unselectAll: '取消全選',
        download: '下載（{{count}}）',
      },
      status: {
        selected: '已選取 {{count}} 個項目',
        clearSelection: '清除選擇',
      },
    },
    actions: {
      edit: '編輯',
      save: '儲存',
      cancel: '取消',
      copy: {
        success: '已複製',
        description: '檔案內容已複製到剪貼簿',
        error: '複製失敗',
        errorDescription: '無法複製檔案內容',
      },
      download: {
        success: '下載成功',
        description: '檔案已下載',
      },
      saveInfo: {
        info: '儲存功能',
        description: '此為範例資料，暫不支援儲存',
      },
    },
    notifications: {
      loadFailed: '載入檔案失敗',
      saveSuccess: '儲存成功',
      saveSuccessDescription: '檔案已成功儲存',
      saveFailed: '儲存失敗',
      copied: '已複製',
      copiedDescription: '內容已複製到剪貼簿',
      copyFailed: '複製失敗',
      downloaded: '已下載',
      downloadedDescription: '檔案已下載',
    },
    editor: {
      markdownPlaceholder: '輸入 Markdown 內容...',
    },
    fileOperations: {
      uploadFailed: '上傳檔案失敗',
      pasteFileFailed: '貼上檔案失敗',
      renamePrompt: '重新命名 {{name}}:',
      renameFailed: '重新命名失敗',
      renameFailedAlert: '重新命名失敗，請稍後再試',
      refreshFailed: '重新整理失敗',
      createFileFailed: '新增檔案失敗',
      createFolderFailed: '新增資料夾失敗',
      deleteFailed: '刪除失敗',
      batchDeleteFailed: '批次刪除失敗',
      moveFolderToSubfolderAlert: '無法將資料夾移動到自己或自己的子目錄中',
      moveFailed: '移動檔案失敗',
      moveFailedAlert: '移動檔案失敗，請稍後再試',
      pasteStarted: '開始貼上操作',
      pasteTargetPath: '目標路徑',
      pasteCallApi: '調用複製 API',
      pasteSuccess: '複製成功，重新載入檔案樹',
      pasteTreeReloaded: '檔案樹重新載入完成',
      pasteFailed: '貼上失敗',
      pasteFailedAlert: '貼上失敗，請稍後再試',
      pathCopied: '路徑已複製',
      copyPathFailed: '複製路徑失敗',
    },
  },
  permissions: {
    header: {
      title: '基本設定',
    },
    tabs: {
      basic: '基本設定',
      plugins: 'Plugins 管理',
      rules: '權限規則',
      mcp: 'MCP 設定',
    },
    stats: {
      label: '規則統計',
      total: '共 {{count}} 個規則',
      allow: '允許 {{count}} 筆',
      deny: '拒絕 {{count}} 筆',
    },
    actions: {
      refresh: '重整',
      save: '儲存設定',
      saving: '儲存中...',
    },
    plugins: {
      title: 'Plugins 設定',
      emptyTitle: '尚未安裝任何 Marketplace',
      emptyDescription: '請先安裝 Marketplace 以使用 Plugins',
      helper: '從 Marketplace 中選擇並啟用 Plugins。展開 Marketplace 查看可用的 Plugins。',
      count: '{{count}} 個插件',
    },
    rules: {
      title: '權限管理',
    },
    scope: {
      label: '設定範圍',
      options: {
        project: '專案',
        user: '個人',
        local: '本地',
      },
    },
    search: {
      placeholder: '搜尋規則...',
    },
    modes: {
      title: '權限模式',
      fieldLabel: '選擇權限模式',
      default: {
        label: '預設模式',
        description: '標準行為 - 在首次使用每個工具時提示權限',
      },
      acceptEdits: {
        label: '自動接受編輯',
        description: '自動接受會話的檔案編輯權限',
      },
      plan: {
        label: '計劃模式',
        description: '計劃模式 - Claude 可以分析但不能修改檔案或執行指令',
      },
      bypassPermissions: {
        label: '跳過權限',
        description: '跳過所有權限提示（需要安全環境）',
      },
    },
    model: {
      title: '模型設定',
      label: '模型覆寫（可選）',
      placeholder: '例如：claude-3-sonnet-20240229',
      helper: '留空則使用 Claude SDK 的預設模型。',
    },
    outputStyle: {
      title: '輸出樣式',
      label: '選擇輸出樣式',
      placeholder: '無',
      none: '無',
      helper: '選擇 Claude Code 的預設輸出樣式，留空則不使用特定樣式',
    },
    basic: {
      apiKeyHelper: {
        title: '認證腳本',
        description: '設定一段 shell 腳本，在每次開啟會話前執行並回傳臨時的 API Key。',
        label: 'API Key 產生腳本',
        placeholder: '/bin/generate_temp_api_key.sh',
        helper: '腳本會由 /bin/sh 執行，stdout 的內容將作為認證值。',
      },
      cleanup: {
        label: '聊天紀錄保留天數',
        placeholder: '30',
        helper: '依照最後活動時間定期清除舊的聊天紀錄，留空則沿用系統預設值。',
      },
      modelDescription: '指定 Claude Code 預設使用的模型與輸出樣式。',
      collaboration: {
        title: '協作行為預設',
      },
      includeCoAuthoredBy: {
        label: '在提交中加入「co-authored-by Claude」',
        description: '當 Claude 產生 Git Commit 或 Pull Request 時，自動附上 co-authored-by Claude 署名。',
      },
      disableAllHooks: {
        label: '停用所有 Claude Code Hooks',
        description: '暫時停用此範圍內的全部 hooks，原本的設定值將被保留但不會執行。',
      },
      env: {
        title: '會話環境變數',
        description: '這些變數會在每次 Claude Code 執行時注入，適用於 CLI 或腳本執行環境。',
        add: '新增環境變數',
        empty: '尚未設定任何環境變數。',
        keyLabel: '變數名稱',
        valueLabel: '變數值',
        keyPlaceholder: '例如：NODE_ENV',
        valuePlaceholder: '例如：development',
      },
    },
    allowRules: {
      title: '允許規則',
      count: '{{count}} 個',
      placeholder: '輸入允許規則...',
      empty: '尚未設定允許規則',
      emptyFiltered: '沒有符合搜尋條件的允許規則',
    },
    denyRules: {
      title: '拒絕規則',
      count: '{{count}} 個',
      placeholder: '輸入拒絕規則...',
      empty: '尚未設定拒絕規則',
      emptyFiltered: '沒有符合搜尋條件的拒絕規則',
    },
    askRules: {
      title: '需確認的規則',
      placeholder: '輸入需要額外確認的規則...',
      empty: '尚未設定需確認的規則',
    },
    directoryRules: {
      title: '額外授權目錄',
      placeholder: '輸入可存取的額外目錄路徑...',
      empty: '尚未設定額外授權的目錄',
    },
    mcp: {
      autoApprove: {
        title: '自動核准專案 MCP 伺服器',
        description: '自動允許專案 .mcp.json 中定義的所有伺服器，避免每次開啟工作區都需要逐一核准。',
        helper: '僅適用於受信任的專案來源，建議與 Git 版本控制搭配使用。',
      },
      mcpjson: {
        title: '.mcp.json 審核設定',
        enabled: {
          label: '自動允許的伺服器 ID',
          helper: '輸入 .mcp.json 中允許自動啟用的伺服器名稱，支援萬用字元 (例如：git-* )。',
          placeholder: '例如：github、git-*',
          empty: '尚未設定自動允許的伺服器。',
        },
        disabled: {
          label: '自動拒絕的伺服器 ID',
          helper: '列出一律拒絕的伺服器名稱，Claude 將在載入時忽略它們。',
          placeholder: '例如：filesystem',
          empty: '尚未設定自動拒絕的伺服器。',
        },
      },
      policies: {
        title: '使用者可管理的 MCP 伺服器',
        helper: '設定 managed-settings.json 可以允許或禁止的 MCP 伺服器，適合大型團隊環境進行控管。',
        allowed: {
          title: '允許清單',
          placeholder: '輸入允許使用者設定的伺服器名稱...',
          empty: '尚未設定允許清單。',
        },
        denied: {
          title: '拒絕清單',
          placeholder: '輸入禁止使用者設定的伺服器名稱...',
          empty: '尚未設定拒絕清單。',
        },
      },
    },
    status: {
      runtimeLoading: 'Workspace Runtime 初始化中...',
      runtimeMissing: '尚未取得 Workspace Runtime 連線，請稍後再試。',
      runtimeUnavailable: 'Workspace Runtime 無法使用：{{message}}',
      loading: '載入基本設定中...',
      loadFailed: '無法載入基本設定，請稍後再試。',
    },
    messages: {
      allowExists: '此允許規則已存在',
      denyExists: '此拒絕規則已存在',
      askExists: '此確認規則已存在',
      directoryExists: '此目錄已在清單中',
      invalidCleanupPeriod: '請輸入大於或等於 0 的天數。',
      saveSuccess: '基本設定已成功儲存！',
      saveError: '儲存失敗，請稍後再試',
      mcpJsonServerExists: '此 MCP 伺服器 ID 已在清單中',
      mcpAllowedExists: '允許清單已包含該 MCP 伺服器',
      mcpDeniedExists: '拒絕清單已包含該 MCP 伺服器',
    },
  },
  agentsMd: {
    scope: { label: '範圍' },
    actions: { save: '儲存設定', refresh: '重新載入' },
    status: {
      runtimeLoading: 'Workspace Runtime 初始化中...',
      runtimeMissing: '尚未取得 Workspace Runtime 連線，請稍後重試。',
      runtimeUnavailable: 'Workspace Runtime 無法使用：{{message}}',
      loading: '載入 {{fileName}}...',
      fallbackNotice: '當前顯示預設模板內容，儲存後將建立新的 {{fileName}}。',
    },
    notifications: {
      saveSuccess: {
        title: '{{fileName}} 已儲存',
        description: '內容已成功同步至 Workspace Runtime。',
      },
      saveFailed: {
        title: '儲存 {{fileName}} 失敗',
        description: '請稍後再試或檢查 Workspace Runtime 狀態。',
      },
      loadFailed: {
        title: '載入 {{fileName}} 失敗',
        description: '無法載入設定檔，已使用預設模板。',
      },
      runtimeUnavailable: {
        title: 'Workspace Runtime 尚未就緒',
        description: '請確認執行環境狀態後再試一次。',
      },
    },
    confirmDiscard: '目前有尚未儲存的變更，確定要放棄嗎？',
    footer: { scope: '範圍：{{scope}}' },
  },
  mcp: {
    header: {
      title: 'Model Context Protocol 設定',
      actions: {
        import: '導入配置',
        create: '新增服務器',
      },
    },
    stats: {
      title: '統計',
      total: '{{count}} 個服務器',
      running: '{{count}} 運行中',
      stopped: '{{count}} 已停用',
    },
    search: {
      placeholder: '搜尋服務器...',
    },
    server: {
      status: {
        running: '運行中',
        stopped: '已停用',
        error: '錯誤',
      },
      scope: {
        label: '範圍',
        all: '全部',
        project: '專案',
        user: '個人',
        local: '本地',
        plugin: '外掛',
      },
    },
    serverDetails: {
      transportType: '傳輸類型',
      serverUrl: '服務器 URL',
      command: '執行命令',
      commandArgs: '命令參數',
      env: '環境變數',
      headers: 'HTTP 標頭',
    },
    list: {
      empty: '未找到符合條件的服務器',
    },
    import: {
      descriptionFromJson: '透過 JSON 導入的服務器',
    },
    dialogs: {
      server: {
        title: {
          create: '新增 MCP 服務器',
          edit: '編輯 MCP 服務器',
        },
        description: '配置 MCP 服務器連接設定。',
        fields: {
          name: {
            label: '服務器名稱 *',
            placeholder: '例如：filesystem',
            hint: '只能包含字母、數字、底線與連字號',
          },
          scope: {
            label: '配置範圍 *',
            options: {
              project: {
                title: '專案',
                description: '專案級別配置',
              },
              user: {
                title: '個人',
                description: '使用者級別配置',
              },
              local: {
                title: '本地',
                description: '本地級別配置',
              },
            },
          },
          transport: {
            label: '傳輸類型 *',
            options: {
              stdio: {
                title: 'Stdio（標準輸入/輸出）',
                description: '透過命令列執行',
              },
              sse: {
                title: 'SSE（伺服器傳送事件）',
                description: '透過伺服器傳送事件連線',
              },
              http: {
                title: 'Streamable HTTP（可串流 HTTP）',
                description: '透過 HTTP API 連線',
              },
            },
          },
          command: {
            label: '執行命令 *',
            placeholder: '例如：npx',
          },
          commandArgs: {
            label: '命令參數',
            add: '添加參數',
            placeholder: '參數 {{index}}',
            empty: '沒有命令參數',
          },
          url: {
            label: '服務器 URL *',
            placeholder: {
              sse: '例如：https://api.example.com/sse',
              http: '例如：https://api.example.com/mcp',
            },
            hint: {
              sse: '輸入完整的 SSE 端點 URL',
              http: '輸入完整的 HTTP/HTTPS URL',
            },
          },
          env: {
            label: '環境變數',
            add: '添加變數',
            keyPlaceholder: '變數名稱',
            valuePlaceholder: '變數值',
            empty: '沒有環境變數',
          },
          headers: {
            label: 'HTTP 標頭',
            add: '添加標頭',
            keyPlaceholder: '標頭名稱',
            valuePlaceholder: '標頭值',
            empty: '沒有 HTTP 標頭',
          },
        },
        actions: {
          create: '新增服務器',
          save: '儲存變更',
        },
      },
      import: {
        title: '上傳 Claude Desktop 配置檔案',
        description: '導入現有的 MCP 服務器配置到當前工作區',
        info: {
          upload: '請上傳 Claude Desktop 配置檔案',
          description: '來導入現有的 MCP 服務器配置。'
        },
        fields: {
          file: {
            label: '選擇配置檔案',
            dragText: '拖拽檔案到此處或點擊選擇',
            formatInfo: '支援 JSON 格式，最大 5MB'
          },
          scope: {
            label: '導入範圍',
            helper: '選擇導入的服務器配置將保存到哪個範圍'
          }
        },
        progress: {
          importing: '正在從 Claude Desktop 導入配置...'
        },
        result: {
          title: '導入結果',
          success: '成功導入',
          failed: '導入失敗',
          successRate: '成功率',
          details: '詳細結果',
          noServers: '未找到可導入的 MCP 服務器配置。請確認 Claude Desktop 配置文件存在且包含 MCP 服務器配置。'
        },
        warning: {
          title: '注意',
          message: '如果服務器名稱已存在，將跳過該服務器的導入。'
        },
        errors: {
          invalidFile: '請選擇 JSON 格式的配置檔案',
          fileTooLarge: '檔案大小不能超過 5MB',
          fileReadError: '檔案讀取失敗',
          noFile: '請先選擇配置檔案'
        },
        actions: {
          removeFile: '移除檔案',
          startImport: '開始導入',
          importing: '導入中...',
          confirm: '確認導入'
        },
        tabs: {
          form: '表單建立',
          json: 'JSON 配置',
        },
        form: {
          fields: {
            name: {
              label: '服務器名稱 *',
              placeholder: '例如：filesystem',
            },
            scope: {
              label: '範圍 *',
            },
            command: {
              label: '執行命令 *',
              placeholder: '例如：npx @modelcontextprotocol/server-filesystem',
            },
            args: {
              label: '命令參數',
              placeholder: '使用空白分隔多個參數',
            },
          },
        },
        json: {
          fields: {
            name: {
              label: '服務器名稱 *',
              placeholder: '例如：filesystem',
            },
            scope: {
              label: '範圍 *',
            },
            config: {
              label: 'JSON 配置 *',
            },
          },
          helper: '配置將會以 JSON 方式匯入，請確認欄位結構與 Model Context Protocol 服務器相容。',
        },
      },
    },
  },
  hooks: {
    header: {
      title: 'Hooks 設定',
    },
    filters: {
      scope: {
        label: '範圍',
        placeholder: '選擇範圍',
        options: {
          all: '全部範圍',
          project: '專案',
          user: '個人',
          local: '本地',
          plugin: '外掛',
        },
      },
    },
    actions: {
      refresh: '重整',
      create: '新增 Hook',
      edit: '編輯 Hook',
      delete: '刪除 Hook',
    },
    stats: {
      title: '統計',
      hooks: '{{count}} 個 Hook',
    },
    search: {
      placeholder: '搜尋 Hook...',
    },
    scope: {
      badge: {
        project: '專案',
        user: '個人',
        local: '本地',
        plugin: '外掛',
      },
    },
    events: {
      PreToolUse: {
        name: 'PreToolUse：在工具呼叫之前執行（可以阻止它們）',
        option: 'PreToolUse：在工具呼叫之前執行（可以阻止它們）',
      },
      PostToolUse: {
        name: 'PostToolUse：在工具呼叫完成後執行',
        option: 'PostToolUse：在工具呼叫完成後執行',
      },
      UserPromptSubmit: {
        name: 'UserPromptSubmit：當使用者提交提示時執行，在 Claude 處理之前',
        option: 'UserPromptSubmit：當使用者提交提示時執行，在 Claude 處理之前',
      },
      Notification: {
        name: 'Notification：當 Claude Code 發送通知時執行',
        option: 'Notification：當 Claude Code 發送通知時執行',
      },
      Stop: {
        name: 'Stop：當 Claude Code 完成回應時執行',
        option: 'Stop：當 Claude Code 完成回應時執行',
      },
      SubagentStop: {
        name: 'SubagentStop：當子代理任務完成時執行',
        option: 'SubagentStop：當子代理任務完成時執行',
      },
      PreCompact: {
        name: 'PreCompact：在 Claude Code 即將執行壓縮操作之前執行',
        option: 'PreCompact：在 Claude Code 即將執行壓縮操作之前執行',
      },
      SessionStart: {
        name: 'SessionStart：當 Claude Code 開始新會話或恢復現有會話時執行',
        option: 'SessionStart：當 Claude Code 開始新會話或恢復現有會話時執行',
      },
      SessionEnd: {
        name: 'SessionEnd：當 Claude Code 會話結束時執行',
        option: 'SessionEnd：當 Claude Code 會話結束時執行',
      },
    },
    matchers: {
      title: '匹配器配置',
      matcherLabel: '匹配規則',
      actionsCount: '{{count}} 個執行動作',
      commandLabel: '命令',
      timeoutValue: '{{value}} 秒',
      noCommand: '尚未設定命令',
      moreActions: '還有 {{count}} 個執行動作...',
      summary: {
        matchers: '{{count}} 個匹配器',
        commands: '{{count}} 個動作',
      },
    },
    list: {
      empty: '未找到符合條件的 Hook。',
    },
    dialog: {
      title: {
        edit: '編輯 Hook',
        create: '新增 Hook',
      },
      description: '設定 Hook 的範圍、觸發事件與執行命令。',
      scope: {
        label: '範圍',
        labelWithAsterisk: '範圍 *',
        placeholder: '請選擇範圍',
        options: {
          project: '專案',
          user: '個人',
          local: '本地',
        },
      },
      event: {
        label: '事件類型 *',
        placeholder: '請選擇事件',
      },
      matcher: {
        sectionTitle: '匹配器配置',
        add: '新增匹配器',
        patternLabel: '匹配模式',
        patternPlaceholder: '工具名稱模式（例如 Write|Edit 或 * 代表全部）',
        helper: {
          intro: '用於匹配工具名稱的模式（PostToolUse 會區分大小寫）',
          simple: '• 簡單字串：Write 僅匹配 Write 工具',
          regex: '• 正規表達式：Edit|Write 或 Notebook.*',
          wildcard: '• * 匹配所有工具，也可留空',
        },
        remove: '移除匹配器',
      },
      execution: {
        sectionTitle: 'Hook 執行配置',
        add: '新增執行動作',
        timeoutLabel: '超時時間（秒）',
        timeoutPlaceholder: '30',
        timeoutHelp: '命令的執行時間上限，超過即會被取消。',
        commandLabel: '命令 *',
        commandPlaceholder: '輸入要執行的命令',
        commandHelp: '可使用環境變數，例如 $CLAUDE_PROJECT_DIR。',
        remove: '移除執行動作',
      },
      actions: {
        cancel: '取消',
        save: '儲存變更',
        create: '新增 Hook',
      },
      validation: {
        invalidHook: '每個匹配器至少需要一個有效的 Hook 執行設定。',
        duplicateEvent: '此事件類型已經存在，請編輯現有的 Hook 或選擇其他事件類型。',
        duplicateEventWarning: '檢測到重複的事件類型',
        duplicateEventSuggestion: '建議編輯現有的 Hook 而不是建立重複的事件。',
      },
    },
  },
  memory: {
    pageTitle: 'Memory 設定',
    actions: {
      create: '新增 Memory 檔案',
    },
    empty: {
      title: '尚未建立任何 Memory 檔案',
      description: '建立或選擇左側 Memory 檔案，以瀏覽與編輯 Claude Memory 內容。',
    },
    dialog: {
      title: {
        create: '新增 Memory 檔案',
        edit: '編輯 Memory 檔案',
      },
      description: {
        create: '建立新的 Claude Memory Markdown 檔案。',
        edit: '更新既有 Claude Memory Markdown 檔案內容。',
      },
      fields: {
        fileName: {
          label: '檔案名稱',
          placeholder: '輸入檔案名稱',
          helper: '僅支援單層 Markdown 檔案，會自動補上 .md。',
        },
        content: {
          label: 'Memory 內容',
          estimatedSize: '預估大小：{{size}}',
        },
      },
      validation: {
        fileName: '請輸入檔案名稱。',
        content: '內容不可為空。',
      },
      actions: {
        cancel: '取消',
        save: '儲存變更',
        create: '建立檔案',
      },
    },
  },
};

export default claudeCode;
