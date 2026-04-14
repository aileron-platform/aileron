const dialogs = {
  settingsCheck: {
    title: {
      ready: '設定檢查完成',
      incomplete: '需要完成系統設定',
    },
    description: {
      ready: '您的系統設定已完成，可以開始建立工作區。',
      incomplete: '在建立工作區之前，請先完成以下必要的系統設定。',
    },
    requiredSettings: '必要設定項目',
    settings: {
      ssh: 'SSH Keys 設定',
      claudeCode: 'Claude Code 設定',
      git: 'Git 設定',
    },
    warning: '請先完成 {{settings}} 的設定',
    allComplete: '所有必要設定已完成，您可以繼續建立工作區。',
    actions: {
      goToSettings: '前往設定',
      proceed: '繼續建立',
    },
  },
};

export default dialogs;

