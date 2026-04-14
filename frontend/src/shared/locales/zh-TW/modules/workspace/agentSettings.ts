const agentSettings = {
  claude: {
    agentsMd: 'CLAUDE.md',
  },
  gemini: {
    instructionFile: 'GEMINI.md',
    hooks: {
      events: {
        BeforeTool: {
          name: 'BeforeTool：工具執行前觸發',
          option: 'BeforeTool：在工具執行前觸發',
        },
        AfterTool: {
          name: 'AfterTool：工具執行後觸發',
          option: 'AfterTool：在工具執行後觸發',
        },
        BeforeAgent: {
          name: 'BeforeAgent：Agent 處理前觸發',
          option: 'BeforeAgent：在 Agent 處理前觸發',
        },
        AfterAgent: {
          name: 'AfterAgent：Agent 處理後觸發',
          option: 'AfterAgent：在 Agent 處理後觸發',
        },
        BeforeModel: {
          name: 'BeforeModel：模型呼叫前觸發',
          option: 'BeforeModel：在模型呼叫前觸發',
        },
        AfterModel: {
          name: 'AfterModel：模型回應後觸發',
          option: 'AfterModel：在模型回應後觸發',
        },
        BeforeToolSelection: {
          name: 'BeforeToolSelection：工具選擇前觸發',
          option: 'BeforeToolSelection：在工具選擇前觸發',
        },
        SessionStart: {
          name: 'SessionStart：會話開始時觸發',
          option: 'SessionStart：在會話開始時觸發',
        },
        SessionEnd: {
          name: 'SessionEnd：會話結束時觸發',
          option: 'SessionEnd：在會話結束時觸發',
        },
        PreCompress: {
          name: 'PreCompress：歷史壓縮前觸發',
          option: 'PreCompress：在歷史壓縮前觸發',
        },
        Notification: {
          name: 'Notification：通知時觸發',
          option: 'Notification：在通知時觸發',
        },
      },
    },
  },
  opencode: {
    agentsMd: 'AGENTS.md',
  },
  codex: {
    agentsMd: 'AGENTS.md',
  },
  common: {
    subViews: {
      geminiMd: 'GEMINI.md',
      agentsMd: 'AGENTS.md',
      mcp: 'Model Context Protocol',
      hooks: 'Hooks',
      slashCommands: 'Slash Commands',
      skills: 'Skills',
    },
    scope: {
      project: '專案',
      user: '使用者',
      global: '全域',
    },
    comingSoon: {
      title: '即將推出',
      description: '{{feature}} 功能即將支援 {{toolName}}。',
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
    hooks: {
      header: { title: 'Hooks 設定' },
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
      stats: { title: '統計', hooks: '{{count}} 個 Hook' },
      search: { placeholder: '搜尋 Hook...' },
      scope: {
        badge: {
          project: '專案',
          user: '個人',
          local: '本地',
          plugin: '外掛',
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
        summary: { matchers: '{{count}} 個匹配器', commands: '{{count}} 個動作' },
      },
      list: { empty: '未找到符合條件的 Hook。' },
      dialog: {
        title: { edit: '編輯 Hook', create: '新增 Hook' },
        description: '設定 Hook 的範圍、觸發事件與執行命令。',
        scope: {
          label: '範圍',
          labelWithAsterisk: '範圍 *',
          placeholder: '請選擇範圍',
          options: { project: '專案', user: '個人', local: '本地' },
        },
        event: { label: '事件類型 *', placeholder: '請選擇事件' },
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
        actions: { cancel: '取消', save: '儲存變更', create: '新增 Hook' },
        validation: {
          invalidHook: '每個匹配器至少需要一個有效的 Hook 執行設定。',
          duplicateEvent: '此事件類型已經存在，請編輯現有的 Hook 或選擇其他事件類型。',
          duplicateEventWarning: '檢測到重複的事件類型',
          duplicateEventSuggestion: '建議編輯現有的 Hook 而不是建立重複的事件。',
        },
      },
    },
    mcp: {
      header: {
        title: 'Model Context Protocol 設定',
        actions: { import: '導入配置', create: '新增服務器' },
      },
      stats: {
        title: '統計',
        total: '{{count}} 個服務器',
        running: '{{count}} 運行中',
        stopped: '{{count}} 已停用',
      },
      search: { placeholder: '搜尋服務器...' },
      server: {
        status: { running: '運行中', stopped: '已停用', error: '錯誤' },
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
      list: { empty: '未找到符合條件的服務器' },
      import: { descriptionFromJson: '透過 JSON 導入的服務器' },
      dialogs: {
        server: {
          title: { create: '新增 MCP 服務器', edit: '編輯 MCP 服務器' },
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
                project: { title: '專案', description: '專案級別配置' },
                user: { title: '個人', description: '使用者級別配置' },
                local: { title: '本地', description: '本地級別配置' },
              },
            },
            transport: {
              label: '傳輸類型 *',
              options: {
                stdio: { title: 'Stdio（標準輸入/輸出）', description: '透過命令列執行' },
                sse: { title: 'SSE（伺服器傳送事件）', description: '透過伺服器傳送事件連線' },
                http: { title: 'Streamable HTTP（可串流 HTTP）', description: '透過 HTTP API 連線' },
              },
            },
            command: { label: '執行命令 *', placeholder: '例如：npx' },
            commandArgs: {
              label: '命令參數',
              add: '添加參數',
              placeholder: '參數 {{index}}',
              empty: '沒有命令參數',
            },
            url: {
              label: '服務器 URL *',
              placeholder: { sse: '例如：https://api.example.com/sse', http: '例如：https://api.example.com/mcp' },
              hint: { sse: '輸入完整的 SSE 端點 URL', http: '輸入完整的 HTTP/HTTPS URL' },
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
          actions: { create: '新增服務器', save: '儲存變更' },
        },
        import: {
          title: '上傳配置檔案',
          description: '導入現有的 MCP 服務器配置到當前工作區',
          info: { upload: '請上傳配置檔案', description: '來導入現有的 MCP 服務器配置。' },
          fields: {
            file: { label: '選擇配置檔案', dragText: '拖拽檔案到此處或點擊選擇', formatInfo: '支援 JSON 格式，最大 5MB' },
            scope: { label: '導入範圍', helper: '選擇導入的服務器配置將保存到哪個範圍' },
          },
          progress: { importing: '正在導入配置...' },
          result: {
            title: '導入結果',
            success: '成功導入',
            failed: '導入失敗',
            successRate: '成功率',
            details: '詳細結果',
            noServers: '未找到可導入的 MCP 服務器配置。請確認配置文件存在且包含 MCP 服務器配置。',
          },
          warning: { title: '注意', message: '如果服務器名稱已存在，將跳過該服務器的導入。' },
          errors: { invalidFile: '請選擇 JSON 格式的配置檔案', fileTooLarge: '檔案大小不能超過 5MB', fileReadError: '檔案讀取失敗', noFile: '請先選擇配置檔案' },
          actions: { removeFile: '移除檔案', startImport: '開始導入', importing: '導入中...', confirm: '確認導入' },
          tabs: { form: '表單建立', json: 'JSON 配置' },
          form: {
            fields: {
              name: { label: '服務器名稱 *', placeholder: '例如：filesystem' },
              scope: { label: '範圍 *' },
              command: { label: '執行命令 *', placeholder: '例如：npx @modelcontextprotocol/server-filesystem' },
              args: { label: '命令參數', placeholder: '使用空白分隔多個參數' },
            },
          },
          json: {
            fields: {
              name: { label: '服務器名稱 *', placeholder: '例如：filesystem' },
              scope: { label: '範圍 *' },
              config: { label: 'JSON 配置 *' },
            },
            helper: '配置將會以 JSON 方式匯入，請確認欄位結構與 Model Context Protocol 服務器相容。',
          },
        },
      },
    },
    slashCommands: {
      pageTitle: 'Slash Command 設定',
      actions: { create: '新增 Slash Command' },
      empty: {
        title: '尚未建立任何 Slash Command',
        description: '請從左側選擇或建立新的指令來開始使用。',
      },
      dialog: {
        title: { create: '新增 Slash Command', edit: '編輯 Slash Command' },
        description: { create: '建立新的自訂 Slash Command。', edit: '更新既有指令的詳細設定與內容。' },
        tabs: { basic: '基本設定', editor: '內容編輯' },
        fields: {
          scope: { label: '範圍' },
          identifier: { label: '命令名稱', placeholder: '輸入命令名稱', helper: '命令名稱需唯一，建議使用英文與連字號。' },
          title: { label: '顯示標題', placeholder: '輸入標題' },
          fileName: { label: '檔案名稱', placeholder: '輸入檔案名稱' },
          namespace: { label: '命名空間', placeholder: '輸入命名空間（可選）', helper: '用於組織相關命令' },
          description: { label: '指令描述', placeholder: '輸入描述（可選）', helper: '簡要說明此指令的用途與情境。' },
          content: { label: '指令內容', estimatedSize: '預估大小：{{size}}' },
        },
        validation: { identifier: '請輸入命令名稱。', title: '請輸入標題。', fileName: '請輸入檔案名稱。', content: '內容不可為空。' },
        actions: { cancel: '取消', save: '儲存變更', create: '建立項目' },
      },
    },
    skills: {
      header: { title: '編輯器', description: '瀏覽檔案。', count: '共 {{count}} 個檔案' },
      noSelection: '請從左側選擇技能檔案以檢視內容。',
    },
    documents: {
      meta: {
        'slash-commands': { title: 'Slash Command 設定' },
      },
      actions: { refresh: '重整', edit: '編輯', copyContent: '複製內容', download: '下載', delete: '刪除' },
      loading: '載入資料中…',
      stats: { total: '共 {{count}} 項' },
      scope: {
        badge: '範圍：{{scope}}',
        values: { project: '專案', user: '個人', local: '本地', plugin: '外掛' },
      },
      size: { badge: '大小：{{size}}' },
      confirmDelete: '確定要刪除「{{title}}」嗎？',
      sidebar: {
        defaultTitle: '設定列表',
        toggle: { expand: '展開側欄', collapse: '收合側欄' },
        searchPlaceholder: '搜尋...',
        scope: { all: '所有範圍' },
        loading: '載入資料中…',
        empty: '尚未找到符合條件的項目',
      },
    },
  },
};

export default agentSettings;
