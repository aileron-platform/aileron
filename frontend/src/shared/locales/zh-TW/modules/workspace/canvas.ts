const canvas = {
  header: {
    title: '畫布',
    actions: {
      fullscreen: {
        enter: '進入全螢幕畫布',
        exit: '退出全螢幕畫布',
      },
    },
    loading: '畫布載入中...',
  },
  sessionResult: {
    title: '對話結果',
    emptyMessage: '目前沒有可在畫布顯示的對話結果',
  },
  webCanvas: {
    title: '網頁畫布',
    routePlaceholder: '選擇或輸入路由',
    iframeTitle: '工作區網頁畫布',
    loading: '畫布載入中...',
    manifest: {
      status: {
        missing: '無 manifest',
        valid: 'manifest 正常',
        invalid: 'manifest 錯誤',
      },
      statusNotice: {
        skill: {
          title: '{{title}}',
          description: '目前顯示來自 {{skillName}} 的 skill 畫布。',
        },
        user: {
          title: '{{title}}',
          description: '目前顯示使用者啟用的畫布。',
        },
        details: 'Manifest：{{manifest}} · Runtime：{{runtime}}',
      },
      errors: {
        invalid: {
          title: '畫布 manifest 錯誤',
          description: '目前的 canvas.json 無效，請修正後重新同步畫布。',
        },
      },
      actions: {},
      warnings: {},
    },
    owner: {
      skill: {
        label: 'Skill 畫布',
      },
      user: {
        label: '使用者畫布',
      },
    },
    default: {
      guidance: {
        title: '預設畫布',
        description: '目前沒有 active canvas manifest。建立 /workspace/.aileron/canvas.json 後即可啟用畫布。',
      },
    },
    runtime: {
      healthy: '正常',
      starting: '啟動中',
      errors: {
        startupFailed: '啟動失敗',
      },
    },
    error: {
      title: '畫布無法使用',
      defaultMessage: '畫布尚未就緒，請同步或重置畫布後再試。',
    },
    actions: {
      missingWorkspace: '工作區資訊不完整。',
      unknownError: '畫布操作失敗。',
      errorTitle: '畫布操作失敗',
      sync: {
        label: '同步畫布',
        successTitle: '畫布已同步',
        successDescription: '畫布 manifest 已重新載入。',
        errorTitle: '畫布同步失敗',
      },
    },
    disable: {
      label: '停用 active canvas',
      successTitle: '已停用 active canvas',
      successDescription: '畫布已回到預設畫面。',
      errorTitle: '無法停用畫布',
    },
    review: {
      toolbar: {
        toggle: '選取畫布元素新增修改指示',
      },
      bridgeWaiting: '正在準備選取模式...',
      form: {
        title: '選取目標修改指示',
        placeholder: '描述這個元素或區域需要如何修改。',
        create: '新增修改指示',
        cancel: '取消',
        close: '關閉修改指示表單',
        dragHandle: '移動修改指示表單',
      },
      target: {
        area: '選取區域',
        multi: '已選取 {{count}} 個元素',
      },
      status: {
        open: '待處理',
        seen: '已送出',
        applied: '已套用',
        dismissed: '已略過',
      },
      notes: {
        title: '畫布修改指示',
        sendToAi: '送給 AI',
        sendAllToAi: '全部送給 AI',
        delete: '刪除指示',
        expand: '展開畫布修改指示',
        collapse: '縮小畫布修改指示',
      },
      toast: {
        createdTitle: '已新增修改指示',
        createdDescription: '已儲存選取目標與修改指示。',
      },
      errors: {
        bridge: '畫布選取模式無法讀取此預覽。',
        missingTarget: '請先選取元素或區域。',
        emptyInstruction: '新增修改指示前請先輸入內容。',
        createFailed: '無法新增修改指示。',
      },
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
      cannotConnect: '無法連接到瀏覽器畫布，請確認 Chrome 容器正在運行',
      securityFailure: 'VNC 安全驗證失敗',
      noWorkspace: '找不到工作區資訊',
      nekoConnectionFailed: 'Neko 連線失敗',
      nekoWebsocketFailed: 'Neko WebSocket 連線失敗',
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

export default canvas;
