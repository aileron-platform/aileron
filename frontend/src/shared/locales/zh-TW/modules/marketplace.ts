const marketplace = {
  common: {
    loading: '正在載入 Marketplace...',
    uncategorized: '未分類',
    noVersion: '無版本',
    unknown: '未知',
    actions: {
      back: '返回',
      cancel: '取消',
      refresh: '重新整理',
      remove: '移除',
      save: '儲存',
    },
    labels: {
      enabled: '已啟用',
    },
  },
  errors: {
    packageNotFound: '找不到 Marketplace 套件。',
    permission: {
      denied: '你沒有權限執行此 Marketplace 操作。',
    },
    module: {
      title: 'Marketplace 無法使用',
      description: 'Marketplace 模組無法呈現此畫面。',
      action: '返回套件列表',
    },
  },
  providers: {
    'claude-code': 'Claude Code',
    codex: 'Codex',
    gemini: 'Gemini',
  },
  features: {
    mcp: 'MCP servers',
    commands: 'Commands',
    hooks: 'Hooks',
    agentsMd: 'AGENTS.md',
    claudeMd: 'CLAUDE.md',
    geminiMd: 'GEMINI.md',
    agents: 'Agents',
    subagents: 'Subagents',
    slashCommands: 'Slash Commands',
    outputStyle: 'Output styles',
    skills: 'Skills',
  },
  packageTypes: {
    plugin: 'Plugin',
    extension: 'Extension',
  },
  sourceTypes: {
    created: '建立',
    imported: '匯入',
    unknown: '未知',
  },
  validation: {
    severity: {
      error: '錯誤',
      warning: '警告',
      info: '資訊',
      none: '有效',
    },
    required_manifest_missing: '缺少必要的 provider manifest。',
    invalid_manifest_shape: 'Provider manifest 結構無效。',
    package_identity_mismatch: '套件識別與 provider manifest 不一致。',
    metadata_conflict: 'Catalog 中繼資料與套件 manifest 中繼資料不一致。',
    invalid_package_id: 'Marketplace 套件 id 無效。',
    path_escape: 'Marketplace 套件路徑超出套件根目錄。',
    root_metadata_stripped: 'Marketplace 根中繼資料由 Marketplace 設定管理，未從套件編輯器儲存。',
  },
  center: {
    header: {
      title: 'Marketplace',
      description: '管理各 provider 原生套件、匯入、安裝與 registry 設定。',
      stats: '共 {{total}} 個套件 · 顯示 {{visible}} 個',
    },
    actions: {
      import: '匯入套件',
      create: '新增套件',
      refresh: '重新整理',
      settings: 'Marketplace 設定',
    },
    filters: {
      searchLabel: '搜尋套件',
      searchPlaceholder: '搜尋 ID、名稱、標籤或資源...',
      cliLabel: 'CLI 類型',
      providerLabel: '供應商',
      allProviders: '所有供應商',
      featureLabel: '功能篩選',
      allFeatures: 'All features',
      categoryLabel: '套件分類',
      allCategories: '所有套件',
      clear: '清除',
      validationLabel: '驗證',
      allSeverity: '所有嚴重度',
      sourceLabel: '來源',
      allSources: '所有來源',
    },
    viewModes: {
      grid: '網格檢視',
      list: '列表檢視',
    },
    list: {
      title: '套件列表',
      loading: '正在載入套件...',
      stats: {
        visible: '顯示 {{visible}} / {{total}}',
        page: '第 {{current}} / {{total}} 頁',
      },
      error: {
        title: '無法載入 Marketplace 套件。',
        retry: '重試',
      },
      empty: {
        title: '沒有符合篩選條件的套件',
        reset: '清除篩選',
      },
    },
    pagination: {
      pageCount: '第 {{current}} / {{total}} 頁',
      previous: '上一頁',
      next: '下一頁',
      perPage: '每頁',
      perPageOption: '每頁 {{count}} 筆',
    },
    accessibility: {
      resizePane: '調整套件篩選欄寬度',
    },
    card: {
      actions: {
        edit: '編輯',
        export: '匯出',
        install: '安裝',
        delete: '刪除',
      },
    },
  },
  detail: {
    header: {
      version: '版本 {{version}}',
      provider: '{{provider}}',
      category: '{{category}}',
    },
    actions: {
      back: '返回',
      backToCenter: '返回 Marketplace',
      edit: '編輯',
      export: '匯出',
      install: '安裝',
      delete: '刪除',
    },
    tabs: {
      basicInfo: '基本資訊',
      readme: 'README',
      manifest: 'Manifest',
      resources: 'Resources',
      targetPreview: 'Target preview',
    },
    featureEmpty: '此區塊沒有內容。',
    sidebar: {
      info: {
        title: '套件資訊',
        categoryLabel: '分類',
        versionLabel: '版本',
        providerLabel: '供應商',
      },
      features: {
        title: '套件區塊',
      },
    },
    basicInfo: {
      title: '套件資訊',
      packageId: 'Package ID',
      registryPath: 'Registry 路徑',
      provider: 'Provider',
      packageType: 'Package type',
      version: 'Version',
      validation: 'Validation',
      sections: {
        general: {
          title: '一般',
          description: 'Provider-native 套件識別與 registry 中繼資料。',
        },
        features: {
          title: '功能摘要',
          description: '從 provider-native layout 偵測到的可用套件區塊。',
        },
      },
    },
    viewer: {
      searchPlaceholder: '搜尋檔案...',
      refresh: '重新整理',
      fileNameFallback: '未命名檔案',
      descriptionFallback: '無描述',
      copy: '複製',
      download: '下載',
      copySuccess: '內容已複製',
      copyFailed: '無法複製內容',
      toml: {
        description: '描述',
        prompt: 'Prompt',
        developerInstructions: 'Developer instructions',
        raw: '原始 TOML',
      },
    },
    agentsMd: {
      placeholder: '撰寫 AGENTS.md 指引...',
      downloadFileName: 'AGENTS.md',
      actions: {
        copy: '複製',
        download: '下載',
        copySuccess: 'AGENTS.md 已複製',
        copyFailed: '無法複製 AGENTS.md',
        downloadSuccess: 'AGENTS.md 已下載',
      },
    },
    hooks: {
      header: {
        title: 'Package hooks',
      },
      badge: '{{count}} hooks',
      actions: {
        download: '下載 hooks',
      },
      downloadFileName: 'hooks.json',
      empty: {
        title: '沒有 hooks',
        description: '此套件未定義 hooks。',
      },
      toasts: {
        downloadSuccess: 'Hooks 已下載',
      },
      card: {
        matchersTitle: 'Matchers',
        matcherLabel: 'Matcher',
        actionsCount: '{{count}} actions',
        executionTypeCommand: 'Command',
        executionTypes: {
          command: 'Command',
          http: 'HTTP',
          mcp_tool: 'MCP tool',
          prompt: 'Prompt',
          agent: 'Agent',
        },
        sequential: 'Sequential',
        timeoutSeconds: '{{count}}s',
        timeoutMilliseconds: '{{count}}ms',
        statusMessage: 'Status: {{value}}',
        shell: 'Shell: {{value}}',
        async: 'Async',
        asyncRewake: 'Rewake',
        ifLabel: 'if',
        emptyCommand: '沒有 command',
        emptyUrl: '沒有 URL',
        moreActions: '+{{count}} more actions',
        summary: {
          matchers: '{{count}} matchers',
          commands: '{{count}} commands',
        },
      },
    },
    mcp: {
      header: {
        title: 'Package MCP servers',
      },
      badge: '{{count}} servers',
      actions: {
        download: '下載 MCP',
      },
      downloadFileName: 'mcp.json',
      empty: {
        title: '沒有 MCP servers',
        description: '此套件未定義 MCP servers。',
      },
      toasts: {
        copySuccess: 'MCP config 已複製',
        downloadSuccess: 'MCP config 已下載',
      },
      card: {
        copyTooltip: '複製 MCP config',
        showEnvValues: '顯示 environment values',
        hideEnvValues: '隱藏 environment values',
        sections: {
          command: 'Command',
          url: 'URL',
          env: 'Environment',
          headers: 'Headers',
        },
      },
    },
    readme: {
      title: 'README',
      description: '以安全化 Markdown 顯示 package README.md。',
      empty: '沒有 README 內容。',
    },
    validation: {
      title: '驗證結果',
      description: '此 package 的 provider-native 驗證結果。',
      metadataConflict: 'Catalog metadata 與 package manifest 不一致。',
    },
    metadata: {
      title: '中繼資料',
      catalog: 'Catalog entry',
      manifest: 'Package manifest',
    },
    resources: {
      title: 'Indexed resources',
    },
    activity: {
      title: '活動',
      description: '近期套件範圍的匯入、安裝與刪除紀錄。',
      empty: '尚無套件活動。',
    },
  },
  onboarding: {
    title: 'Marketplace 設定',
    description: '瀏覽套件前先初始化或 clone 本機 registry。',
    setupTitle: '設定本機 registry',
    setupDescription: 'Marketplace 會把各家原生套件存放在系統管理的共用 registry root。',
    rootPath: 'Registry root：{{path}}',
    actions: {
      initialize: '初始化 registry',
      initializeDescription: '在本機建立依 provider 分離的 root。',
      clone: 'Clone registry',
      cloneDescription: '把既有 registry clone 到受管理的 root。',
    },
  },
  import: {
    title: '匯入套件',
    description: '掃描外部 provider marketplace repository，並選擇要複製到本機的套件。',
    fields: {
      provider: 'Provider',
      sourceKind: '來源類型',
      source: 'Repository URL',
      branch: 'Branch',
      localFile: '上傳套件封存檔',
      newPackageId: '新套件 ID',
      newPackageIdPlaceholder: 'package-id-copy',
    },
    sourceKinds: {
      git: 'Git repository',
      local: '本機上傳',
    },
    localFile: {
      empty: '尚未選擇封存檔',
    },
    branch: {
      placeholder: '選擇 branch',
    },
    actions: {
      scan: '掃描來源',
      import: '匯入選取項目',
      settings: 'SSH 設定',
      chooseFile: '選擇封存檔',
      loadBranches: '載入分支',
      selectAll: '全選',
      clearSelection: '取消全選',
    },
    candidates: {
      title: '候選套件',
      empty: '掃描來源後會列出可匯入的候選套件。',
      duplicate: '重複',
    },
    duplicateActions: {
      skip: '略過',
      overwrite: '覆寫',
      importAsNew: '匯入為新 ID',
    },
    validation: {
      duplicate: '本機已存在相同 provider 與 ID 的套件。',
      sourceRequired: '必須提供匯入來源。',
      invalidSourceKind: '匯入來源類型無效。',
      invalidRepositoryUrl: '匯入 repository URL 無效。',
      invalidRef: '匯入 ref 無效。',
      localPathNotFound: '找不到匯入本機路徑。',
      localPathNotAllowed: '不允許使用此匯入本機路徑。',
      rawPrivateKeyUnsupported: 'Marketplace 匯入不接受原始 private key 內容。',
      httpsTokenUnsupported: '此版本的 Marketplace 匯入不支援 HTTPS token 驗證。',
      sshKeyRequired: '從 SSH repository 匯入前，請先產生 Marketplace SSH key。',
      cloneFailed: 'Marketplace 匯入來源 checkout 失敗。',
      branchListFailed: 'Marketplace 匯入來源 branch 查詢失敗。',
      invalidUploadArchive: '請上傳有效的 ZIP 封存檔。',
      nestedRemoteSourceUnsupported: '此版本的 Marketplace 不支援巢狀遠端套件來源。',
      nested_remote_source_unsupported: '此版本的 Marketplace 不支援巢狀遠端套件來源。',
    },
    result: {
      summary: '已匯入 {{imported}}，略過 {{skipped}}，失敗 {{failed}}，重複 {{duplicates}}，警告 {{warnings}}。',
      failedDetails: '失敗項目',
    },
  },
  install: {
    title: '安裝套件',
    description: '透過目標 workspace runtime 執行 provider CLI 來安裝套件。',
    fields: {
      provider: 'Provider',
      package: '套件',
      workspace: '目標 workspace',
    },
    workspaceSelect: {
      placeholder: '選擇 workspace',
      loading: '正在載入 workspace...',
      currentWorkspace: '目前 workspace',
    },
    preflight: {
      loading: '正在檢查 provider CLI 可用性...',
      ready: 'Provider CLI 可用（{{version}}）。',
      unavailable: 'Provider CLI 不可用：{{code}}。',
      unknownVersion: '版本未知',
    },
    commandPreview: 'Command preview',
    output: {
      title: '已遮蔽輸出',
      stdout: 'stdout',
      stderr: 'stderr',
      truncated: '輸出已截斷。',
    },
    actions: {
      install: '安裝',
    },
    result: {
      success: '套件已安裝。',
      failed: '安裝失敗，錯誤代碼：{{code}}',
      timeout: 'Provider CLI 未在時間內完成安裝。錯誤代碼：{{code}}',
      validation: 'Provider 驗證阻擋安裝。錯誤代碼：{{code}}',
      cliUnavailable: '目標 workspace 無法使用 provider CLI。錯誤代碼：{{code}}',
      cliVersionUnsupported: 'Provider CLI 版本不支援。錯誤代碼：{{code}}',
      cliCapabilityMissing: 'Provider CLI 缺少必要安裝能力。錯誤代碼：{{code}}',
      runtimeUnavailable: 'Workspace runtime 不可用。錯誤代碼：{{code}}',
    },
  },
  export: {
    title: '匯出套件',
    description: '建立以 provider-native 套件目錄為根的 .zip archive。',
    fields: {
      archive: 'Archive',
      root: 'Archive root',
    },
    compatibilityNotice: '第一版 Marketplace 不保證匯出的 archive 可直接匯入。',
    actions: {
      export: '匯出 .zip',
    },
    result: {
      ready: '匯出 archive 已就緒。',
    },
  },
  delete: {
    title: '刪除套件',
    description: '使用目前 package revision 硬刪除本機 Marketplace 套件。',
    warning: '這會移除 package directory，並在適用時移除 provider marketplace entry。',
    fields: {
      package: '套件',
      revision: 'Revision',
      confirm: '輸入 {{id}} 確認',
    },
    actions: {
      delete: '刪除套件',
    },
    result: {
      success: '套件已刪除。',
      failed: '刪除失敗，錯誤代碼：{{code}}',
    },
  },
  activity: {
    actions: {
      import: '匯入',
      install: '安裝',
      delete: '刪除',
    },
    status: {
      success: '成功',
      failed: '失敗',
    },
  },
  editor: {
    createTitle: '建立 Marketplace 套件',
    editTitle: '編輯 Marketplace 套件',
    dirty: '尚未儲存',
    unsaved: {
      leaveConfirm: 'Marketplace package 有未儲存變更。要放棄變更並離開嗎？',
      title: '尚未儲存的變更',
      description: '你可以儲存變更、放棄變更，或取消離開。',
    },
    saveStatus: {
      success: '已儲存',
      validationError: '驗證失敗',
      revisionConflict: 'Revision 衝突',
    },
    actions: {
      save: '儲存',
      discard: '放棄',
    },
    providerStep: {
      title: '建立 Marketplace 套件',
      description: '先選擇 provider 格式，再編輯套件欄位。',
      heading: '選擇 provider 格式',
      help: '選定的 provider 會決定原生 scaffold、可見編輯區塊、驗證、匯出格式與安裝指令。',
      sectionsLabel: '編輯區塊',
      options: {
        'claude-code': {
          description: '建立 Claude Code plugin package。',
        },
        codex: {
          description: '建立 Codex plugin package。',
        },
        gemini: {
          description: '建立 Gemini extension package。',
        },
      },
    },
    common: {
      rename: {
        action: '重新命名',
        title: '重新命名路徑',
        description: '更新 package 內的相對檔案路徑；內容編輯維持獨立。',
        pathLabel: '檔案路徑',
        pathPlaceholder: 'agents/review-agent.md',
      },
    },
    fields: {
      provider: '供應商',
      providerHint: '供應商會決定原生套件 layout 與編輯區塊。',
      packageId: '套件 ID',
      packageIdPlaceholder: 'review-assistant',
      packageIdHint: '作為 provider-native 資料夾與套件識別。',
      packageIdPreviewFallback: 'package-id',
      displayName: '顯示名稱',
      displayNamePlaceholder: 'Review Assistant',
      description: '描述',
      descriptionPlaceholder: '描述此套件會安裝或啟用的內容。',
      registryPath: 'Registry 路徑',
    },
    defaults: {
      packageName: 'package-id',
      codexMarketplaceName: 'local-codex-marketplace',
      claudeMarketplaceName: 'local-claude-marketplace',
      ownerName: '本機使用者',
      description: '描述此套件。',
    },
    requiredTabs: {
      form: '表單',
      json: 'JSON',
    },
    requiredFields: {
      title: '必填欄位',
      description: '只編輯一次 provider 必填欄位；JSON 模式顯示各 provider-native 輸出文件。',
    },
    tabs: {
      basic: '基本資訊',
      agentsMd: 'AGENTS.md',
      pluginManifest: 'Plugin manifest',
      extensionManifest: 'Extension manifest',
      packageMetadata: 'Package metadata',
      readme: 'README',
      skills: 'Skills',
      commands: 'Commands',
      slashCommand: 'Slash Commands',
      agents: 'Agents',
      subagents: 'Subagents',
      hooks: 'Hooks',
      mcp: 'MCP',
      outputStyle: 'Output styles',
      files: '檔案管理',
      claudeMd: 'CLAUDE.md',
      geminiMd: 'GEMINI.md',
      tomlCommands: 'TOML commands',
      policies: 'Policies',
    },
    packageSections: {
      listing: {
        title: 'Package listing 欄位',
        description: '用來產生此 package listing 的欄位。這裡不提供編輯整份 marketplace manifest。',
      },
      manifest: {
        description: '此套件的 provider-native manifest 內容。',
      },
      commonMetadata: {
        title: 'Common plugin metadata',
      },
      interfaceMetadata: {
        title: 'Interface metadata',
        description: '儲存在 provider-native plugin manifest 的 Codex interface metadata。',
        summaryFallback: '描述此 plugin 在 Codex 中的呈現方式。',
      },
      codexPolicy: {
        title: 'Codex marketplace policy',
        description: '儲存在 Codex marketplace entry 中，目前 package 的 policy projection。',
      },
      geminiAdvanced: {
        title: 'Gemini 進階 manifest 欄位',
        description: '保留在 gemini-extension.json 內的結構化 extension settings。',
      },
      providerGuidance: {
        title: 'Provider guidance',
        description: '隨 extension 安裝的 Gemini 指引。',
        defaultBody: '新增此 extension 的 Gemini 專用指引。',
        placeholder: '撰寫 GEMINI.md 指引...',
      },
      readme: {
        description: '顯示在套件 detail 與 marketplace preview 的 README 內容。',
        placeholder: '撰寫 README 內容...',
      },
      fields: {
        packageId: 'Package ID',
        packageName: 'Package name',
        provider: 'Provider',
        category: 'Category',
        source: 'Source',
        tags: 'Tags',
        strict: 'Strict',
        manifestId: 'Manifest ID',
        manifestName: 'Manifest name',
        version: 'Version',
        file: 'File',
        marketplaceName: 'Marketplace 名稱',
        ownerName: 'Owner 名稱',
        rootMetadataHint: 'Root marketplace metadata 請到 Marketplace 設定編輯。',
        description: '描述',
        authorName: 'Author name',
        authorEmail: 'Author email',
        authorUrl: 'Author URL',
        homepage: 'Homepage',
        repository: 'Repository',
        license: 'License',
        keywords: 'Keywords',
        policyInstallation: 'policy.installation',
        policyAuthentication: 'policy.authentication',
        displayName: 'displayName',
        shortDescription: 'shortDescription',
        longDescription: 'longDescription',
        developerName: 'developerName',
        interfaceCategory: 'interface.category',
        capabilities: 'capabilities',
        websiteURL: 'websiteURL',
        privacyPolicyURL: 'privacyPolicyURL',
        termsOfServiceURL: 'termsOfServiceURL',
        defaultPrompt: 'defaultPrompt',
        brandColor: 'brandColor',
        composerIcon: 'composerIcon',
        logo: 'logo',
        screenshots: 'screenshots',
        contextFileName: 'contextFileName',
        excludeTools: 'excludeTools',
        migratedTo: 'migratedTo',
        planDirectory: 'plan.directory',
        settings: 'settings[]',
        themes: 'themes[]',
        mcpServers: 'mcpServers',
      },
    },
    required: {
      json: {
        tabs: {
          entry: 'Marketplace entry',
          plugin: 'Plugin settings',
          extension: 'Extension settings',
        },
        infoLabel: '顯示 {{document}} 的 JSON 說明',
        popovers: {
          entry: '只編輯 marketplace.json 中目前這個 package entry。Root marketplace metadata 與同檔其他 entries 不在此套件編輯器管理。',
          plugin: '編輯此 package 的 plugin.json 必填設定。合法 JSON 會立即同步回必填欄位表單。',
          extension: '編輯此 package 的 gemini-extension.json 設定。合法 JSON 會立即同步回必填欄位表單。',
        },
        fileBadge: {
          thisEntryOnly: '僅此 entry',
        },
        parseError: 'JSON 格式無效。文字會保留，但表單欄位會維持最後一次合法 JSON 的值。',
      },
    },
    agentsMd: {
      title: 'AGENTS.md',
      description: '隨 package 安裝到 workspace 的操作指引。',
      placeholder: '撰寫 AGENTS.md 指引...',
      status: {
        loading: '正在載入 AGENTS.md...',
      },
      actions: {
        copy: '複製',
        download: '下載',
      },
    },
    featureSections: {
      count: '{{count}} items',
      actions: {
        add: '新增',
      },
      skills: {
        emptyTitle: '沒有 skills',
        emptyDescription: 'Marketplace file APIs 串接後可新增 package skills。',
      },
      agents: {
        emptyTitle: '沒有 agents',
        emptyDescription: 'Marketplace file APIs 串接後可新增 package agents。',
      },
      commands: {
        emptyTitle: '沒有 commands',
        emptyDescription: 'Marketplace file APIs 串接後可新增 package commands。',
      },
      mcp: {
        emptyTitle: '沒有 MCP servers',
        emptyDescription: 'Marketplace file APIs 串接後可新增 MCP server definitions。',
      },
      hooks: {
        emptyTitle: '沒有 hooks',
        emptyDescription: 'Marketplace file APIs 串接後可新增 hook definitions。',
      },
      outputStyle: {
        emptyTitle: '沒有 output styles',
        emptyDescription: 'Marketplace file APIs 串接後可新增 output style documents。',
      },
      files: {
        emptyTitle: '沒有 files',
        emptyDescription: 'Marketplace file APIs 串接後可瀏覽 package files。',
      },
    },
    fileManager: {
      skills: {
        title: 'Skills',
      },
      packageFiles: {
        title: '檔案',
        rootLabel: '套件根目錄',
      },
      search: {
        placeholder: '搜尋檔案...',
      },
      sidebar: {
        refresh: '重新整理',
        upload: '上傳',
        createFile: '建立檔案',
        createFolder: '建立資料夾',
      },
      actions: {
        save: '儲存',
        create: {
          trigger: '建立',
        },
      },
      viewer: {
        noFile: '未選擇檔案',
        placeholder: '撰寫 package skill 內容...',
        binaryTitle: '二進位資產',
        binaryDescription: '此檔案會以 {{mimeType}} 處理，不會用文字編輯器開啟。',
        binaryDownloadContent: '{{name}} 的二進位資產 placeholder。',
        previewAlt: '{{name}} 預覽',
        previewUnavailable: '此二進位檔案類型無法預覽。',
        download: '下載',
        delete: '刪除',
      },
    },
    documentViewer: {
      unsavedFile: '未儲存',
      search: {
        placeholder: '搜尋檔案...',
      },
      actions: {
        add: '新增',
        refresh: '重新整理',
        delete: '刪除',
        copy: '複製',
        download: '下載',
      },
      editor: {
        placeholder: '撰寫 Markdown 內容...',
        tomlPlaceholder: '撰寫 TOML 內容...',
      },
      formats: {
        markdown: 'Markdown',
        toml: 'TOML',
      },
      create: {
        title: '新增 {{resource}}',
        description: '在此 Marketplace package 建立 {{format}} resource。',
        defaultTitle: '新的 Markdown resource',
        defaultDescription: '由 Marketplace editor 建立。',
        fields: {
          path: {
            label: '檔案路徑',
            placeholder: 'commands/new-command.md',
            helper: '使用 provider 原生相對路徑，未填 {{extension}} 時會自動補上。',
          },
          content: {
            label: '內容',
          },
        },
        validation: {
          pathRequired: '檔案路徑為必填。',
          contentRequired: '內容為必填。',
        },
        actions: {
          create: '建立',
        },
      },
      empty: {
        filtered: '沒有符合搜尋的檔案。',
      },
      agents: {
        title: 'Subagents',
        empty: '沒有 subagents',
      },
      commands: {
        title: 'Slash Commands',
        empty: '沒有 slash commands',
      },
      outputStyle: {
        title: 'Output styles',
        empty: '沒有 output styles',
      },
      policies: {
        title: 'Policies',
        empty: '沒有 policies',
      },
    },
    mcp: {
      card: {
        sections: {
          command: 'Command',
          arguments: 'Arguments',
          environment: 'Environment',
        },
      },
      dialog: {
        title: '編輯 MCP server',
        titleCreate: '新增 MCP server',
        description: '更新此 Marketplace package 內的 MCP server definition。',
        descriptionCreate: '建立此 Marketplace package 的 MCP server definition。',
        create: {
          defaultTitle: '新的 MCP server',
          defaultDescription: '由 Marketplace editor 建立。',
        },
        actions: {
          save: '儲存 server',
        },
        transport: {
          label: 'Transport type',
          options: {
            stdio: {
              label: 'Standard I/O',
              description: '透過 stdio 執行本機 command。',
            },
            sse: {
              label: 'Server-Sent Events',
              description: '連線到遠端 SSE endpoint。',
            },
            http: {
              label: 'Streamable HTTP',
              description: '連線到遠端 HTTP endpoint。',
            },
          },
        },
        validation: {
          nameRequired: 'Server 名稱為必填。',
          descriptionRequired: '描述為必填。',
          commandRequired: 'stdio transport 必須填寫 command。',
          urlRequired: '遠端 transport 必須填寫 URL。',
        },
        fields: {
          name: {
            label: '名稱',
            placeholder: 'repository-context',
          },
          description: {
            label: '描述',
            placeholder: '描述這個 server 提供的能力',
          },
          command: {
            label: 'Command',
            placeholder: 'node',
          },
          args: {
            label: 'Arguments',
            add: '新增 argument',
            empty: '沒有 arguments',
            placeholder: 'Argument {{index}}',
          },
          url: {
            label: 'URL',
            placeholderSse: 'https://example.com/sse',
            placeholderHttp: 'https://example.com/mcp',
            hintSse: '使用 MCP server 暴露的 SSE endpoint。',
            hintHttp: '使用 MCP server 暴露的 streamable HTTP endpoint。',
          },
          headers: {
            label: 'Headers',
            add: '新增 header',
            keyPlaceholder: 'Header',
            valuePlaceholder: 'Value',
            empty: '沒有 headers',
            hint: 'Header values 可以包含環境變數 placeholder。',
          },
          env: {
            label: '環境變數',
            add: '新增變數',
            keyPlaceholder: 'NAME',
            valuePlaceholder: 'value',
            empty: '沒有環境變數',
          },
        },
      },
    },
    hooks: {
      card: {
        matchersTitle: 'Matchers',
        matcherLabel: 'Matcher',
        actionsCount: '{{count}} actions',
        executionTypeCommand: 'Command',
        sequential: 'Sequential',
        summary: {
          matchers: '{{count}} matchers',
          commands: '{{count}} commands',
        },
      },
      dialog: {
        title: '編輯 hook',
        titleCreate: '新增 hook',
        description: {
          'claude-code': '設定 Claude Code command hook event、matcher 與 execution options。',
          codex: '設定 Codex hooks.json event、matcher、command execution 與 status message。',
          gemini: '設定 Gemini hooks/hooks.json event、sequential execution、command name 與毫秒 timeout。',
        },
        create: {
          defaultTitle: '新的 hook',
          defaultDescription: '由 Marketplace editor 建立。',
        },
        actions: {
          save: '儲存 hook',
        },
        validation: {
          commandRequired: '每個 matcher 至少需要一個 command。',
        },
        fields: {
          name: {
            label: '名稱',
            placeholder: 'review-pre-submit',
          },
          event: {
            label: 'Event',
            placeholder: '選擇 hook event',
          },
        },
        matchers: {
          title: 'Matchers',
          add: '新增 matcher',
          patternLabel: 'Matcher pattern',
          patternPlaceholder: '*',
          sequentialLabel: '依序執行 hooks',
          sequentialHelp: 'Gemini 可針對此 matcher group 依序執行 hook actions，而不是平行執行。',
          patternHelp: {
            'claude-code': {
              overview: '使用 matcher 限制哪些 Claude Code tool 或 event target 會執行此 hook。',
              literal: '支援明確 tool 名稱。',
              regex: 'Regex pattern 可匹配多個 tools。',
              wildcard: '使用 * 匹配全部。',
            },
            codex: {
              overview: '使用 matcher 限制哪些 Codex tool、permission 或 session source 會執行此 hook。',
              literal: '支援 Bash 或 apply_patch 這類明確 tool 名稱。',
              regex: 'Regex pattern 可匹配多個 tools。',
              wildcard: '使用 * 或空 matcher 匹配全部。',
            },
            gemini: {
              overview: '使用 matcher 限制哪些 Gemini CLI tool 或 agent event 會執行此 hook。',
              literal: '支援明確 tool 或 agent 名稱。',
              regex: 'Regex pattern 可匹配多個目標。',
              wildcard: '使用 * 匹配全部。',
            },
          },
        },
        executions: {
          title: 'Commands',
          add: '新增 command',
          timeoutLabel: {
            'claude-code': 'Timeout 秒數',
            codex: 'Timeout 秒數',
            gemini: 'Timeout 毫秒',
          },
          timeoutHelp: {
            'claude-code': 'Claude Code command handler 使用秒為單位。',
            codex: 'Codex hook command 使用秒為單位，未設定時使用 CLI 預設行為。',
            gemini: 'Gemini hook command 使用毫秒為單位，預設為 60000。',
          },
          conditionLabel: 'Condition',
          conditionPlaceholder: 'event.tool_name == "Bash"',
          conditionHelp: '選填 Claude Code if expression，用來決定此 handler 是否執行。',
          commandLabel: {
            'claude-code': 'Command',
            codex: 'Command',
            gemini: 'Command',
          },
          commandPlaceholder: {
            'claude-code': 'npm test',
            codex: 'npm test',
            gemini: 'gemini context load',
          },
          commandHelp: {
            'claude-code': 'Claude Code plugin editor 第一版以 command hooks 表單為主；進階 handler type 可從 package files 管理。',
            codex: 'Codex 會從 workspace context 執行 command hooks。',
            gemini: 'Gemini 會從 extension 或 workspace context 執行 command hooks。',
          },
          nameLabel: 'Hook name',
          namePlaceholder: 'workspace-context',
          nameHelp: 'Gemini hooks/hooks.json 裡的 hook action name。',
          descriptionLabel: 'Description',
          descriptionPlaceholder: '描述此 hook 做什麼。',
          descriptionHelp: '選填 Gemini hook action description。',
          statusMessageLabel: 'Status message',
          statusMessagePlaceholder: 'Running checks',
          statusMessageHelp: 'Hook 執行時顯示的選填進度文字。',
          asyncLabel: '非同步執行',
          asyncRewakeLabel: '非同步完成後 rewake',
          shellLabel: 'Shell',
          shellPlaceholder: '選擇 shell',
          shellOptions: {
            bash: 'Bash',
            powershell: 'PowerShell',
          },
          remove: '移除 command',
        },
        codexFeatureFlag: 'Codex plugin hooks 需要在目標 Codex config layer 啟用 features.codex_hooks。',
      },
      events: {
        PreToolUse: { label: 'PreToolUse', description: 'Tool call 前執行。' },
        PostToolUse: { label: 'PostToolUse', description: 'Tool call 後執行。' },
        PermissionRequest: { label: 'PermissionRequest', description: 'Codex 要求 permission 時執行。' },
        UserPromptSubmit: { label: 'UserPromptSubmit', description: '使用者送出 prompt 時執行。' },
        Notification: { label: 'Notification', description: '發出 notification 時執行。' },
        Stop: { label: 'Stop', description: '主 agent 停止時執行。' },
        SubagentStop: { label: 'SubagentStop', description: 'Subagent 停止時執行。' },
        PreCompact: { label: 'PreCompact', description: 'Context compaction 前執行。' },
        PreCompress: { label: 'PreCompress', description: 'Gemini context compression 前執行。' },
        SessionStart: { label: 'SessionStart', description: 'Session 開始時執行。' },
        SessionEnd: { label: 'SessionEnd', description: 'Session 結束時執行。' },
        BeforeTool: { label: 'BeforeTool', description: 'Gemini tool call 前執行。' },
        AfterTool: { label: 'AfterTool', description: 'Gemini tool call 後執行。' },
        BeforeAgent: { label: 'BeforeAgent', description: 'Gemini subagent 執行前執行。' },
        AfterAgent: { label: 'AfterAgent', description: 'Gemini subagent 執行後執行。' },
        BeforeModel: { label: 'BeforeModel', description: 'Gemini 送出 model request 前執行。' },
      },
    },
    featureMeta: {
      labels: {
        transport: 'Transport',
        env: 'Environment',
        matcher: 'Matcher',
        timeout: 'Timeout',
        type: 'Type',
        sequential: 'Sequential',
      },
    },
    scaffold: {
      skills: {
        reviewChecklist: {
          title: 'Review checklist',
          description: '引導結構化 review 流程，涵蓋 findings、risk 與 test coverage。',
        },
        riskMap: {
          title: 'Risk map',
          description: '將變更檔案對應到可能的產品與 runtime 風險。',
        },
      },
      agents: {
        reviewAgent: {
          title: 'Review agent',
          description: '專注於 bug、regression 與 missing-test analysis 的 package agent。',
        },
      },
      commands: {
        reviewSummary: {
          title: 'Review summary',
          description: '根據 staged changes 產生精簡 review summary。',
        },
        reviewTests: {
          title: 'Review tests',
          description: '針對目前 diff 建議聚焦的驗證指令。',
        },
      },
      mcp: {
        repositoryContext: {
          title: 'Repository context',
          description: '提供 repository metadata 與 diff context 給 CLI runtime。',
        },
      },
      hooks: {
        reviewPreSubmit: {
          title: 'Review pre-submit',
          description: '在 submit-oriented tool calls 前執行 review checks。',
        },
      },
      outputStyle: {
        reviewFindings: {
          title: 'Review findings',
          description: '以 findings first、summary second 的方式格式化 review output。',
        },
      },
      policies: {
        safeShell: {
          title: 'Safe shell policy',
          description: '阻擋 Gemini CLI 的破壞性 shell command pattern。',
        },
      },
      files: {
        packageIcon: {
          title: 'Package icon',
          description: '顯示在 package catalog 介面的 SVG icon asset。',
        },
        license: {
          title: 'License',
          description: '隨 provider-native package 一起提供的 license file。',
        },
      },
    },
  },
  settings: {
    title: 'Marketplace 設定',
    description: '管理 registry 中繼資料、版本控制、remote、Git 身分、SSH key 與活動紀錄。',
    tabs: {
      general: '一般',
      versionControl: '版本控制',
      remote: 'Remote',
      gitUser: 'Git 使用者',
      sshKeys: 'SSH Keys',
      activity: '活動',
    },
    general: {
      title: '一般',
      description: 'Marketplace provider 匯出使用的 registry 中繼資料。',
      displayName: 'Registry 顯示名稱',
      maintainerName: '維護者名稱',
      maintainerEmail: '維護者 Email',
      rootPath: 'Registry root',
      status: 'Registry 狀態',
      statusReady: '可用',
      descriptionField: 'Registry 描述',
      rootMetadataTitle: 'Root marketplace metadata',
      rootMetadataDescription: '這些欄位會產生各 provider 匯出用的 root marketplace.json metadata。',
      generatedPreviewTitle: '產生的 marketplace.json 預覽',
      generatedPreviewDescription: '預覽每個 provider 匯出時寫入的 root metadata 結構。',
      previews: {
        claude: {
          title: 'Claude Code marketplace.json',
        },
        codex: {
          title: 'Codex marketplace.json',
        },
      },
    },
    versionControl: {
      title: 'Registry 版本控制',
      description: 'Commit 或同步前檢視依 provider 分離的 registry 變更。',
      actions: {
        fetch: 'Fetch',
        pull: 'Pull',
        push: 'Push',
        stage: 'Stage',
        unstage: 'Unstage',
        commit: 'Commit staged changes',
      },
      status: {
        title: 'Repository 狀態',
        description: '目前 branch、remote 與 staged 變更摘要。',
        staged: '{{count}} staged',
        unstaged: '{{count}} unstaged',
      },
      changes: {
        title: '變更檔案',
        staged: 'Staged',
        unstaged: 'Unstaged',
      },
      diff: {
        title: 'Diff 預覽',
      },
      commit: {
        title: 'Commit',
        description: 'Commit staged Marketplace registry files。',
        placeholder: '描述 registry 變更...',
      },
      history: {
        title: 'History',
        description: '近期 registry commits。',
      },
      errors: {
        conflict: 'Pull 已停止，因為 registry 檔案發生衝突。請在 Marketplace 外解決衝突後重新整理。',
        unsupportedBranch: '此 repository 需要目前不支援的 branch 操作。Marketplace 第一版只支援目前 branch 的 fetch、pull、push、status、diff、commit 與 history。',
      },
      setupRequired: {
        title: '需要設定 Git repository',
        description: '初始化或 clone Marketplace registry後才能使用版本控制。',
        action: '開啟 repository 設定',
      },
    },
    git: {
      repository: {
        title: 'Repository',
        description: 'Marketplace registry的 Git remote 與 branch 設定。',
        status: 'Marketplace API 串接前，repository 設定會先以 placeholder data 呈現。',
        remoteUrl: 'Remote URL',
        branch: 'Branch',
      },
      user: {
        title: 'Git 使用者',
        description: 'Marketplace registry 變更 commit 時使用的身分。',
        name: '使用者名稱',
        email: '使用者 Email',
        save: '儲存 Git 設定',
      },
    },
    activity: {
      title: '活動',
      description: 'Registry 範圍的匯入、安裝與刪除紀錄。',
      empty: '目前沒有 Marketplace 活動紀錄。',
    },
  },
};

export default marketplace;
