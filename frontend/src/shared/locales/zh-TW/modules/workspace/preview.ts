const preview = {
  header: {
    title: '預覽畫面',
    actions: {
      fullscreen: {
        enter: '全螢幕預覽',
        exit: '退出全螢幕',
      },
      refresh: '重新整理',
      menu: '選單',
    },
  },
  sessionResult: {
    title: '對話結果',
    emptyMessage: '目前沒有對話結果可預覽',
  },
  webPreview: {
    title: '網頁預覽',
    urlPlaceholder: '輸入要載入的網址，例如：https://localhost:5173',
    iframeTitle: 'Workspace Live 預覽畫面',
    notFound: {
      title: '未找到 Next.js 專案',
      defaultMessage: '工作區中未找到 Next.js 專案',
    },
  },
  browser: {
    title: 'Chrome 瀏覽器',
    actions: {
      reload: '重新整理',
      retry: '重試',
      restartContainer: '重啟容器',
    },
    loading: '載入中...',
    connecting: '正在連接...',
    notReady: {
      title: '瀏覽器尚未啟動',
      description: 'Chrome 瀏覽器容器目前無法使用',
      hint: '提示：Chrome 瀏覽器會隨工作區執行環境一起啟動',
    },
    restart: {
      started: 'Chrome 重啟中',
      inProgress: '正在重啟 Chrome 瀏覽器',
      description: 'Chrome 容器重啟已開始，請稍候...',
      failed: '重啟失敗',
    },
    error: {
      status: '瀏覽器狀態異常',
      notStarted: '瀏覽器尚未啟動',
      connection: '無法連接到瀏覽器',
      connectionFailed: '連接失敗',
      cannotConnect: '無法連接到瀏覽器預覽，請確認 Chrome 容器正在運行',
      securityFailure: 'VNC 安全驗證失敗',
      noWorkspace: '找不到工作區資訊',
    },
  },
  usage: {
    stats: '統計',
    totalTokens: '總 Token',
    input: '輸入',
    output: '輸出',
    details: '詳細資訊',
    cost: 'Cost',
    costUnavailable: '成本未提供',
    notAvailable: '未提供',
    cache: 'Cache',
    tier: 'Service Tier',
    duration: '耗時',
    provider: '來源',
    model: '模型',
    models: '模型貢獻',
    modelCount: '{{count}} 個模型',
    modelCost: '成本',
    dialog: {
      title: '使用詳細資訊',
      description: '本次回應的完整使用統計',
    },
    cacheRead: '讀',
    cacheWrite: '寫',
  },
};

export default preview;
