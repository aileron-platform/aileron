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
  webCanvas: {
    title: '網頁畫布',
    routePlaceholder: '選擇或輸入路由',
    iframeTitle: '工作區網頁畫布',
    loading: '畫布載入中...',
    manifest: {
      errors: {
        invalid: {
          title: '畫布 manifest 錯誤',
          description: '目前的 canvas.json 無效，請修正後重新同步畫布。',
        },
      },
      actions: {},
      warnings: {},
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
    review: {
      toolbar: {
        toggle: '選取畫布元素新增修改指示',
      },
      bridgeWaiting: '正在準備選取模式...',
      form: {
        title: '選取目標修改指示',
        placeholder: '描述這個元素或區域需要如何修改。',
        addToList: '加入修改清單',
        sendNow: '立即送出給 AI',
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
        sendToChat: '送到 AI Chat',
        sendAllToChat: '全部送到 AI Chat',
        delete: '刪除指示',
        expand: '展開畫布修改指示',
        collapse: '縮小畫布修改指示',
      },
      toast: {
        sentTitle: '已送出給 AI',
        sentDescription: '修改指示已送到 AI Chat 並送出訊息。',
        handoffFailedTitle: '無法送到 AI Chat',
        handoffFailedDescription: '修改指示仍保留在清單中，請稍後重試。',
      },
      errors: {
        bridge: '畫布選取模式無法讀取此預覽。',
        missingTarget: '請先選取元素或區域。',
        emptyInstruction: '新增修改指示前請先輸入內容。',
        createFailed: '無法新增修改指示。',
      },
    },
  },
};

export default canvas;
