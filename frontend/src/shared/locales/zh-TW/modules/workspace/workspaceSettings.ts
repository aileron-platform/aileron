const workspaceSettings = {
  header: {
    title: '工作區設定',
  },
  empty: {
    title: '選擇設定項目',
    description: '請從左側選單選擇要設定的項目',
  },
  basic: {
    header: {
      title: '基本設定頁面',
    },
    actions: {
      save: {
        label: '儲存設定',
        saving: '儲存中...',
      },
    },
    status: {
      loading: '載入工作區設定中...',
    },
    notifications: {
      loadFailed: '無法載入工作區設定。',
      saveSuccess: '基本設定已更新。',
      saveFailed: '儲存設定時發生錯誤。',
    },
    fields: {
      name: {
        label: '工作區名稱',
        placeholder: '請輸入工作區名稱',
        helper: '工作區名稱將顯示在導航欄和標題中',
      },
      description: {
        label: '工作區描述',
        placeholder: '請輸入工作區描述',
        helper: '描述工作區的用途和功能，幫助團隊成員了解專案內容',
      },
      repository: {
        label: 'Git Repository',
        placeholder: 'Git repository URL',
        helper: 'Git repository 設定在工作區建立後無法修改',
      },
      branch: {
        label: '分支',
        helper: 'Git repository 的分支設定在工作區建立後無法修改',
      },
      cliType: {
        label: 'CLI 類型',
        helper: '建立後不可修改',
      },
    },
    metadata: {
      title: '執行資訊',
      description: '顯示目前工作區的佈建方式、命名空間與整體狀態。',
      fields: {
        provisioner: 'Provisioner',
        namespace: 'Namespace',
        overallPhase: '整體狀態',
      },
      namespaceFallback: '使用平台預設命名空間',
      notAvailable: '尚未提供',
      provisioners: {
        docker: 'Docker',
        kubernetes: 'Kubernetes',
      },
      phases: {
        running: '運行中',
        starting: '啟動中',
        reconciling: '同步中',
        pending: '等待中',
        failed: '失敗',
        error: '錯誤',
        stopped: '已停止',
        disabled: '已停用',
        unknown: '未知',
      },
    },
    components: {
      title: '服務狀態',
      description: '顯示 runtime、browser 與 nextjs 的個別狀態與連線位址。',
      runtime: 'Runtime',
      browser: 'Browser',
      nextjs: 'Next.js',
      fields: {
        internalUrl: '內部 URL',
        externalUrl: '外部 URL',
        lastRestartRequestedAt: '最後重啟請求時間',
      },
    },
  },
  reset: {
    header: {
      title: '工作區重置頁面',
    },
    danger: {
      title: '危險操作',
      description: '以下操作可能會對您的工作區造成不可逆的影響，請謹慎操作',
    },
    lifecycle: {
      title: '生命週期操作',
      description: '針對 runtime、browser、nextjs 或整體工作區發送重啟請求。',
      operationState: {
        submitted: '已送出',
        processing: '進行中',
        completed: '已完成',
        description: '目前操作狀態：{{phase}}',
      },
      phases: {
        running: '運行中',
        starting: '啟動中',
        restarting: '重啟中',
        reconciling: '同步中',
        pending: '等待中',
        failed: '失敗',
        error: '錯誤',
        stopped: '已停止',
        disabled: '已停用',
        unknown: '未知',
      },
      actions: {
        runtime: {
          title: '重啟 Runtime',
          description: '重新啟動主要執行環境，通常用於套用 runtime 設定更新。',
          label: '重啟 Runtime',
          loading: '重啟 Runtime 中...',
          successTitle: 'Runtime 重啟已開始',
          successDescription: 'Runtime 重啟請求已送出，請稍候片刻。',
          errorTitle: 'Runtime 重啟失敗',
          errorDescription: '無法重啟 Runtime，請稍後再試。',
        },
        browser: {
          title: '重啟 Browser',
          description: '重新啟動 browser workload，適合處理瀏覽器串流或互動異常。',
          label: '重啟 Browser',
          loading: '重啟 Browser 中...',
          successTitle: 'Browser 重啟已開始',
          successDescription: 'Browser 重啟請求已送出，請稍候片刻。',
          errorTitle: 'Browser 重啟失敗',
          errorDescription: '無法重啟 Browser，請稍後再試。',
        },
        nextjs: {
          title: '重啟 Next.js',
          description: '重新啟動 Next.js workload，適合處理預覽服務異常。',
          label: '重啟 Next.js',
          loading: '重啟 Next.js 中...',
          successTitle: 'Next.js 重啟已開始',
          successDescription: 'Next.js 重啟請求已送出，請稍候片刻。',
          errorTitle: 'Next.js 重啟失敗',
          errorDescription: '無法重啟 Next.js，請稍後再試。',
        },
        workspace: {
          title: '重啟整體工作區',
          description: '重新啟動整個工作區的主要執行流程，適合處理整體狀態異常。',
          label: '重啟工作區',
          loading: '重啟工作區中...',
          successTitle: '工作區重啟已開始',
          successDescription: '工作區重啟請求已送出，請稍候片刻。',
          errorTitle: '工作區重啟失敗',
          errorDescription: '無法重啟工作區，請稍後再試。',
        },
      },
    },
    delete: {
      title: '刪除工作區',
      description: '永久刪除此工作區及其所有相關資料，包括設定檔、專案檔案和歷史記錄',
      trigger: '刪除工作區',
      dialog: {
        title: '確認刪除工作區',
        intro: '您即將刪除工作區「{{workspaceName}}」。',
        impactTitle: '此操作將會永久刪除：',
        impactItems: {
          settings: '所有工作區設定',
          projects: '關聯的專案資料',
          variables: '環境變數與配置',
          history: '建置與部署歷史',
        },
        warning: '此操作無法復原！',
        confirmLabel: {
          prefix: '請輸入',
          suffix: '來確認刪除：',
        },
        cancel: '取消',
        confirm: '確認刪除',
        confirming: '刪除中...',
      },
      success: {
        title: '刪除已開始',
        description: '工作區刪除已在背景執行，即將返回工作區列表',
      },
      error: {
        title: '刪除失敗',
        description: '無法刪除工作區，請稍後再試',
      },
    },
  },
};

export default workspaceSettings;
