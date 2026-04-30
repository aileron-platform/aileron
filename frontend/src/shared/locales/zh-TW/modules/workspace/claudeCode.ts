const claudeCode = {
  shellRequired: '請透過 WorkspaceShell 使用 Claude Code 功能。',
  unsupportedView: '未支援的視圖。',
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
