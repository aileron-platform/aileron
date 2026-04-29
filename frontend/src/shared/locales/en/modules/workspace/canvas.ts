const canvas = {
  header: {
    title: 'Canvas',
    actions: {
      fullscreen: {
        enter: 'Enter full screen canvas',
        exit: 'Exit full screen canvas',
      },
    },
    loading: 'Loading Canvas...',
  },
  sessionResult: {
    title: 'Session Result',
    emptyMessage: 'No session results available in Canvas',
  },
  webCanvas: {
    title: 'Web Canvas',
    routePlaceholder: 'Select or enter a route',
    iframeTitle: 'Workspace Web Canvas',
    loading: 'Loading Canvas...',
    types: {
      html: 'HTML',
      nextjs: 'Next.js',
      default: 'Default',
    },
    manifest: {
      missing: 'No manifest',
      valid: 'Manifest ready',
      invalid: 'Manifest error',
    },
    error: {
      title: 'Canvas unavailable',
      defaultMessage: 'Canvas is not ready. Sync or reset the Canvas and try again.',
    },
    statusNotice: {
      title: 'Canvas status',
      defaultDescription: 'No directly renderable Web Canvas content has been detected yet.',
      missingManifestDescription: 'No Canvas route manifest was found, so Canvas is shown in its default state.',
      invalidManifestDescription: 'The Canvas route manifest has an issue. Fix it and sync Canvas again.',
      details: 'Type: {{type}} · Manifest: {{manifest}}',
    },
    actions: {
      missingWorkspace: 'Workspace information is incomplete.',
      unknownError: 'The Canvas action failed.',
      errorTitle: 'Canvas action failed',
      sync: {
        label: 'Sync Canvas',
        successTitle: 'Canvas synced',
        successDescription: 'The Canvas snapshot has been updated.',
        errorTitle: 'Canvas sync failed',
      },
    },
    review: {
      toolbar: {
        toggle: 'Select Canvas elements to add edit instructions',
      },
      bridgeWaiting: 'Preparing selection mode...',
      form: {
        title: 'Selected target edit instruction',
        placeholder: 'Describe what should change in this element or area.',
        create: 'Add edit instruction',
        cancel: 'Cancel',
        close: 'Close edit instruction form',
        dragHandle: 'Move edit instruction form',
      },
      target: {
        area: 'Selected area',
        multi: '{{count}} selected elements',
      },
      status: {
        open: 'Open',
        seen: 'Sent',
        applied: 'Applied',
        dismissed: 'Dismissed',
      },
      notes: {
        title: 'Canvas edit instructions',
        sendToAi: 'Send to AI',
        sendAllToAi: 'Send all to AI',
        delete: 'Delete instruction',
        expand: 'Expand Canvas edit instructions',
        collapse: 'Collapse Canvas edit instructions',
      },
      toast: {
        createdTitle: 'Edit instruction added',
        createdDescription: 'The selected Canvas target and edit instruction were saved.',
      },
      errors: {
        bridge: 'Canvas selection mode could not read this preview.',
        missingTarget: 'Select an element or area first.',
        emptyInstruction: 'Enter an instruction before adding it.',
        createFailed: 'Could not add the edit instruction.',
      },
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
      cannotConnect: 'Cannot connect to browser canvas, please check if Chrome container is running',
      securityFailure: 'VNC security verification failed',
      noWorkspace: 'Workspace information not found',
      nekoConnectionFailed: 'Neko connection failed',
      nekoWebsocketFailed: 'Neko WebSocket connection failed',
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

export default canvas;
