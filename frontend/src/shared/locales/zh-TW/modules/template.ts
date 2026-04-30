const template = {
  center: {
    loading: '載入中...',
    onboarding: {
      loading: '正在檢查模板中心倉庫...',
      title: '設定模板中心 Registry',
      description: '請先 clone 既有 registry，或將目前 registry 初始化為 Git，才能進入模板中心。',
      unknownError: '未知錯誤',
      statusError: {
        title: '無法檢查倉庫狀態',
        description: '模板中心需要先取得倉庫狀態，才能載入一般工作流程。',
      },
      actions: {
        retry: '重新嘗試',
      },
      validation: {
        cloneUrlRequired: 'Repository URL 為必填。',
      },
      clone: {
        title: 'Clone 既有 Registry',
        description: '使用已包含模板中心 registry 檔案的 Git 倉庫。',
        blockedTitle: '無法 Clone',
        blockedDescription: '本地 registry 檔案已存在，為避免覆蓋內容已停用 clone。',
        blockedReason: '請初始化目前 registry，以保留並追蹤既有本地檔案。',
        urlLabel: 'Repository URL',
        urlPlaceholder: 'git@github.com:username/template-registry.git',
        branchLabel: '分支',
        branchPlaceholder: 'main',
        branchHelper: '留空則使用倉庫預設分支。',
        progressTitle: 'Clone 進度',
        actions: {
          clone: 'Clone Registry',
          cloning: 'Clone 中...',
        },
      },
      init: {
        title: '初始化目前 Registry',
        description: '保留既有本地檔案，並開始用 Git 追蹤此 registry。',
        actions: {
          init: '初始化 Registry',
          initializing: '初始化中...',
        },
      },
      toasts: {
        cloneStarted: {
          title: 'Clone 已開始',
          description: '模板中心正在背景 clone registry。',
        },
        cloneFailed: {
          title: 'Clone 失敗',
          description: '無法 clone registry：{{error}}',
        },
        initSuccess: {
          title: 'Registry 已初始化',
          description: '模板中心 registry 現在已由 Git 追蹤。',
        },
        initFailed: {
          title: '初始化失敗',
          description: '無法初始化 registry：{{error}}',
        },
      },
    },
    header: {
      title: '模板中心',
      description: '瀏覽與管理所有模板，支援快速安裝、匯出與匯入。',
      stats: '共 {{total}} 個模板 · 顯示 {{visible}} 個',
    },
    actions: {
      import: '匯入模板',
      create: '新增模板',
      refresh: '重新整理',
      settings: '設定模板中心',
    },
    filters: {
      searchLabel: '搜尋模板',
      searchPlaceholder: '輸入關鍵字...',
      featureLabel: '功能篩選',
      cliLabel: 'CLI 類型',
      allCli: '全部 CLI 類型',
      cliOptions: {
        claudeCode: 'ClaudeCode',
        codex: 'Codex',
        gemini: 'Gemini',
        opencode: 'OpenCode',
      },

      clear: '清除',
      categoryLabel: '模板分類',
      allTemplates: '全部模板',
      allFeatures: '全部功能',
      featureOptions: {
        mcp: 'MCP',
        commands: 'Commands',
        hooks: 'Hooks',
        agentsMd: 'AGENTS.md',
        agentMd: 'AGENT.md',
        agents: 'Agents',
        outputStyle: 'Output Style',
        scripts: 'Scripts',
        skills: 'Skills',
      },
    },
    accessibility: {
      resizePane: '調整欄寬',
    },
    list: {
      title: '模板列表',
      description: '共 {{total}} 個模板，依需求快速篩選或新增。',
      stats: {
        visible: '顯示 {{visible}} / {{total}}',
        page: '第 {{current}} / {{total}} 頁',
      },
      loading: '載入模板中...',
      error: {
        title: '無法載入模板資料。',
        retry: '重新嘗試',
      },
      empty: {
        title: '找不到符合條件的模板',
        reset: '清除篩選',
      },
    },
    pagination: {
      pageCount: '頁數 {{current}} / {{total}}',
      previous: '上一頁',
      next: '下一頁',
      perPage: '每頁顯示',
      perPageOption: '{{count}}',
    },
    dialogs: {
      delete: {
        title: '確認刪除模板',
        description: '確定要刪除模板「{{name}}」嗎？此操作無法復原。',
        cancel: '取消',
        confirm: '確認刪除',
      },
    },
    settings: {
      tabs: {
        versionControl: '版本控制',
        gitUser: 'Git 使用者',
        sshKeys: 'SSH Keys',
      },
      versionControl: {
        rebuildProgressTitle: '模板重建進度',
        confirmDiscard: '確定要捨棄「{{path}}」的變更嗎？此操作無法復原。',
        confirmDiscardMultiple: '確定要捨棄 {{count}} 個檔案的變更嗎？此操作無法復原。',
        mode: {
          title: '版本控制',
          fileChanges: '檔案變更',
          commitHistory: '變更記錄',
        },
        registryStale: {
          description: 'Registry 內容可能已變更，建議重建模板索引以同步最新狀態。',
        },
        setupRequired: {
          title: '需要先設定 Git 倉庫',
          description: '請先初始化目前模板 registry，或從既有遠端 registry clone 後再使用版本控制。',
          action: '開啟倉庫設定',
        },
        remoteMissing: {
          description: '尚未設定 origin 遠端。你仍可使用本地 Git 操作，但 fetch、pull、push 需要先設定遠端 URL。',
          inline: '未設定 origin，遠端同步動作已停用。',
        },
        status: {
          branch: '分支',
          noBranch: '尚無分支',
          sync: '同步狀態',
          aheadBehind: '領先 {{ahead}} / 落後 {{behind}}',
          changes: '變更',
          changeCounts: '暫存 {{staged}} · 未暫存 {{unstaged}} · 未追蹤 {{untracked}}',
          conflicts: '衝突',
          hasConflicts: '有衝突',
          noConflicts: '無衝突',
        },
        actions: {
          rebuild: '重建索引',
        },
        toasts: {
          loadFailed: {
            title: '載入 Git 資料失敗',
            description: '無法載入模板中心版本控制資料',
          },
          operationFailed: {
            title: 'Git 操作失敗',
            description: '無法完成 Git 操作',
          },
          commitSuccess: {
            title: '提交成功',
          },
          fetchSuccess: {
            title: 'Fetch 成功',
          },
          pullSuccess: {
            title: 'Pull 成功',
          },
          pushSuccess: {
            title: 'Push 成功',
          },
          checkoutSuccess: {
            title: '切換分支成功',
          },
          rebuildFailed: {
            title: '重建索引失敗',
            description: '無法啟動模板索引重建',
          },
        },
      },
    },
    settingsDialog: {
      title: '設定模板中心',
      description: '設定模板中心的同步來源與基本資訊。',
      git: {
        repositorySetup: {
          title: '倉庫設定',
          description: '將目前模板 registry 初始化為 Git，或將既有遠端 registry clone 到空的模板中心。',
          localContentWarning: '模板中心已有本地檔案。為避免覆蓋既有內容，已停用 clone；請改用初始化來保留並追蹤目前檔案。',
          cloneDisabledHelper: 'Clone 僅可用於沒有本地檔案的模板中心。若要保留目前檔案，請使用初始化。',
          initializedAlertTitle: 'Git 倉庫已初始化',
          actions: {
            init: '初始化倉庫',
            initializing: '初始化中...',
          },
        },
        remote: {
          title: '遠端倉庫',
          description: '設定現有 Git 倉庫的 origin，供 fetch、pull、push 使用。',
          urlLabel: 'Origin URL',
          helper: '此操作會更新倉庫 Git 設定中的 origin 遠端。',
          missingOrigin: '尚未設定 origin。請新增遠端 URL 以啟用 fetch、pull、push。',
          noBranch: '尚無分支',
          validation: {
            required: 'Origin URL 為必填',
          },
          actions: {
            save: '儲存遠端',
            saving: '儲存中...',
          },
        },
        userConfig: {
          title: 'Git 使用者資訊',
          description: '設定 Git 提交時使用的全域使用者名稱與 Email。',
          userNameLabel: 'Git 使用者名稱',
          userNamePlaceholder: '請輸入 Git 使用者名稱',
          userEmailLabel: 'Git 使用者 Email',
          userEmailPlaceholder: '請輸入 Git 使用者 Email',
          helper: '此設定會以 git config --global 儲存，影響所有工作區的 Git 提交紀錄。',
          validation: {
            required: 'Git 使用者名稱與 Email 皆為必填',
          },
          actions: {
            save: '儲存 Git 設定',
            saving: '儲存中...',
          },
        },
        cloneRepo: {
          title: 'Clone Git 倉庫',
          description: 'Clone 遠端 Git 倉庫到模板中心，或更新已存在的倉庫。',
          cloneProgressTitle: 'Clone 進度',
          successAlertTitle: '已成功 Clone 倉庫',
          remoteLabel: '遠端',
          branchStatusLabel: '分支',
          urlLabel: 'Git Repository URL',
          urlPlaceholder: '例如: git@github.com:username/repo.git 或 https://github.com/username/repo.git',
          branchLabel: '分支名稱（可選）',
          branchPlaceholder: '例如: main 或 develop（留空則使用預設分支）',
          branchHelper: '指定要 clone 的分支，留空則使用倉庫的預設分支。',
          helper: 'Clone 倉庫會將遠端內容下載到模板中心。如果已存在相同倉庫，則會執行更新操作。',
          actions: {
            clone: 'Clone Repos',
            cloning: 'Clone 中...',
          },
        },
        sshKeys: {
          title: 'SSH Keys 管理',
          description: '管理用於 Git 操作的 SSH 金鑰對。',
          publicKeyLabel: '公鑰',
          privateKeyLabel: '私鑰',
          fingerprintLabel: '指紋',
          lastRotatedLabel: '最後產生時間',
          showPrivateKey: '顯示私鑰',
          hidePrivateKey: '隱藏私鑰',
          notGenerated: '尚未產生',
          copy: '複製',
          copyToClipboard: '複製到剪貼簿',
          copied: '已複製',
          copiedDescription: '內容已複製到剪貼簿',
          copyFailed: '複製失敗',
          copyFailedDescription: '無法複製到剪貼簿',
          keepPrivateKeySafe: '⚠️ 請妥善保管私鑰，不要與他人分享',
          addPublicKeyToGit: '💡 將此公鑰新增到 Git 服務（GitHub、GitLab 等）的 SSH Keys 設定中',
          unsavedChanges: '⚠️ 您有未保存的變更',
          regenerateWarning: '⚠️ 重新產生將會覆蓋現有的 SSH Keys',
          actions: {
            generate: '產生 SSH Key Pair',
            regenerate: '重新產生 SSH Key Pair',
            generating: '產生中...',
            save: '儲存變更',
            saving: '儲存中...',
          },
          usageInstructions: {
            title: '使用說明',
            steps: [
              '點擊「產生 SSH Key Pair」按鈕產生金鑰對',
              '複製公鑰並新增到您的 Git 服務商（GitHub、GitLab 等）',
              '在基本設定中填入 Git Repository URL（使用 SSH 格式）',
              '即可使用 SSH 金鑰進行 Git 操作',
            ],
          },
          toasts: {
            loadFailed: {
              title: '載入失敗',
              description: '無法載入 SSH Keys',
            },
            generating: {
              title: '正在產生 SSH Key Pair...',
              description: '請稍候',
            },
            generateSuccess: {
              title: '成功',
              description: 'SSH Key Pair 已成功產生並儲存',
            },
            generateFailed: {
              title: '產生失敗',
              description: '無法產生 SSH Key Pair',
            },
            saveSuccess: {
              title: '儲存成功',
              description: 'SSH Keys 已成功更新',
            },
            saveFailed: {
              title: '儲存失敗',
              description: '無法儲存 SSH Keys',
            },
          },
        },
      },
      unknownError: '未知錯誤',
      actions: {
        back: '返回模板中心',
      },
      toasts: {
        commitSuccess: {
          title: '提交成功',
          description: '變更已成功提交並推送到遠端。',
        },
        commitFailed: {
          title: '提交失敗',
          description: '提交變更時發生錯誤：{{error}}',
        },
        pullSuccess: {
          title: '拉取成功',
          description: '已成功從遠端拉取最新變更。',
        },
        pullFailed: {
          title: '拉取失敗',
          description: '從遠端拉取變更時發生錯誤：{{error}}',
        },
        syncLocalToRemote: {
          title: '已啟動同步',
          description: '已使用本地設定同步至遠端儲存庫。',
        },
        syncRemoteToLocal: {
          title: '已啟動同步',
          description: '已以遠端儲存庫內容覆蓋本地設定。',
        },
        gitUserConfigSaved: {
          title: 'Git 使用者資訊已更新',
          description: '已成功更新 Git 使用者名稱與 Email。',
        },
        gitUserConfigFailed: {
          title: 'Git 使用者資訊更新失敗',
          description: '無法更新 Git 使用者資訊：{{error}}',
        },
        remoteUrlSaved: {
          title: '遠端 URL 已儲存',
          description: 'Origin 遠端已更新。',
        },
        remoteUrlFailed: {
          title: '遠端 URL 儲存失敗',
          description: '無法儲存遠端 URL：{{error}}',
        },
        initRepoSuccess: {
          title: '倉庫已初始化',
          description: '模板中心現在已由 Git 追蹤。',
        },
        initRepoFailed: {
          title: '倉庫初始化失敗',
          description: '無法初始化倉庫：{{error}}',
        },
        cloneRepoSuccess: {
          title: 'Clone 倉庫成功',
          description: '已成功 clone 或更新遠端倉庫。',
        },
        cloneRepoStarted: {
          title: 'Clone 任務已提交',
          description: '後台正在執行 clone 操作，請稍候...',
        },
        cloneRepoFailed: {
          title: 'Clone 倉庫失敗',
          description: '無法 clone 倉庫：{{error}}',
        },
        failed: {
          title: '操作失敗',
          description: '執行設定操作時發生錯誤，請稍後再試。',
        },
        rebuildStarted: {
          title: '重建任務已提交',
          description: '後台正在重建模板資料庫，請稍候...',
        },
        rebuildFailed: {
          title: '重建失敗',
          description: '{{error}}',
        },
        unknownError: '未知錯誤',
      },
    },
    createDialog: {
      title: '建立新模板',
      description: '請輸入模板代號（僅限英文、數字和連字號，使用 kebab-case 格式，例如：my-template）',
      nameLabel: '模板代號',
      placeholder: 'my-template',
      validation: {
        kebabCase: '請使用 kebab-case 格式，且必須以小寫英文字母開頭（例如：my-template）',
      },
      actions: {
        cancel: '取消',
        create: '建立',
        creating: '建立中...'
      },
      errors: {
        generic: '建立模板時發生錯誤，請稍後再試。',
        invalidPayload: '模板資料格式不正確，請檢查必填欄位。',
        unauthorized: '認證失敗，請重新登入後再試。',
        duplicate: '模板代號已存在，請使用其他代號。',
      },
    },
    toasts: {
      deleteSuccess: {
        title: '刪除成功',
        description: '模板「{{name}}」已刪除。',
      },
      deleteFailed: {
        title: '刪除失敗',
        description: '刪除模板時發生錯誤，請稍後再試。',
      },
      exportSuccess: {
        title: '匯出完成',
        description: '已匯出模板「{{name}}」。',
      },
      exportFailed: {
        title: '匯出失敗',
        description: '匯出模板時發生錯誤。',
      },
      importSuccess: {
        title: '匯入成功',
        description: '模板「{{name}}」已匯入。',
      },
      importFailed: {
        title: '匯入失敗',
        description: '無法匯入選擇的檔案。',
      },
      installSuccess: {
        title: '安裝完成',
        description: '模板「{{template}}」已安裝至 {{workspace}}。',
      },
      installFailed: {
        title: '安裝失敗',
        description: '安裝模板時發生錯誤，請稍後再試。',
      },
    },
    errors: {
      loadFailed: '無法載入範本資料',
      unsupportedImport: '目前僅支援 JSON 或 mwtemplate 檔案匯入。',
      invalidFileType: '請上傳 ZIP 格式的模板檔案。',
    },
    card: {
      features: {
        mcp: 'MCP',
        commands: 'Commands',
        hooks: 'Hooks',
        agentsMd: 'AGENTS.md',
        agents: 'Agents',
        outputStyle: 'Output Style',
        scripts: 'Scripts',
        skills: 'Skills',
      },
      actions: {
        edit: '編輯',
        export: '匯出',
        delete: '刪除',
        install: '安裝',
        exporting: '匯出中...',
      },
    },
    install: {
      title: '安裝 {{name}}',
      description: '選擇目標工作區與要包含的組件。',
      workspace: {
        label: '目標工作區',
        placeholder: '選擇工作區',
      },
      components: {
        label: '安裝內容',
        selectedCount: '{{selected}} / {{total}}',
      },
      options: {
        mcp: {
          label: 'MCP 服務',
          description: 'Model Context Protocol 服務器與連線設定',
        },
        commands: {
          label: 'Commands',
          description: '可安裝到不同 CLI 的命令與指令範本',
        },
        hooks: {
          label: 'Hooks',
          description: '事件觸發腳本與自動化流程',
        },
        agentsMd: {
          label: 'AGENTS.md',
          description: '主要規則文件與代理指引',
        },
        agents: {
          label: 'Agents',
          description: '代理角色、子代理與協作定義',
        },
        outputStyle: {
          label: 'Output Style',
          description: '輸出風格與格式偏好設定',
        },
        scripts: {
          label: '範本腳本',
          description: '隨附的腳本與資源',
        },
        skills: {
          label: 'Skills',
          description: 'Skills檔案與自訂行為定義',
        },
      },
      actions: {
        cancel: '取消',
        confirm: '安裝到 {{workspace}}',
      },
      preview: {
        title: '安裝預覽',
        summary: '{{files}} 檔案 / {{warnings}} 警告 / {{unsupported}} 不支援 / {{degradation}} 降級',
        target: '目標：{{target}}',
        loading: '載入編譯預覽中...',
        loadFailed: '無法載入安裝預覽',
        none: '此目標沒有額外警告或降級資訊。',
        sections: {
          warnings: '警告',
          unsupported: '不支援',
          degradation: '降級',
        },
      },
    },
    import: {
      title: '匯入模板',
      description: '上傳 .json 或 .mwtemplate 檔案以匯入模板設定。',
      selectedFile: '已選擇檔案：{{name}}',
      actions: {
        cancel: '取消',
        confirm: '匯入',
        importing: '匯入中...',
      },
    },
  },
  editor: {
    loading: '載入編輯器中...',
    creating: '建立模板中...',
    header: {
      create: '新增模板',
      edit: '編輯模板：{{name}}',
    },
    toolbar: {
      back: '返回',
      save: '儲存變更',
      saving: '儲存中...'
    },
    collection: {
      actions: {
        add: '新增',
      },
      itemTitle: '設定項目',
    },
    fileManagement: {
      collection: {
        actions: {
          add: '新增',
        },
        itemTitle: '設定項目',
      },
      header: {
        title: '檔案',
      },
      search: {
        placeholder: '搜尋檔案或資料夾',
        contentPlaceholder: '搜尋檔案名稱或內容...',
        button: '搜尋',
        clear: '清除搜尋',
        results: '找到 {{count}} 個結果',
      },
      labels: {
        file: '檔案',
        folder: '資料夾',
        root: '根目錄',
      },
      actions: {
        create: {
          trigger: '新增',
          upload: '上傳檔案',
          folder: '建立資料夾',
          file: '新增文字檔',
        },
        multiSelect: {
          enable: '多選',
          disable: '取消多選',
        },
        refresh: '重新整理',
        cancel: '取消',
        delete: '刪除',
      },
      sidebar: {
        createFile: '新增文字檔',
        createFolder: '建立資料夾',
        upload: '上傳檔案',
        refresh: '重新整理',
      },
      multiSelect: {
        summary: '已選擇 {{count}} 個項目',
        selectAll: '全選',
        unselectAll: '取消全選',
      },
      tree: {
        itemCount: '{{count}} 項目',
        selectedCount: '已選 {{count}} 個',
        empty: '目前沒有檔案，請透過右鍵或上方按鈕建立',
        filteredEmpty: '找不到符合條件的項目',
      },
      viewer: {
        emptyState: '請選擇一個檔案',
        noTemplate: '請先選擇或創建模板',
        noFile: '選擇一個檔案開始編輯',
      },
      editor: {
        actions: {
          save: '儲存',
          cancel: '取消',
          edit: '編輯',
          copy: '複製',
          download: '下載',
        },
        markdownPlaceholder: '請輸入 Markdown 內容...',
      },
      contextMenu: {
        upload: '上傳檔案',
        createFolder: '建立資料夾',
        createFile: '新增文字檔',
        copy: '複製',
        paste: '貼上',
        rename: '重新命名',
        delete: '刪除',
        deleteMultiple: '刪除 {{count}} 個項目',
      },
      dialogs: {
        createFolder: {
          title: '建立資料夾',
          placeholder: '資料夾名稱',
          confirm: '建立',
        },
        createFile: {
          title: '新增文字檔',
          placeholder: '檔案名稱',
          confirm: '建立',
        },
        rename: {
          title: '重新命名',
          placeholder: '新名稱',
          confirm: '重新命名',
        },
        delete: {
          title: '確認刪除',
          description: '確定要刪除「{{name}}」嗎？',
          folderExtra: '此操作將刪除資料夾及其所有內容。',
          confirm: '刪除',
        },
      },
      toasts: {
        loadFailed: {
          title: '載入失敗',
          description: '無法載入檔案列表',
        },
        save: {
          success: {
            title: '儲存成功',
            description: '已儲存「{{name}}」',
          },
          error: {
            title: '儲存失敗',
            description: '無法儲存檔案',
          },
        },
        copyContent: {
          success: {
            title: '已複製',
            description: '檔案內容已複製到剪貼簿',
          },
        },
        create: {
          success: {
            title: '建立成功',
            description: '已建立{{type}}「{{name}}」',
          },
          error: {
            title: '建立失敗',
            description: '無法建立{{type}}，請稍後再試。',
          },
        },
        rename: {
          success: {
            title: '重新命名成功',
            description: '已將「{{oldName}}」重新命名為「{{newName}}」',
          },
          error: {
            title: '重新命名失敗',
            description: '無法重新命名「{{name}}」，請稍後再試。',
          },
        },
        delete: {
          success: {
            title: '刪除成功',
            description: '已刪除「{{name}}」',
          },
          error: {
            title: '刪除失敗',
            description: '無法刪除「{{name}}」，請稍後再試。',
          },
        },
        batchDelete: {
          success: {
            title: '批次刪除成功',
            description: '已成功刪除 {{count}} 個項目',
          },
          partial: {
            title: '部分刪除成功',
            description: '已刪除 {{succeeded}} / {{total}} 個項目',
          },
          error: {
            title: '批次刪除失敗',
            description: '無法刪除選取的項目，請稍後再試。',
          },
        },
        upload: {
          success: {
            title: '上傳成功',
            description: '已上傳 {{count}} 個檔案',
          },
          error: {
            title: '上傳失敗',
            description: '無法上傳檔案，請稍後再試。',
          },
        },
        copy: {
          success: {
            title: '複製成功',
            description: '已複製「{{name}}」到「{{path}}」',
          },
          error: {
            title: '複製失敗',
            description: '無法複製「{{name}}」，請稍後再試。',
          },
        },
        paste: {
          error: {
            title: '貼上失敗',
            description: '貼上失敗，請稍後再試',
          },
        },
        move: {
          success: {
            title: '移動成功',
            description: '已移動「{{name}}」到「{{target}}」',
          },
          error: {
            title: '移動失敗',
            description: '無法移動檔案',
          },
        },
        nodeCopy: {
          success: {
            title: '已複製',
            description: '已複製「{{name}}」',
          },
        },
      },
    },
    toasts: {
      invalid: {
        title: '資料未完成',
        description: '請先填寫所有必填欄位。',
      },
      createSuccess: {
        title: '建立成功',
        description: '模板「{{name}}」已建立。',
      },
      createFailed: {
        title: '建立失敗',
        description: '無法建立模板，請稍後再試。',
      },
      updateSuccess: {
        title: '更新成功',
        description: '模板「{{name}}」已更新。',
      },
      saveFailed: {
        title: '儲存失敗',
        description: '請稍後再試。',
      },
      saveSuccess: {
        title: '儲存成功',
        description: '變更已儲存。',
      },
      deleteSuccess: {
        title: '刪除成功',
        description: '項目已刪除。',
      },
      deleteFailed: {
        title: '刪除失敗',
        description: '無法刪除項目，請稍後再試。',
      },
      error: {
        title: '錯誤',
        description: '缺少模板資訊，請重新整理後再試。',
      },
    },
    tabs: {
      basic: '基本資訊',
      agentsMd: 'AGENTS.md',
      hooks: 'Hooks',
      mcp: 'MCP',
      agents: 'Agents',
      commands: 'Commands',
      outputStyle: 'Output Style',
      skills: 'Skills',
      scripts: 'Scripts',
      docs: 'Docs',
    },
    docs: {
      actions: {
        save: '儲存',
        saving: '儲存中...',
      },
    },
    basicInfo: {
      fields: {
        templateId: {
          label: '模板代號',
          placeholder: '例如 java-unittest',
          hint: 'kebab-case 格式，只能使用小寫英文、數字和連字號，建立後無法修改',
        },
        name: {
          label: '模板名稱',
          placeholder: '輸入模板名稱（可使用中文）',
        },
        version: {
          label: '版本',
          placeholder: '例如 1.0.0',
        },
        author: {
          name: {
            label: '作者名稱',
            placeholder: '輸入作者名稱',
          },
          email: {
            label: '作者電子郵件',
            placeholder: 'author@example.com',
          },
          url: {
            label: '作者網址',
            placeholder: 'https://github.com/author',
          },
        },
        description: {
          label: '描述',
          placeholder: '描述模板的核心用途與適用場景',
        },
        category: {
          label: '分類',
          placeholder: '選擇模板分類',
        },
        initCommands: {
          label: '初始化指令',
          placeholder: '輸入 bash 指令（多行）\n例如：\nnpm install\nnpm run build',
          hint: '這些指令將在模板安裝時自動執行，可用於安裝依賴、初始化環境等。',
        },
        keywords: {
          label: '關鍵字',
          placeholder: '輸入關鍵字後按 Enter',
          remove: '移除',
          add: '新增關鍵字',
        },
      },
    },
    mcp: {
      empty: {
        title: '尚未建立任何 MCP 服務',
        description: '請建立新的 MCP 服務來擴充功能。',
      },
      actions: {
        add: '新增 MCP 服務',
      },
      card: {
        nameFallback: 'MCP 伺服器',
        actions: {
          copyTooltip: '複製設定',
          showEnvValues: '顯示環境變數值',
          hideEnvValues: '隱藏環境變數值',
        },
        toast: {
          title: '設定已複製',
          description: 'MCP 伺服器「{{name}}」的設定已複製到剪貼簿。',
        },
        sections: {
          headers: 'HTTP 標頭',
          command: {
            urlLabel: 'URL',
            commandLabel: '命令',
            args: '參數：{{args}}',
          },
          environment: {
            title: '環境變數',
          },
        },
      },
      dialog: {
        title: {
          create: '新增 MCP 伺服器',
          edit: '編輯 MCP 伺服器',
        },
        description: {
          create: '設定新的 Model Context Protocol 伺服器。',
          edit: '修改 MCP 伺服器設定。',
        },
        actions: {
          create: '新增',
          save: '儲存變更',
        },
        validation: {
          nameRequired: '伺服器名稱為必填項。',
          descriptionRequired: '描述為必填項。',
          commandRequired: 'Stdio 傳輸需填寫執行命令。',
          urlRequired: 'HTTP 或 SSE 傳輸需填寫伺服器 URL。',
          urlInvalid: '請輸入有效的 URL。',
          saveFailed: '儲存失敗',
        },
        transport: {
          label: '傳輸類型 *',
          placeholder: '選擇傳輸方式',
          options: {
            stdio: {
              label: 'Stdio（標準輸入/輸出）',
              description: '透過命令列執行。',
            },
            http: {
              label: 'HTTP（HTTP API）',
              description: '透過 HTTP/HTTPS 端點連線。',
            },
            sse: {
              label: 'SSE（伺服器推播事件）',
              description: '透過 SSE 端點串流事件。',
            },
          },
        },
        fields: {
          name: {
            label: '伺服器名稱 *',
            placeholder: '輸入伺服器名稱',
          },
          description: {
            label: '描述 *',
            placeholder: '輸入伺服器描述',
          },
          command: {
            label: '執行命令 *',
            placeholder: '例如：python -m my_mcp_server',
          },
          url: {
            label: '伺服器 URL *',
            placeholderHttp: '例如：https://api.example.com/mcp',
            placeholderSse: '例如：https://api.example.com/sse',
            hintHttp: '完整的 HTTP/HTTPS 端點。',
            hintSse: '完整的 SSE 端點網址。',
          },
          args: {
            label: '命令參數',
            add: '新增參數',
            placeholder: '參數 {{index}}',
            empty: '沒有命令參數',
          },
          env: {
            label: '環境變數',
            add: '新增變數',
            keyPlaceholder: '變數名稱',
            valuePlaceholder: '變數值',
            empty: '沒有環境變數',
          },
          headers: {
            label: 'HTTP 標頭',
            add: '新增標頭',
            keyPlaceholder: '標頭名稱',
            valuePlaceholder: '標頭值',
            empty: '沒有 HTTP 標頭',
            hint: '用於 HTTP/SSE 連線的標頭，如 Authorization、Content-Type 等。',
          },
        },
      },
    },
    commands: {
      sidebar: {
        title: 'Commands',
        searchPlaceholder: '搜尋…',
        empty: '尚未找到符合條件的項目。',
      },
      empty: {
        title: '尚未建立任何 Command',
        description: '請建立新的指令來管理 Claude 的行為。',
      },
      actions: {
        add: '新增 Command',
        copy: '複製內容',
        download: '下載',
        edit: '編輯',
        delete: '刪除',
      },
      list: {
        sizeLabel: '大小：{{size}}',
      },
      logs: {
        copyFailed: '無法複製到剪貼簿：',
      },
      detail: {
        descriptionFallback: '尚未提供描述。',
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
        validation: {
          nameRequired: '請輸入命令名稱。',
          contentRequired: '內容不可為空。',
        },
        actions: {
          create: '建立項目',
          save: '儲存變更',
        },
        fields: {
          name: {
            label: '命令名稱 *',
            placeholder: '輸入命令名稱',
            helper: '命令名稱需唯一，建議使用英文與連字號。',
          },
          namespace: {
            label: '命名空間',
            placeholder: '輸入命名空間（可選）',
            helper: '用於組織相關的命令。',
          },
          content: {
            label: '指令內容 *',
            sizeHint: '預估大小：{{size}}',
          },
        },
      },
    },
    hooks: {
      empty: {
        title: '尚未建立任何 Hook',
        description: '請建立 Hook 以便在事件觸發時執行自動化流程。',
      },
      actions: {
        add: '新增 Hook',
        remove: '移除',
        editTooltip: '編輯 {{event}} 事件 Hook',
        deleteTooltip: '刪除 {{event}} 事件 Hook',
        editSrLabel: '編輯 Hook',
        deleteSrLabel: '刪除 Hook',
      },
      card: {
        nameFallback: '未命名 Hook',
        triggerLabel: '觸發事件:',
        matchersCount: '{{count}} 個匹配器',
        rulesCount: '{{count}} 個匹配器',
        matcherLabel: '匹配器:',
        actionsCount: '{{count}} 個執行動作',
        moreActions: '還有 {{count}} 個執行動作…',
        eventLabel: '事件',
        matchersAndActions: 'Hook 匹配器與執行動作',
        matcherNumber: '匹配器 {{number}}',
        execution: {
          type: {
            command: '命令',
            script: '指令碼',
            undefined: '未知類型',
          },
          empty: '無內容',
        },
        matchers: {
          title: '匹配器與執行動作',
          matcherLabel: '匹配器',
          actionsCount: '{{count}} 個執行動作',
          commandLabel: '命令',
          noCommand: '無內容',
          moreActions: '還有 {{count}} 個執行動作…',
          summary: {
            matchers: '{{count}} 個匹配器',
            commands: '{{count}} 個命令',
          },
        },
        summary: {
          matchers: '{{count}} 個匹配器',
          actions: '{{count}} 個動作',
          commands: '{{count}} 個命令',
          events: '{{count}} 個事件',
        },
        stats: {
          events: '{{count}} 個事件',
        },
        scope: {
          project: '專案',
        },
        actions: {
          editTooltip: '編輯 {{event}} 事件 Hook',
          deleteTooltip: '刪除 {{event}} 事件 Hook',
          editSrLabel: '編輯 Hook',
          deleteSrLabel: '刪除 Hook',
          remove: '移除',
        },
      },
      dialog: {
        title: {
          create: '新增 Hook',
          edit: '編輯 Hook',
          editMerged: '編輯事件 Hook',
        },
        description: '設定 Hook 的觸發事件與執行命令。',
        'description.merged': '編輯該事件下的所有 Hook 規則。您可以修改、新增或刪除匹配器配置。',
        actions: {
          create: '新增 Hook',
          save: '儲存變更',
        },
        validation: {
          missingExecution: '每個規則至少需要一個有效的執行命令。',
          duplicateEvent: '此事件類型已經存在，請編輯現有的 Hook 或選擇其他事件類型。',
          duplicateEventWarning: '檢測到重複的事件類型',
          duplicateEventSuggestion: '建議編輯現有的 Hook 而不是建立重複的事件。',
        },
        fields: {
          name: {
            label: 'Hook 名稱 *',
            placeholder: '輸入 Hook 名稱',
          },
          event: {
            label: '事件類型 *',
            placeholder: '選擇事件',
          },
        },
        matchers: {
          title: '匹配器配置',
          add: '新增匹配器',
          patternLabel: '匹配模式',
          patternPlaceholder: '工具名稱模式（如：Write|Edit 或 *）',
          patternHelp: {
            overview: '用於匹配工具名稱（區分大小寫，僅適用於 PostToolUse）。',
            literal: '• 簡單字串：Write 僅匹配 Write 工具。',
            regex: '• 正規表達式：Edit|Write 或 Notebook.*',
            wildcard: '• * 可匹配所有工具，也可留空。',
          },
        },
        executions: {
          title: 'Hook 執行配置',
          add: '新增 Hook',
          timeoutLabel: '超時時間（秒）',
          timeoutPlaceholder: '30',
          timeoutHelp: '命令執行的最長時間，超過將中止。',
          commandLabel: '命令 *',
          commandPlaceholder: '輸入要執行的命令',
          commandHelp: '可使用環境變數，例如 $CLAUDE_PROJECT_DIR。',
          remove: '移除 Hook',
        },
      },
      events: {
        preToolUse: {
          label: 'PreToolUse：在工具呼叫之前執行（可以阻止它們）',
          description: '在工具呼叫之前執行，可阻止執行。',
        },
        postToolUse: {
          label: 'PostToolUse：在工具呼叫完成後執行',
          description: '在工具呼叫完成後執行。',
        },
        userPromptSubmit: {
          label: 'UserPromptSubmit：當使用者提交提示時執行，在 Claude 處理之前',
          description: '使用者提交提示後、Claude 處理之前執行。',
        },
        notification: {
          label: 'Notification：當 Claude Code 發送通知時執行',
          description: '當 Claude Code 發送通知時執行。',
        },
        stop: {
          label: 'Stop：當 Claude Code 完成回應時執行',
          description: '當 Claude Code 完成回應時執行。',
        },
        subagentStop: {
          label: 'SubagentStop：當子代理任務完成時執行',
          description: '當子代理任務完成時執行。',
        },
        preCompact: {
          label: 'PreCompact：在 Claude Code 即將執行壓縮操作之前執行',
          description: '在 Claude Code 執行壓縮操作前執行。',
        },
        sessionStart: {
          label: 'SessionStart：當 Claude Code 開始新會話或恢復現有會話時執行',
          description: '當工作階段開始或恢復時執行。',
        },
        sessionEnd: {
          label: 'SessionEnd：當 Claude Code 會話結束時執行',
          description: '當工作階段結束時執行。',
        },
      },
    },
    agents: {
      sidebar: {
        title: 'Agents 管理',
        searchPlaceholder: '搜尋 Agents…',
        empty: '目前沒有符合條件的項目',
      },
      actions: {
        add: '新增 Agent',
        copy: '複製內容',
        download: '下載',
        edit: '編輯',
        delete: '刪除',
      },
      list: {
        sizeLabel: '大小：{{size}}',
      },
      detail: {
        nameFallback: '未命名 Agent',
        descriptionFallback: '尚未提供描述。',
      },
      empty: {
        title: '尚未建立任何 Agent',
        description: '新增代理以擴充模板能力。',
      },
      logs: {
        copyFailed: '複製 Agent 內容失敗：',
      },
      toasts: {
        copySuccess: {
          title: '內容已複製',
          description: 'Agent「{{name}}」內容已複製到剪貼簿。',
        },
        copyFailed: {
          title: '複製失敗',
          description: '無法複製 Agent 內容，請稍後再試。',
        },
        downloadSuccess: {
          title: '開始下載',
          description: '正在下載 Agent「{{name}}」為 Markdown 檔案。',
        },
        createSuccess: {
          title: '建立成功',
          description: 'Agent「{{name}}」已建立。',
        },
        updateSuccess: {
          title: '更新成功',
          description: 'Agent「{{name}}」已更新。',
        },
        deleteSuccess: {
          title: '刪除成功',
          description: 'Agent「{{name}}」已刪除。',
        },
      },
      dialog: {
        title: {
          create: '新增 Agent',
          edit: '編輯 Agent',
        },
        description: {
          create: '建立新的 Agent 與主流程協作。',
          edit: '更新此 Agent 的檔名與內容。',
        },
        fields: {
          fileName: {
            label: '檔案名稱 *',
            placeholder: '輸入檔案名稱，例如 data-analyst.md',
            helper: '請使用能代表角色或專業領域的名稱。',
          },
          content: {
            label: 'Agent 內容 *',
            sizeHint: '預估大小：{{size}}',
            helper: '描述此 Agent 的行為、工具與專長。',
          },
        },
        validation: {
          fileName: '請輸入檔案名稱。',
          content: '內容不可為空。',
        },
        actions: {
          create: '建立 Agent',
          save: '儲存變更',
        },
      },
    },
    outputStyle: {
      sidebar: {
        title: 'Output Style 管理',
        searchPlaceholder: '搜尋 Output Style…',
        empty: '目前沒有符合條件的項目',
      },
      actions: {
        add: '新增 Output Style',
        copy: '複製內容',
        download: '下載',
        edit: '編輯',
        delete: '刪除',
      },
      list: {
        sizeLabel: '大小：{{size}}',
        nameFallback: '未命名 Output Style',
      },
      detail: {
        descriptionFallback: '尚未提供描述。',
      },
      empty: {
        title: '尚未建立任何 Output Style',
        description: '新增輸出樣式以自訂 AI 回應格式。',
      },
      logs: {
        copyFailed: '複製 Output Style 內容失敗：',
      },
      toasts: {
        copySuccess: {
          title: '內容已複製',
          description: 'Output Style「{{name}}」內容已複製到剪貼簿。',
        },
        copyFailed: {
          title: '複製失敗',
          description: '無法複製 Output Style 內容，請稍後再試。',
        },
        downloadSuccess: {
          title: '開始下載',
          description: '正在下載 Output Style「{{name}}」為 Markdown 檔案。',
        },
      },
      errors: {
        copyFailed: '複製 Output Style 內容失敗',
      },
      dialog: {
        title: {
          create: '新增 Output Style',
          edit: '編輯 Output Style',
        },
        description: {
          create: '建立新的 Output Style 以自訂 AI 回應格式。',
          edit: '更新此 Output Style 的檔名與內容。',
        },
        fields: {
          fileName: {
            label: '檔案名稱 *',
            placeholder: '輸入檔案名稱，例如 concise-format.md',
            helper: '請使用能代表輸出樣式的名稱。',
          },
          content: {
            label: 'Output Style 內容 *',
            sizeHint: '預估大小：{{size}}',
            helper: '描述此 Output Style 的格式與規則。',
          },
        },
        validation: {
          fileName: '請輸入檔案名稱。',
          content: '內容不可為空。',
        },
        actions: {
          cancel: '取消',
          create: '建立 Output Style',
          update: '更新',
          submitting: '處理中...',
        },
      },
    },
    agentsMd: {
      editor: {
        placeholder: '編輯 AGENTS.md 內容－主要規則文件與代理指引（支援 Markdown）。',
      },
      status: {
        loading: '載入中...',
        saving: '儲存中...',
        error: '錯誤',
        retry: '重試',
      },
      actions: {
        retry: '重試',
      },
      toasts: {
        loadFailed: {
          title: '載入失敗',
          description: '無法載入 AGENTS.md 內容。',
        },
        saveSuccess: {
          title: '儲存成功',
          description: 'AGENTS.md 內容已更新。',
        },
        saveFailed: {
          title: '儲存失敗',
          description: '無法儲存 AGENTS.md 內容。',
        },
      },
      errors: {
        loadFailed: '無法載入 AGENTS.md 內容，請稍後再試。',
        saveFailed: '無法儲存 AGENTS.md 內容，請稍後再試。',
      },
    },
    files: {
      loading: '載入腳本中…',
      header: {
        title: '腳本',
        badge: '共 {{count}} 個腳本',
      },
      actions: {
        add: '新增',
        addTooltip: '新增腳本',
        copyTooltip: '複製腳本內容',
        downloadTooltip: '下載腳本',
        cancelEditTooltip: '取消編輯',
      },
      filters: {
        searchPlaceholder: '搜尋腳本…',
        types: {
          all: '全部',
          files: '腳本',
          folders: '資料夾',
        },
      },
      tree: {
        empty: '尚未新增腳本',
        deleteTooltip: '刪除腳本',
      },
      resize: {
        label: '拖曳以調整面板寬度',
      },
      detail: {
        titleFallback: '腳本內容',
        editorPlaceholder: '輸入腳本內容…',
        emptyFile: '腳本內容為空',
        folderHint: '這是一個目錄',
        emptySelection: '選擇腳本以查看內容',
      },
      logs: {
        loadFailed: '載入腳本假資料失敗：',
        copyFailed: '複製腳本內容失敗：',
        saveFailed: '儲存腳本失敗：',
        createFailed: '建立腳本失敗：',
        deleteFailed: '刪除腳本失敗：',
      },
      toasts: {
        loadFailed: {
          title: '載入失敗',
          description: '無法載入腳本列表。',
        },
        copySuccess: {
          title: '內容已複製',
          description: '腳本「{{name}}」內容已複製到剪貼簿。',
        },
        copyFailed: {
          title: '複製失敗',
          description: '無法複製腳本內容，請稍後再試。',
        },
        downloadSuccess: {
          title: '開始下載',
          description: '正在下載「{{name}}」至裝置。',
        },
        saveSuccess: {
          title: '儲存成功',
          description: '腳本內容已更新。',
        },
        saveFailed: {
          title: '儲存失敗',
          description: '無法儲存腳本內容。',
        },
        createSuccess: {
          title: '建立成功',
          description: '{{type}}已建立。',
        },
        createFailed: {
          title: '建立失敗',
          description: '無法建立{{type}}。',
        },
        deleteSuccess: {
          title: '刪除成功',
          description: '腳本已刪除。',
        },
        deleteFailed: {
          title: '刪除失敗',
          description: '無法刪除腳本。',
        },
      },
      dialog: {
        title: '建立腳本',
        description: '建立新的腳本或目錄。',
        typeLabel: '類型',
        typeOptions: {
          file: '腳本',
          directory: '目錄',
        },
        nameLabel: '名稱',
        namePlaceholder: {
          file: '腳本名稱（例如：script.sh）',
          directory: '目錄名稱',
        },
        actions: {
          create: '建立',
        },
      },
    },
    validation: {
      required: '必填',
      select: '請選擇一項',
      commandName: '命令名稱為必填',
      commandContent: '指令內容為必填',
      hookName: 'Hook 名稱為必填',
      hookEvent: '觸發事件為必填',
      agentFile: '檔名必填',
      agentContent: '內容必填',
      filePath: '腳本路徑必填',
    },
  },
  detail: {
    loading: '載入模板詳細資訊...',
    notFound: '找不到指定的模板。',
    actions: {
      backToCenter: '返回模板中心',
      back: '返回',
      edit: '編輯',
      goToInstall: '前往安裝',
    },
    header: {
      version: '版本 {{version}}',
      author: '作者 {{author}}',
      category: '分類 {{category}}',
    },
    tabs: {
      basicInfo: '基本資訊',
      agentsMd: 'AGENTS.md',
      hooks: 'Hooks',
      mcp: 'MCP',
      agents: 'Agents',
      commands: 'Commands',
      outputStyle: 'Output Style',
      skills: 'Skills',
      scripts: 'Scripts',
      targetPreview: 'Target Preview',
    },
    targetPreview: {
      description: '檢視模板編譯到不同目標 CLI 的輸出檔案與降級資訊。',
      targetLabel: '目標 CLI',
      loading: '載入編譯預覽中...',
      emptyFiles: '此目標目前沒有可輸出的檔案。',
      sections: {
        files: '編譯輸出',
        warnings: '警告',
        unsupported: '不支援',
        degradation: '降級',
      },
      file: {
        sourceLabel: '來源',
        contentPreviewLabel: '內容預覽',
      },
      states: {
        none: '目前沒有項目。',
      },
      errors: {
        loadFailed: '無法載入目標編譯預覽，請稍後再試。',
      },
    },
    fileViewer: {
      loading: '載入檔案列表…',
      loadingContent: '載入檔案內容…',
      searchPlaceholder: '搜尋檔案或資料夾',
      empty: '目前沒有檔案',
      emptySearch: '找不到符合條件的檔案或資料夾',
      noSelection: '請選擇檔案以檢視內容',
      actions: {
        refresh: '重新整理',
      },
      errors: {
        loadTree: '無法載入檔案列表，請稍後再試。',
      },
    },
    sidebar: {
      info: {
        title: '模板資訊',
        categoryLabel: '分類',
        versionLabel: '版本',
      },
      features: {
        title: '功能項',
      },
      keywords: {
        title: '關鍵字',
      },
    },
    basicInfo: {
      title: '基本資訊',
      description: '查看模板的詳細資訊與統計數據',
      sections: {
        general: {
          title: '一般資訊',
          description: '模板的基本識別資訊',
        },
        author: {
          title: '作者資訊',
          description: '模板創建者的相關資訊',
        },
        keywords: {
          title: '關鍵字標籤',
          description: '用於搜尋與分類的關鍵字',
        },
        features: {
          title: '功能統計',
          description: '模板包含的各項功能數量',
        },
        timestamps: {
          title: '時間資訊',
          description: '模板的創建與更新時間',
        },
      },
      fields: {
        name: '模板名稱',
        templateId: '模板 ID',
        version: '版本號',
        cliType: 'CLI 類型',
        category: '分類',
        description: '描述',
        noDescription: '尚未提供描述',
        initCommands: '初始化指令',
        authorName: '作者姓名',
        authorEmail: '作者郵箱',
        noKeywords: '尚未設定關鍵字',
        createdAt: '創建時間',
        updatedAt: '更新時間',
      },
      stats: {
        mcpServers: 'MCP 伺服器',
        commands: 'Commands',
        hooks: 'Hooks',
        agents: 'Agents',
        agentsMd: 'AGENTS.md',
        scripts: '腳本檔案',
      },
    },
    mcp: {
      downloadFileName: 'mcp-servers.json',
      header: {
        title: 'MCP 伺服器配置',
        description: '管理範本串接的 Model Context Protocol 伺服器。',
      },
      badge: '{{count}} 個 MCP 伺服器',
      empty: {
        title: '尚未配置 MCP 伺服器',
        description: '此範本尚未設定任何 MCP 伺服器。',
      },
      actions: {
        download: '下載配置',
      },
      toasts: {
        copySuccess: {
          title: '配置已複製',
          description: 'MCP 伺服器「{{name}}」的設定已複製到剪貼簿。',
        },
        downloadSuccess: {
          title: '配置已下載',
          description: 'MCP 伺服器配置已下載為 JSON 檔案。',
        },
      },
      card: {
        transport: '傳輸類型:',
        url: '伺服器 URL:',
        command: '執行命令:',
        args: '命令參數:',
        env: '環境變數:',
        copyTooltip: '複製配置',
        toast: {
          title: '設定已複製',
          description: 'MCP 伺服器「{{name}}」的設定已複製到剪貼簿。',
        },
        sections: {
          url: 'URL',
          command: '命令',
          env: '環境變數',
        },
      },
    },
    hooks: {
      downloadFileName: 'hooks-config.json',
      header: {
        title: 'Hook 配置',
        description: '管理自動化 Hook、觸發事件與執行命令。',
      },
      badge: '{{count}} 個 Hook',
      actions: {
        download: '下載配置',
        copyTooltip: '複製配置',
      },
      empty: {
        title: '尚未配置 Hook',
        description: '此範本尚未設定任何 Hook。',
      },
      toasts: {
        downloadSuccess: {
          title: '配置已下載',
          description: 'Hook 配置已下載為 JSON 檔案。',
        },
        copySuccess: {
          title: '配置已複製',
          description: 'Hook「{{name}}」的設定已複製到剪貼簿。',
        },
      },
      events: {
        postToolUse: '工具執行後',
        preToolUse: '工具執行前',
        notification: '通知事件',
        sessionStart: '工作階段開始',
        stop: '工作階段停止',
      },
      matchers: {
        title: '匹配器配置',
        matchLabel: '匹配:',
        actionsCount: '{{count}} 個執行動作',
        commandLabel: '命令',
        emptyCommand: '無內容',
        moreActions: '還有 {{count}} 個執行動作…',
      },
      summary: {
        matchers: '{{count}} 個匹配器',
        actions: '{{count}} 個動作',
      },
    },
    agentsMd: {
      downloadFileName: 'AGENTS.md',
      header: {
        title: 'AGENTS.md 配置',
        description: '範本的全域指令與行為設定檔案。',
      },
      status: {
        configured: '已配置',
        missing: '未配置',
        loading: '載入中...',
        saving: '儲存中...',
        error: '錯誤',
      },
      empty: {
        title: '尚未配置 AGENTS.md',
        description: '此範本尚未包含任何 AGENTS.md 設定檔。',
      },
      actions: {
        copy: '複製',
        download: '下載',
        edit: '編輯',
        create: '建立 AGENTS.md',
        copySuccess: {
          title: '複製成功',
          description: 'AGENTS.md 內容已複製到剪貼簿。',
        },
        copyFailed: {
          title: '複製失敗',
          description: '無法複製 AGENTS.md 內容。',
        },
        downloadSuccess: {
          title: '下載成功',
          description: 'AGENTS.md 已下載為 Markdown 檔案。',
        },
      },
      toasts: {
        copySuccess: {
          title: '複製成功',
          description: 'AGENTS.md 內容已複製到剪貼簿。',
        },
        copyFailed: {
          title: '複製失敗',
          description: '無法複製 AGENTS.md 內容。',
        },
        downloadSuccess: {
          title: '下載成功',
          description: 'AGENTS.md 已下載為 Markdown 檔案。',
        },
      },
    },
    agents: {
      accessibility: {
        collapseSidebar: '收合左欄',
      },
      sidebar: {
        title: 'Agents',
        searchPlaceholder: '搜尋...',
        empty: '尚未找到符合條件的 Agent',
      },
      actions: {
        copy: '複製內容',
        download: '下載',
      },
      list: {
        sizeLabel: '大小：{{size}}',
        nameFallback: '未命名 Agent',
      },
      detail: {
        descriptionFallback: '尚未提供描述。',
        noContent: '無內容',
      },
      empty: {
        title: '尚未建立任何 Agent',
        description: '請從左側選擇或建立新的 Agent。',
      },
      errors: {
        copyFailed: '複製 Agent 內容失敗',
      },
      toasts: {
        copySuccess: {
          title: '內容已複製',
          description: 'Agent 內容已複製到剪貼簿。',
        },
        downloadSuccess: {
          title: '開始下載',
          description: '正在下載 Agent 為 Markdown 檔案。',
        },
      },
    },
    outputStyle: {
      accessibility: {
        collapseSidebar: '收合左欄',
      },
      sidebar: {
        title: 'Output Style',
        searchPlaceholder: '搜尋...',
        empty: '尚未找到符合條件的 Output Style',
      },
      actions: {
        copy: '複製內容',
        download: '下載',
      },
      list: {
        sizeLabel: '大小：{{size}}',
        nameFallback: '未命名 Output Style',
      },
      detail: {
        descriptionFallback: '尚未提供描述。',
        noContent: '無內容',
      },
      empty: {
        title: '尚未建立任何 Output Style',
        description: '請從左側選擇或建立新的 Output Style。',
      },
      errors: {
        copyFailed: '複製 Output Style 內容失敗',
      },
      toasts: {
        copySuccess: {
          title: '內容已複製',
          description: 'Output Style 內容已複製到剪貼簿。',
        },
        downloadSuccess: {
          title: '開始下載',
          description: '正在下載 Output Style 為 Markdown 檔案。',
        },
      },
    },
    commands: {
      accessibility: {
        collapseSidebar: '收合左欄',
      },
      sidebar: {
        title: 'Commands',
        searchPlaceholder: '搜尋...',
        empty: '尚未找到符合條件的項目',
        scopeLabel: '範圍',
        scopes: {
          all: '所有範圍',
          project: '專案',
          user: '個人',
          local: '本地',
        },
      },
      actions: {
        copy: '複製內容',
        download: '下載',
      },
      list: {
        sizeLabel: '大小：{{size}}',
        nameFallback: '未命名指令',
      },
      detail: {
        descriptionFallback: '尚未提供描述。',
      },
      empty: {
        title: '尚未建立任何 Command',
        description: '請從左側選擇或建立新的指令來管理 Claude 的行為。',
      },
      errors: {
        copyFailed: '無法複製到剪貼簿',
      },
    },
    files: {
      sidebar: {
        title: '檔案',
        searchPlaceholder: '搜尋腳本路徑或名稱...',
        empty: '尚無檔案',
      },
      actions: {
        copy: '複製',
        download: '下載',
      },
      detail: {
        noContent: '此檔案無內容',
        selectPrompt: '請從左側選擇檔案以檢視內容',
      },
      errors: {
        copyFailed: '複製腳本內容失敗',
      },
    },
  },
  errors: {
    templateNotFound: '找不到指定的模板',
    workspaceNotFound: '找不到指定的工作區',
  },
  common: {
    uncategorized: '未分類',
    targets: {
      claudeCode: 'Claude Code',
      codex: 'Codex',
      gemini: 'Gemini',
      opencode: 'OpenCode',
    },
    features: {
      mcp: 'MCP',
      commands: 'Commands',
      hooks: 'Hooks',
      agentsMd: 'AGENTS.md',
      agents: 'Agents',
      outputStyle: 'Output Style',
      scripts: 'Scripts',
      skills: 'Skills',
    },
  },
};

export default template;
