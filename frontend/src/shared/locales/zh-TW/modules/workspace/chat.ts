const chat = {
  dialogs: {
    fileChooser: {
      title: '選擇工作區檔案',
      searchPlaceholder: '輸入檔名或路徑搜尋...',
      projectPathLabel: '專案路徑：{{path}}',
      quickFilterTitle: '快速過濾',
      currentFilter: '當前過濾：{{description}}',
      noFiles: '目前沒有檔案。',
      noMatches: '沒有符合條件的檔案。',
      foundCount: '共找到 {{count}} 個檔案',
      filterPresets: {
        markdown: {
          label: 'Markdown',
          description: '所有 Markdown 檔案',
        },
        testMarkdown: {
          label: 'Test MD',
          description: '測試相關的 Markdown 檔案',
        },
        typescript: {
          label: 'TypeScript',
          description: 'TypeScript 程式檔案',
        },
        react: {
          label: 'React',
          description: 'React TypeScript 檔案',
        },
        javascript: {
          label: 'JavaScript',
          description: 'JavaScript 檔案',
        },
        json: {
          label: 'JSON',
          description: 'JSON 設定檔案',
        },
        css: {
          label: 'CSS',
          description: 'CSS 樣式檔案',
        },
        all: {
          label: '全部',
          description: '顯示所有檔案',
        },
      },
    },
  },
};

export default chat;
