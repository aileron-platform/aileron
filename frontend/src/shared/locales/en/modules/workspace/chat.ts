const chat = {
  dialogs: {
    fileChooser: {
      title: 'Attach workspace files',
      searchPlaceholder: 'Search files by name or path...',
      projectPathLabel: 'Project path: {{path}}',
      quickFilterTitle: 'Quick filters',
      currentFilter: 'Current filter: {{description}}',
      noFiles: 'No files available.',
      noMatches: 'No files match your current filters.',
      foundCount: 'Found {{count}} file(s)',
      filterPresets: {
        markdown: {
          label: 'Markdown',
          description: 'All Markdown files',
        },
        testMarkdown: {
          label: 'Test MD',
          description: 'Markdown files related to tests',
        },
        typescript: {
          label: 'TypeScript',
          description: 'TypeScript source files',
        },
        react: {
          label: 'React',
          description: 'React TypeScript files',
        },
        javascript: {
          label: 'JavaScript',
          description: 'JavaScript files',
        },
        json: {
          label: 'JSON',
          description: 'JSON configuration files',
        },
        css: {
          label: 'CSS',
          description: 'CSS stylesheets',
        },
        all: {
          label: 'All',
          description: 'All files',
        },
      },
    },
  },
};

export default chat;
