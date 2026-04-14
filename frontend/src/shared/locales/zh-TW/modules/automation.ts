const automation = {
  logs: {
    createFailed: '建立自動化任務失敗',
    updateFailed: '更新自動化任務失敗',
  },
  create: {
    title: '新增自動化任務',
    subtitle: '設定工作區、執行指令與觸發方式',
    actions: {
      creating: '建立中...',
      submit: '建立任務',
    },
  },
  edit: {
    title: '編輯自動化任務',
    subtitle: '更新任務配置、執行指令與啟停狀態',
    actions: {
      saving: '儲存中...',
      submit: '儲存任務',
    },
  },
  form: {
    fields: {
      name: {
        label: '任務名稱',
        placeholder: '例如：每日工作區備份',
      },
      workspace: {
        label: '目標工作區',
        placeholder: '選擇工作區',
        loading: '載入工作區中…',
        empty: '目前沒有可用的工作區',
        error: '無法載入工作區',
      },
      description: {
        label: '描述',
        placeholder: '說明任務要在工作區內執行的內容',
      },
      prompt: {
        label: 'Prompt / 指令',
        placeholder: '輸入要在任務中執行的 Prompt 或 Slash Command',
        helper: '可直接輸入自訂 Prompt，或透過指令選擇器快速插入標準化 Slash Command。',
        selectCommand: '選擇指令',
        commandsLoading: '正在載入 Slash Command…',
        commandsEmpty: '此工作區沒有可用的 Slash Command。',
        commandsError: '無法載入 Slash Command，請稍後再試。',
      },
      trigger: {
        label: '觸發類型',
        placeholder: '選擇觸發類型',
      },
      status: {
        label: '狀態',
        placeholder: '選擇狀態',
      },
      timezone: {
        label: '時區',
        placeholder: '選擇時區',
      },
      schedule: {
        label: '執行設定',
        placeholder: '例如：0 9 * * *',
        helper: 'Cron 例：0 9 * * * 表示每日 09:00。',
        timezoneHelper: '⏰ 所有任務統一使用系統時區，無需個別設定。',
      },
      webhookApiKey: {
        label: 'Webhook API Key',
        regenerate: '重新產生',
        helper: '使用此 API Key 透過 Webhook 觸發任務執行。',
      },
      tags: {
        label: '分類標籤',
        placeholder: '輸入標籤後按 Enter',
        add: '加入',
        suggestionsLabel: '常用：',
      },
    },
    timezone: {
      taipei: 'GMT+8 台北 (Asia/Taipei)',
      utc: 'UTC',
      losAngeles: 'GMT-8 舊金山 (America/Los_Angeles)',
      berlin: 'GMT+1 柏林 (Europe/Berlin)',
    },
    trigger: {
      cron: '排程觸發',
      manual: '手動觸發',
      webhook: 'Webhook',
    },
    status: {
      active: '啟用中',
      paused: '暫停',
      draft: '草稿',
    },
    workspace: {
      options: {
        aileron: 'Aileron',
        infraOperations: 'Infra Operations',
        promptLibrary: 'Prompt Library',
        mlLab: 'ML Lab',
      },
    },
  },
  slashDialog: {
    title: '選擇 Slash Command',
    description: '從指令庫挑選常用指令，將結果填入 Prompt 欄位。',
    searchPlaceholder: '輸入指令名稱、描述或標籤搜尋…',
    empty: '目前沒有符合條件的指令',
    scope: {
      all: '全部',
      project: '專案',
      user: '個人',
    },
  },
  sidebar: {
    title: '任務篩選',
    description: '依狀態快速篩選任務',
    filters: {
      all: '全部任務',
      active: '執行中',
      paused: '已暫停',
      failed: '異常',
    },
    summary: {
      title: '執行摘要',
      successRate: '成功率',
      averageDuration: '平均耗時',
      running: '執行中',
      queued: '排隊中',
      seconds: '{{value}} 秒',
    },
  },
  execution: {
    status: {
      queued: '已加入佇列',
      waiting: '排隊中',
      running: '執行中',
      success: '成功',
      failed: '失敗',
      cancelled: '已取消',
      timeout: '超時',
      unknown: '未知',
    },
  },
  dashboard: {
    title: '自動化中心',
    actions: {
      refresh: '重新整理',
      create: '新增任務',
    },
    info: {
      failureRate: '近 24 小時失敗率 {{rate}}',
      taskCount: '{{count}} 筆任務',
    },
    metrics: {
      active: {
        title: '啟用中的任務',
        subtitle: '持續投遞到工作區的任務',
      },
      paused: {
        title: '暫停的任務',
        subtitle: '暫停等待調整或審核的任務',
      },
      failed: {
        title: '失敗執行次數',
        subtitle: '所有任務累計的失敗執行次數',
      },
      duration: {
        title: '平均執行耗時',
        subtitle: '近期工作區任務的平均完成時間',
      },
    },
    search: {
      placeholder: '搜尋名稱、說明或負責人',
      submit: '搜尋',
    },
    table: {
      title: '任務管理',
      subtitle: '依工作區與觸發條件掌握任務，點擊即可查看執行日誌',
      headers: {
        name: '名稱',
        schedule: '排程時間',
        nextRun: '下次執行',
        status: '狀態',
        view: '執行紀錄',
        actions: '操作',
      },
      status: {
        active: '啟用中',
        paused: '已暫停',
        failed: '異常',
        draft: '草稿',
      },
      viewTask: '檢視執行',
      edit: '編輯任務',
      runNow: '立即執行',
      delete: '刪除任務',
      empty: '目前無符合條件的任務。',
      confirmDelete: '確定要刪除「{{name}}」嗎？',
      nextRunLabel: '下次：{{value}}',
      lastRunLabel: '上次：{{value}}',
      noScheduled: '未排程',
    },
    upcoming: {
      title: '即將執行',
      subtitle: '掌握排隊與執行中的工作區任務',
      none: '目前沒有排隊或執行中的任務。',
      recentTitle: '最近完成',
    },
    executionCard: {
      trigger: '觸發方式：{{trigger}}',
      duration: '耗時：{{seconds}} 秒',
      viewLogs: '查看日誌',
      viewSession: '查看對話',
      notStarted: '尚未開始',
    },
    timeline: {
      empty: '尚無執行紀錄。',
    },
    pagination: {
      summary: '顯示第 {{start}} - {{end}} 筆，共 {{total}} 筆',
      empty: '目前沒有資料',
      previous: '上一頁',
      next: '下一頁',
      page: '第 {{current}} / {{total}} 頁',
    },
    dialogs: {
      executionLog: {
        description: '檢視此次執行的日誌與狀態細節。',
        fields: {
          executionId: '執行 ID',
          taskId: '任務',
          jobId: '任務 ID',
          startedAt: '開始時間',
          finishedAt: '完成時間',
          trigger: '觸發方式',
          duration: '耗時',
        },
        durationSeconds: '{{seconds}} 秒',
        logs: {
          title: '執行日誌',
          filters: {
            all: '全部日誌',
            info: 'INFO',
            error: 'ERROR',
            warning: 'WARNING',
            success: 'SUCCESS',
          },
          reload: '重新載入',
          loading: '載入日誌中...',
          empty: '暫無日誌',
        },
        mock: {
          start: '任務（{{taskId}}）開始執行，觸發方式：{{trigger}}',
          loadEnvironment: '載入執行環境設定...完成',
          failureDetected: '偵測到執行錯誤，已觸發警示通知。',
          completed: '任務完成，結果已寫入目標資料源。',
          running: '持續執行中，請稍候查看最新日誌...',
          queued: '已排隊等待可用的工作節點...',
        },
      },
    },
    executionsDialog: {
      title: '執行日誌 - {{name}}',
      rangeTitle: '時間範圍篩選',
      rangeSubtitle: '依時間範圍查看此任務的執行記錄',
      tabs: {
        all: '全部',
        today: '今日',
        tomorrow: '明日',
        week: '本週',
        month: '本月',
        custom: '自定範圍',
      },
      date: {
        start: '開始日期',
        end: '結束日期',
        to: '至',
        clear: '清除範圍',
      },
      empty: '尚無執行紀錄。',
    },
  },
};

export default automation;
