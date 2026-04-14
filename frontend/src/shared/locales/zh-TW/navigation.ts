const navigation = {
  workspace: '工作區',
  templateCenter: '模板中心',
  automation: '自動化中心',
  brand: {
    title: 'Aileron',
  },
  workspaceSelector: {
    label: '工作區：',
    current: '目前工作區',
    description: '尚未提供描述',
    selectLabel: '選擇工作區',
    newWorkspace: '新增工作區',
    empty: '尚未建立任何工作區',
    error: '無法載入工作區列表',
    active: '使用中',
    owner: '擁有者：{{name}}',
    namespace: '命名空間：{{name}}',
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
  userMenu: {
    profile: '個人資料',
    settings: '系統設定',
    logout: '登出',
  },
  fullscreen: {
    enter: '進入全螢幕',
    exit: '退出全螢幕',
    error: '全螢幕切換失敗',
  },
  compactHeader: {
    exitFullscreen: '退出全螢幕',
    modules: {
      workspace: '工作區',
      automation: '自動化中心',
      template: '模板中心',
    },
    separator: '›',
  },
};

export default navigation;
