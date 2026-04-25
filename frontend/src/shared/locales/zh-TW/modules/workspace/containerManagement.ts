const containerManagement = {
  runtime: {
    header: {
      title: '執行環境',
      actions: {
        save: '儲存設定',
        saving: '儲存中…',
      },
    },
    status: {
      loading: '執行環境設定載入中…',
      empty: '尚未載入執行環境設定。',
    },
    notifications: {
      loadFailed: '無法載入執行環境設定。',
      saveSuccess: '執行環境設定已更新。',
      saveFailed: '儲存執行環境設定時發生錯誤。',
    },
    form: {
      runtime: {
        label: '容器映像選擇',
        placeholder: '選擇容器映像',
        loading: '載入中...',
        recommended: '推薦',
      },
      setupScript: {
        label: '設定指令碼',
        placeholder: '輸入安裝依賴項的指令，例如：npm install 或 pip install -r requirements.txt',
        description: '這些指令將在專案建立後自動執行',
      },
    },
    resources: {
      title: '執行環境資源配置',
      description: '僅 Kubernetes 工作區可覆寫執行環境的 CPU 與記憶體 requests / limits。',
      scope: 'workspace-browser 與 workspace-canvas 仍使用 Helm chart 的平台預設資源。',
      requests: {
        title: '資源請求',
      },
      limits: {
        title: '資源上限',
      },
      fields: {
        cpu: 'CPU',
        memory: '記憶體',
      },
    },
    envVars: {
      label: '環境變數設定',
      keyPlaceholder: '變數名稱',
      valuePlaceholder: '變數值',
      add: '新增環境變數',
    },
    portMappings: {
      system: {
        label: '系統連接埠',
        description: '由平台管理的預設 Docker 連接埠。',
        fields: {
          name: '名稱',
          containerPort: '容器連接埠',
          hostPort: '主機連接埠',
          protocol: '協定',
          description: '描述',
        },
      },
      label: '端口映射配置',
      description: '配置容器端口映射，可以指定固定端口或使用動態分配',
      fields: {
        containerPort: {
          label: '容器端口',
          placeholder: '3000',
        },
        hostPort: {
          label: '主機端口',
          placeholder: '自動分配',
        },
        protocol: {
          label: '協議',
          options: {
            tcp: 'TCP',
            udp: 'UDP',
          },
        },
        description: {
          label: '描述',
          placeholder: '端口用途說明',
        },
      },
      add: '新增端口映射',
      kubernetesUnsupported: 'Kubernetes 工作區目前不支援工作區層級的連接埠對外暴露設定。',
      hints: {
        autoAssign: '• 主機端口留空將自動分配可用端口',
        defaultPort: '• 容器端口 3002 為 Workspace Runtime 預設端口',
        reservedPorts: '• 避免使用系統保留端口 (1-1023)',
      },
    },
    environments: {
      universal: {
        label: '標準容器映像',
        description: 'Aileron 標準執行環境，包含 Python、Node.js、Git、SSH、Claude Code 等完整工具鏈',
      },
      'ubuntu-22': {
        label: 'Ubuntu 22.04',
        description: '通用 Linux 開發環境',
      },
      'ubuntu-24': {
        label: 'Ubuntu 24.04',
        description: '最新 Ubuntu LTS 版本',
      },
      'node-18': {
        label: 'Node.js 18',
        description: 'Node.js 18 + npm 開發環境',
      },
      'node-20': {
        label: 'Node.js 20',
        description: 'Node.js 20 + npm 開發環境',
      },
      'python-311': {
        label: 'Python 3.11',
        description: 'Python 3.11 + pip 開發環境',
      },
      'python-312': {
        label: 'Python 3.12',
        description: 'Python 3.12 + pip 開發環境',
      },
    },
  },
  firewall: {
    header: {
      title: '防火牆',
      actions: {
        save: '儲存設定',
        saving: '儲存中…',
      },
    },
    status: {
      loading: '防火牆設定載入中…',
      empty: '尚未載入防火牆設定。',
    },
    notifications: {
      loadFailed: '無法載入防火牆設定。',
      saveSuccess: '防火牆設定已更新。',
      saveFailed: '儲存防火牆設定時發生錯誤。',
    },
    unavailable: {
      title: '防火牆功能不可用',
      description: '平台尚未啟用 Cilium，因此目前無法使用防火牆功能。',
      reasons: {
        CILIUM_NOT_ENABLED: '平台尚未啟用 Cilium，因此目前無法使用防火牆功能。',
      },
    },
    groups: {
      workspace: {
        title: '工作區網路規則',
        description: '套用到 workspace-runtime 與 workspace-canvas。',
      },
      browser: {
        title: '瀏覽器網路規則',
        description: '套用到 workspace-browser。',
      },
    },
    networkAccess: {
      label: '網路存取權限',
      badge: {
        enabled: '開啟',
        disabled: '關閉',
      },
      options: {
        enabled: {
          description: '允許容器存取外部網路',
        },
        disabled: {
          description: '禁止容器存取外部網路',
        },
      },
    },
    domainAccessMode: {
      label: '允許網域選項',
      badge: {
        all: '全部（不受限制）',
        specific: '指定網域',
      },
      options: {
        all: {
          description: '允許存取所有網域',
        },
        specific: {
          description: '僅允許存取指定的網域',
        },
      },
    },
    allowedDomains: {
      label: '允許網域管理',
      placeholder: '輸入網域名稱，例如：example.com',
      add: '新增允許網域',
    },
    effectiveAllowedDomains: {
      label: '實際生效網域',
      empty: '目前沒有額外的生效網域可顯示。',
    },
  },
  terminal: {
    title: '終端機',
    newTab: '新增分頁',
    header: {
      title: '終端機',
    },
    tabs: {
      label: '終端機 {{index}}',
      add: '新增終端機',
      empty: '沒有終端機',
      new: '新增終端機',
      close: '關閉終端機',
      active: '目前',
    },
    menus: {
      actions: '操作',
      context: {
        clear: '清除',
        close: '關閉終端機',
        rename: '重新命名',
        unassign: '解除指派',
        renamePrompt: '輸入新的終端機名稱',
        switch: '切換終端機',
      },
    },
    layout: {
      changeTooltip: '切換佈局',
      confirm: {
        title: '變更佈局？',
        description: '切換至此佈局將關閉 {{count}} 個終端連線，僅保留最早的連線，確定要繼續嗎？',
        cancel: '取消',
        confirm: '繼續',
      },
      options: {
        single: {
          label: '單一窗格',
          description: '1 個窗格',
        },
        splitHorizontal: {
          label: '左右分割',
          description: '左右 2 個窗格',
        },
        splitVertical: {
          label: '上下分割',
          description: '上下 2 個窗格',
        },
        quad: {
          label: '四分割',
          description: '4 個等分窗格',
        },
        leftOneRightTwo: {
          label: '左 1 右 2',
          description: '左側 1 個，右側上下 2 個',
        },
        rightOneLeftTwo: {
          label: '右 1 左 2',
          description: '左側上下 2 個，右側 1 個',
        },
        topOneBottomTwo: {
          label: '上 1 下 2',
          description: '上方 1 個，下方左右 2 個',
        },
        bottomOneTopTwo: {
          label: '下 1 上 2',
          description: '上方左右 2 個，下方 1 個',
        },
      },
    },
    status: {
      connecting: '連線中...',
      reconnecting: '重新連線中...',
      connected: '已連線',
      disconnected: '已中斷連線',
      unassigned: '未指派',
    },
    connectionError: '連線錯誤',
    connect: '連線',
    retry: '重試',
    actions: {
      copy: '複製',
      paste: '貼上',
      restart: '重新啟動終端',
      enterFullscreen: '全螢幕',
      exitFullscreen: '退出全螢幕',
    },
    footer: {
      rows_one: '列: {{count}}',
      rows_other: '列: {{count}}',
      columns_one: '行: {{count}}',
      columns_other: '行: {{count}}',
      selection_one: '選取 {{count}} 字元',
      selection_other: '選取 {{count}} 字元',
      rows: '列: {{count}}',
      columns: '行: {{count}}',
      encoding: 'UTF-8',
      selection: '選取 {{count}} 字元',
    },
    limits: {
      max: {
        title: '已達終端機上限',
        description: '最多可建立 {{count}} 個終端機。',
      },
    },
  },
};

export default containerManagement;
