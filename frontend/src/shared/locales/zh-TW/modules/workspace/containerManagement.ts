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
    browserCredential: {
      title: '瀏覽器存取憑證',
      description: '輪替此工作區瀏覽器的一般使用者與管理者憑證。',
      rotate: '輪替憑證',
      rotateSuccess: '已開始輪替瀏覽器憑證。',
      rotateFailed: '無法開始輪替瀏覽器憑證。',
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
    envVars: {
      label: '環境變數設定',
      keyPlaceholder: '變數名稱',
      valuePlaceholder: '變數值',
      configuredValuePlaceholder: '已設定，如需取代請輸入新值',
      replaceConfiguredValues: '取代環境變數清單前，請重新輸入所有已設定項目的值。',
      add: '新增環境變數',
    },
    environments: {
      universal: {
        label: '標準容器映像',
        description: 'Aileron 標準執行環境，包含 Python、Node.js、Git、SSH、Claude Code 等完整工具鏈',
      },
      java: {
        label: 'Java 21 + Maven',
        description: '預載 Eclipse Temurin JDK 21 與 Apache Maven 3.9，適合 Spring Boot、Maven 專案',
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
      applied: '防火牆設定已完成套用。',
      saveFailed: '儲存防火牆設定時發生錯誤。',
      refreshFailed: '無法更新防火牆同步狀態。',
      retryFailed: '無法重試防火牆同步。',
      revisionConflict: '防火牆設定已在其他地方變更，已載入最新設定。',
    },
    sync: {
      applying: {
        title: '正在套用防火牆設定',
        description: '已觀測 revision {{observedRevision}}，正在收斂至目標 revision {{desiredRevision}}。',
      },
      applied: 'revision {{revision}} 已完成套用。',
      failed: {
        title: '防火牆套用失敗',
        description: '平台無法套用目標防火牆 revision。',
        retry: '重試套用',
        retrying: '重試中…',
      },
    },
    errors: {
      FIREWALL_DELIVERY_FAILED: '控制平面無法傳遞目標防火牆 revision。',
      FIREWALL_APPLY_FAILED: '平台無法執行目標防火牆 revision。',
      FIREWALL_DOMAIN_INVALID: '請輸入單一 canonical exact hostname，不可包含萬用字元、URL、路徑、連接埠或 IP 位址。',
      FIREWALL_DOMAIN_DUPLICATE: '此 exact hostname 已存在。',
      FIREWALL_DOMAIN_LIMIT_EXCEEDED: '允許網域數量已超過上限。',
      FIREWALL_ALLOWLIST_EMPTY: '「僅允許指定網域」至少需要一個允許網域。',
      FIREWALL_DOMAINS_NOT_ALLOWED: '只有「僅允許指定網域」模式可以設定允許網域。',
      FIREWALL_RETRY_NOT_ALLOWED: '此防火牆 revision 已無法重試，請重新載入最新狀態。',
      CILIUM_NOT_ENABLED: '此平台尚未啟用 Cilium。',
      FIREWALL_CILIUM_ENDPOINT_DISCOVERY_FAILED: '平台無法檢查 Cilium 端點，因此無法確認防火牆規則是否已套用。',
      FIREWALL_POLICY_APPLY_FAILED: '平台無法建立或更新 Cilium 防火牆規則。',
      FIREWALL_POLICY_ENFORCEMENT_TIMEOUT: 'Cilium 未能在時限內確認防火牆規則已強制執行。',
      FIREWALL_POLICY_REJECTED: 'Cilium 已拒絕防火牆規則。',
      FIREWALL_POLICY_STATUS_INVALID: 'Cilium 回報的防火牆規則狀態無效。',
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
        title: 'Workspace Runtime 網路規則',
        description: '獨立控制 Runtime 執行群組的外部網路存取，不會變更 Browser。',
      },
      browser: {
        title: 'Browser 網路規則',
        description: '獨立控制 Browser 的外部網路存取，不會變更 Workspace Runtime。',
      },
    },
    egressMode: {
      label: '外部網路存取模式',
      options: {
        blocked: {
          label: '封鎖外部網路',
          description: '禁止所有外部連線，但保留 DNS 解析能力',
        },
        allowlist: {
          label: '僅允許指定網域',
          description: '僅允許連線至已設定的外部網域',
        },
        unrestricted: {
          label: '允許所有外部網路',
          description: '允許外部連線，不限制存取網域',
        },
      },
    },
    allowedDomains: {
      label: '允許網域管理',
      placeholder: '輸入網域名稱，例如：example.com',
      add: '新增允許網域',
      remove: '移除 {{domain}}',
      exactHostnameHint: '僅接受 exact hostname，不支援萬用字元或隱含子網域。',
      invalid: '請輸入單一 canonical exact hostname，不可包含萬用字元、URL、路徑、連接埠或 IP 位址。',
      duplicate: '此 exact hostname 已存在。',
      required: '「僅允許指定網域」至少需要一個允許網域。',
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
      scrollLeft: '向左捲動終端機分頁',
      scrollRight: '向右捲動終端機分頁',
    },
    theme: {
      label: '終端機主題',
      options: {
        light: '淺色終端機',
        dark: '深色終端機',
      },
    },
    menus: {
      actions: '操作',
      context: {
        clear: '清除',
        close: '關閉終端機',
        unassign: '解除指派',
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
      syncing: '正在同步終端機工作階段...',
      replayReset: '重新連線後已重設終端畫面',
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
