const browser = {
  title: 'Chrome Browser',
  actions: {
    reload: 'Reload',
    retry: 'Retry',
    restartContainer: 'Restart Container',
    fullscreen: {
      enter: 'Enter full screen browser',
      exit: 'Exit full screen browser',
    },
  },
  extensionPairing: {
    action: 'Connect browser extension',
    connecting: 'Connecting extension...',
    success: {
      title: 'Browser extension pairing started',
      description: 'The extension accepted this workspace pairing request.',
    },
    error: {
      title: 'Browser extension pairing failed',
      description:
        'The extension could not accept this workspace. Confirm that the configured extension is installed and try again.',
    },
  },
  loading: 'Loading...',
  connecting: 'Connecting...',
  connectivity: {
    preparing: 'Preparing a verified browser connection...',
    unavailable: 'Browser connectivity verification is temporarily unavailable.',
    state: {
      pending: 'Verifying connectivity',
      ready: 'Connectivity ready',
      degraded: 'Connectivity degraded but available',
      not_ready: 'Connectivity not ready',
      unavailable: 'Connectivity verification unavailable',
    },
  },
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
    cannotConnect: 'Cannot connect to browser, please check if Chrome container is running',
    securityFailure: 'VNC security verification failed',
    noWorkspace: 'Workspace information not found',
    credentialUnavailable: 'Browser access credential is unavailable',
    recoveryExhausted: 'The browser connection could not recover within the retry limit.',
    nekoConnectionFailed: 'Neko connection failed',
    nekoConnectionTimeout: 'Browser connection timed out',
    nekoIceServerUnreachable: 'Cannot reach the TURN server. Check the network configuration.',
    nekoWebsocketFailed: 'Neko WebSocket connection failed',
    nekoWebrtcFailed: 'Browser video connection failed',
    nekoDataChannelFailed: 'Browser input connection failed',
  },
};

export default browser;
