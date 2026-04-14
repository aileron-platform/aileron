const preview = {
  header: {
    title: 'Preview',
    actions: {
      fullscreen: {
        enter: 'Enter full screen preview',
        exit: 'Exit full screen preview',
      },
      refresh: 'Refresh',
      menu: 'Menu',
    },
  },
  sessionResult: {
    title: 'Session Result',
    emptyMessage: 'No session results available to preview',
  },
  webPreview: {
    title: 'Web Preview',
    urlPlaceholder: 'Enter the URL to load, e.g. https://localhost:5173',
    iframeTitle: 'Workspace live preview',
    notFound: {
      title: 'Next.js Project Not Found',
      defaultMessage: 'No Next.js project found in workspace',
    },
  },
  browser: {
    title: 'Chrome Browser',
    actions: {
      reload: 'Reload',
      retry: 'Retry',
      restartContainer: 'Restart Container',
    },
    loading: 'Loading...',
    connecting: 'Connecting...',
    notReady: {
      title: 'Browser Not Started',
      description: 'Chrome browser container is not available',
      hint: 'Tip: Chrome browser starts with the workspace runtime',
    },
    restart: {
      started: 'Restarting Chrome',
      inProgress: 'Restarting Chrome Browser',
      description: 'Chrome container restart has started, please wait...',
      failed: 'Restart Failed',
    },
    error: {
      status: 'Browser status error',
      notStarted: 'Browser not started',
      connection: 'Cannot connect to browser',
      connectionFailed: 'Connection Failed',
      cannotConnect: 'Cannot connect to browser preview, please check if Chrome container is running',
      securityFailure: 'VNC security verification failed',
      noWorkspace: 'Workspace information not found',
    },
  },
  usage: {
    stats: 'Stats',
    totalTokens: 'Total Tokens',
    input: 'Input',
    output: 'Output',
    details: 'Details',
    cost: 'Cost',
    costUnavailable: 'Cost unavailable',
    notAvailable: 'Not available',
    cache: 'Cache',
    tier: 'Service Tier',
    duration: 'Duration',
    provider: 'Provider',
    model: 'Model',
    models: 'Model Breakdown',
    modelCount: '{{count}} models',
    modelCost: 'Cost',
    dialog: {
      title: 'Usage Details',
      description: 'Complete usage statistics for this response',
    },
    cacheRead: 'Read',
    cacheWrite: 'Write',
  },
};

export default preview;
