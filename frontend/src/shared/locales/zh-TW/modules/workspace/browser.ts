const browser = {
  title: 'Chrome 瀏覽器',
  actions: {
    reload: '重新整理',
    retry: '重試',
    restartContainer: '重啟容器',
    fullscreen: {
      enter: '進入全螢幕瀏覽器',
      exit: '退出全螢幕瀏覽器',
    },
  },
  extensionPairing: {
    action: '連接瀏覽器擴充功能',
    connecting: '正在連接擴充功能...',
    success: {
      title: '已開始配對瀏覽器擴充功能',
      description: '擴充功能已接受此工作區的配對請求。',
    },
    error: {
      title: '瀏覽器擴充功能配對失敗',
      description: '擴充功能無法接受此工作區。請確認已安裝部署所設定的擴充功能後再試一次。',
    },
  },
  loading: '載入中...',
  connecting: '正在連接...',
  connectivity: {
    preparing: '正在準備已驗證的瀏覽器連線…',
    unavailable: '瀏覽器連線驗證暫時無法使用。',
    state: {
      pending: '連線驗證中',
      ready: '連線已就緒',
      degraded: '連線降級但可用',
      not_ready: '連線尚未就緒',
      unavailable: '連線驗證無法使用',
    },
  },
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
    cannotConnect: '無法連接到瀏覽器，請確認 Chrome 容器正在運行',
    securityFailure: 'VNC 安全驗證失敗',
    noWorkspace: '找不到工作區資訊',
    credentialUnavailable: '無法取得瀏覽器存取憑證',
    recoveryExhausted: '瀏覽器連線未能在重試上限內恢復。',
    nekoConnectionFailed: 'Neko 連線失敗',
    nekoConnectionTimeout: '瀏覽器連線逾時',
    nekoIceServerUnreachable: '無法連線至 TURN 伺服器，請確認網路設定',
    nekoWebsocketFailed: 'Neko WebSocket 連線失敗',
    nekoWebrtcFailed: '瀏覽器視訊連線失敗',
    nekoDataChannelFailed: '瀏覽器操作連線失敗',
  },
};

export default browser;
