const pages = {
  auth: {
    login: {
      title: '登入 Aileron',
      description: '使用組織的身分提供者單一登入。',
      footer: {
        noAccount: '還沒有帳號？',
        register: '註冊',
      },
      error: {
        title: '登入失敗',
        providerFailed: '身分提供者登入失敗',
        configurationInvalid: '登入設定無效，請聯絡管理員。',
        sessionExpired: '登入要求已過期，請重新嘗試。',
      },
      button: {
        signIn: '使用組織帳號登入',
        redirecting: '正在重新導向至身分提供者...',
      },
      hint: '點擊上方按鈕將重新導向至組織的身分提供者進行安全登入。',
    },
    register: {
      title: '註冊 Aileron',
      description: '透過組織的身分提供者建立帳號。',
      footer: {
        hasAccount: '已有帳號？',
        login: '登入',
      },
      error: {
        title: '註冊失敗',
        registerFailed: '註冊失敗',
        providerUnavailable: '帳號註冊由您的組織管理。',
        configurationInvalid: '註冊設定無效，請聯絡管理員。',
      },
      button: {
        register: '使用組織帳號註冊',
        redirecting: '正在重新導向至身分提供者...',
      },
      hint: '點擊上方按鈕將重新導向至組織的身分提供者進行帳號註冊。',
    },
  },
  profile: {
    title: '個人資料',
    subtitle: '管理您的個人資訊和偏好設定',
    actions: {
      edit: '編輯資料',
      save: '儲存變更',
      saving: '儲存中...',
    },
    summary: {
      about: '關於我',
    },
    sections: {
      personalInfo: {
        title: '個人資訊',
        description: '更新您的個人資訊，這些資訊將會顯示在您的個人檔案中。',
      },
    },
    fields: {
      username: {
        label: '使用者名稱',
        cannotChange: '使用者名稱無法修改',
      },
      firstName: {
        label: '名字',
        placeholder: '輸入名字',
      },
      lastName: {
        label: '姓氏',
        placeholder: '輸入姓氏',
      },
      email: {
        label: '電子郵件',
        placeholder: '輸入電子郵件',
        identityProviderNote: '請透過您的身分提供者修改',
      },
    },
    errors: {
      notLoggedIn: '請先登入',
    },
    status: {
      loading: '個人資料載入中...',
    },
    notifications: {
      loadFailed: '無法載入個人資料。',
      saveFailed: '儲存個人資料時發生錯誤。',
    },
  },
  settings: {
    title: '系統設定',
    subtitle: '管理應用程式設定與開發工具配置',
    actions: {
      resetDefaults: '重置預設',
      save: '儲存設定',
      saving: '儲存中...',
      saveAll: '儲存所有設定',
      syncWorkspace: '同步工作區設定',
      syncing: '同步中...',
    },
    tabs: {
      general: '一般',
      ssh: 'SSH Keys',
      claudeCode: 'Claude Code',
      opencode: 'OpenCode',
      codex: 'Codex',
      git: 'Git',
    },
    sections: {
      appearance: {
        title: '外觀與語系',
        description: '自訂主題、語言與時區',
        theme: {
          label: '主題模式',
          description: '選擇您偏好的主題外觀',
          options: {
            light: '淺色模式',
            dark: '深色模式',
            system: '跟隨系統',
          },
        },
        language: {
          label: '語言設定',
          description: '選擇應用程式介面語言',
          options: {
            zhTW: '繁體中文',
            en: 'English',
          },
        },
        timezone: {
          label: '時區設定',
          description: '設定顯示的時區',
          options: {
            utc: 'UTC',
            taipei: '台北 (UTC+8)',
            tokyo: '東京 (UTC+9)',
            london: '倫敦 (UTC+0)',
            losAngeles: '洛杉磯 (UTC-8)',
          },
        },
      },
      ssh: {
        title: 'SSH Key 管理',
        description: '管理您的 SSH 公私鑰對',
        privateKey: {
          label: 'Private Key',
          placeholder: '-----BEGIN OPENSSH PRIVATE KEY-----',
          actions: {
            show: '顯示',
            hide: '隱藏',
            copy: '複製',
          },
        },
        publicKey: {
          label: 'Public Key',
          placeholder: 'ssh-rsa AAAAB3NzaC1yc2E...',
          copy: '複製',
        },
        generate: '產生新的 SSH Key Pair',
      },
      claudeCode: {
        title: 'Claude Code 設定',
        description: '配置認證方式與模型參數',
        authMethod: {
          label: '認證方式',
          description: '選擇 Claude 的認證方式',
          options: {
            subscription: 'Subscription',
            apikey: 'API Key',
          },
        },
        subscription: {
          title: 'Claude Subscription',
          connectButton: '連結 Claude 帳號',
          disconnectButton: '取消連結',
          authCodeLabel: 'Authentication Code',
          authCodePlaceholder: '請輸入認證碼',
          authCodeHint: '請在新視窗中完成認證，然後貼上取得的 Authentication Code',
          connectedStatus: '✓ 已成功連結 Claude 帳號',
          expiresAt: '過期時間',
          status: {
            connected: '已連結',
            notConnected: '未連結',
          },
          account: '帳號',
          accountUnavailable: '尚未提供',
          description: '您的 Claude 訂閱將被 Aileron 代理用於執行開發任務。',
          oauthWindow: {
            openingTitle: '正在開啟認證視窗...',
            openingDescription: '請在彈出的視窗中完成 Claude 認證',
            openedTitle: '認證視窗已開啟',
            openedDescription: '請在新視窗中完成認證，然後貼上取得的 Authentication Code',
            failedTitle: '無法開啟認證視窗',
            failedDescription: '請確保瀏覽器允許彈出視窗',
          },
          verifying: '正在驗證認證碼...',
          pleaseWait: '請稍候',
          saveButton: '儲存',
          cancelButton: '取消',
          success: {
            title: '認證成功',
            description: '已成功連結 Claude 帳號',
            syncDescription: '認證成功！請點擊「同步設定」按鈕將設定同步到工作區。',
          },
          errors: {
            emptyCode: '請輸入 Authentication Code',
            loginRequired: '您需要先登入才能進行 OAuth 認證',
            authFailed: '認證失敗',
            sessionExpiredTitle: '認證失敗',
            sessionExpiredDescription: '您的登入狀態已過期，請重新登入後再試',
            unknown: '無法完成認證',
          },
          disconnect: {
            loginRequiredTitle: '無法取消連結',
            successTitle: '已取消連結',
            successDescription: 'Claude 帳號連結資訊已清除',
            failedTitle: '取消連結失敗',
            failedDescription: '請稍後再試',
          },
        },
        apikey: {
          title: 'API Key 認證',
          providerLabel: 'API 廠商',
          providerPlaceholder: '選擇 API 廠商',
          providerOptions: {
            anthropic: 'Anthropic',
            awsBedrock: 'AWS Bedrock',
            googleVertexAi: 'Google Vertex AI',
            other: '其他',
          },
          modelLabel: '模型',
          modelPlaceholder: '例如：claude-sonnet-5（選填，留空使用預設）',
          modelHelp: '若留空，將使用 Claude SDK 的預設模型',
        },
        environmentVariables: {
          title: '環境變數',
          description: '設定 API 金鑰和其他環境變數',
          addButton: '新增變數',
          keyLabel: '變數名稱',
          valueLabel: '變數值',
          keyPlaceholder: '例如：ANTHROPIC_API_KEY',
          valuePlaceholder: '變數值',
          emptyState: {
            title: '尚未設定任何環境變數',
            description: '點擊「新增變數」開始設定',
          },
          hints: {
            loaded: '環境變數會在 Claude Code 執行時載入',
            required: '變數名稱和值都不可為空',
            naming: '建議使用大寫字母和底線命名變數',
          },
        },
        authKey: {
          label: 'Authentication Key',
          placeholder: '請輸入您的 API 金鑰...',
        },
        model: {
          label: '模型',
          placeholder: '選擇模型',
        },
        provider: {
          label: 'API 廠商',
          placeholder: '選擇 API 廠商',
        },
        models: {
          title: '模型',
          description: '選擇 AI Chat 可用於此工具的模型。',
          addPlaceholder: '輸入模型 ID',
          addButton: '新增模型',
          allowedLabel: '允許使用',
          defaultLabel: '預設模型',
          customBadge: '自訂',
          removeCustom: '移除自訂模型',
        },
      },
      codex: {
        title: 'Codex 設定',
        description: '設定 Codex 的 ChatGPT 訂閱登入、模型與 runtime container 環境變數。',
        authMethod: {
          label: '認證方式',
          description: '選擇 Codex 的認證方式',
          options: {
            subscription: 'Subscription',
            apikey: 'API Key',
          },
        },
        login: {
          title: 'ChatGPT 訂閱',
          account: '帳號',
          notConnectedDescription: '連結後可在 workspace container 中使用 ChatGPT 訂閱執行 Codex。',
          deviceCode: '請開啟驗證頁面並輸入代碼 {{code}}。',
          openVerificationLink: '開啟 Codex 驗證頁',
          connectButton: '連結 ChatGPT 帳號',
          refreshButton: '重新整理狀態',
          cancelButton: '取消',
          disconnectButton: '取消連結',
          status: {
            notConnected: '未連結',
            pending: '等待中',
            connected: '已連結',
            needsRelogin: '需要重新登入',
            error: '錯誤',
          },
          errors: {
            startFailedTitle: '無法開始 Codex 登入',
            startFailedDescription: '請稍後再試。',
            serviceUnavailableDescription: '請確認 Codex 登入服務可用，然後再試一次。',
            providerFailedDescription: 'Codex 登入提供者暫時無法完成驗證，請稍後再試。',
            logoutFailedTitle: '無法取消連結 Codex',
            logoutFailedDescription: '請稍後再試。',
          },
          window: {
            openedTitle: '已開啟 Codex 登入頁',
            openedDescription: '請在新視窗輸入畫面上的驗證代碼。',
            blockedTitle: '無法自動開啟登入頁',
            blockedDescription: '請手動開啟驗證頁面並輸入畫面上的代碼。',
          },
        },
        model: {
          label: '模型',
          placeholder: 'model-id',
          help: '此模型會同步到 Codex runtime 設定。',
        },
        environmentVariables: {
          title: 'Codex 環境變數',
          description: 'API Key 模式會將這些變數寫入 workspace runtime container，並套用到新 workspace。',
        },
        models: {
          title: '模型',
          description: '選擇 AI Chat 可用於此工具的模型。',
          addPlaceholder: '輸入模型 ID',
          addButton: '新增模型',
          allowedLabel: '允許使用',
          defaultLabel: '預設模型',
          customBadge: '自訂',
          removeCustom: '移除自訂模型',
        },
      },
      opencode: {
        description: '設定 OpenCode 的模型存取與環境變數。',
        environmentVariables: {
          title: 'OpenCode 環境變數',
          description: '這些變數會寫入 workspace runtime container 供 OpenCode 使用。',
        },
        models: {
          title: '模型',
          description: '選擇 AI Chat 可用於此工具的模型。',
          addPlaceholder: '輸入模型 ID',
          addButton: '新增模型',
          allowedLabel: '允許使用',
          defaultLabel: '預設模型',
          customBadge: '自訂',
          removeCustom: '移除自訂模型',
        },
      },
      git: {
        title: 'Git 設定',
        description: '配置 Git 使用者資訊',
        userName: {
          label: 'Git 使用者名稱',
          placeholder: '請輸入您的 Git 使用者名稱',
        },
        userEmail: {
          label: 'Git 使用者信箱',
          placeholder: '請輸入您的 Git 使用者信箱',
        },
      },
    },
    notifications: {
      saved: {
        title: '設定已保存',
        description: '所有設定已成功保存',
      },
      loginRequired: {
        title: '請先登入',
        description: '請先登入',
      },
      saveLoginRequired: {
        title: '無法儲存',
        description: '請先登入',
      },
      loadFailed: {
        title: '設定載入失敗',
        description: '無法從伺服器載入使用者設定。',
      },
      saveFailed: {
        title: '儲存設定失敗',
        description: '更新設定時發生錯誤，請稍後再試。',
      },
      copied: {
        title: '已複製',
        description: '內容已複製到剪貼簿',
      },
      copyFailed: {
        title: '複製失敗',
        description: '無法將內容複製到剪貼簿',
      },
      generateKey: {
        title: '產生 SSH Key',
        progress: '正在產生 SSH Key Pair...',
        successTitle: '產生成功',
        failedTitle: '產生失敗',
        failedDescription: '無法產生 SSH Key Pair',
        description: 'SSH Key Pair 已成功產生並儲存',
      },
      syncSuccess: {
        title: '同步成功',
        description: '設定已成功同步到 {{count}} 個工作區',
      },
      syncPartial: {
        title: '部分同步失敗',
        description: '同步到 {{count}} 個工作區時部分設定失敗',
      },
      syncFailed: {
        title: '同步失敗',
        description: '無法同步設定到 {{count}} 個工作區',
        loginRequired: '請先登入',
      },
      saveAndSyncSuccess: {
        title: '儲存成功',
        description: '設定已儲存並同步到工作區',
      },
    },
    status: {
      loading: '設定載入中...',
    },
  },
};

export default pages;
