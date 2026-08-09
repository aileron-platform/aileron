import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  accessBrowser: vi.fn(),
  useNekoStream: vi.fn(),
  useBrowserAccessRecovery: vi.fn(),
  workspaceRuntime: {
    workspaceId: 'e0e4aba0-8442-4851-a9c4-5c45f9e74fb6',
    runtimeStatus: { browserStatus: 'running' },
    browserConnectivity: {
      contractVersion: 'browser-connectivity/v1',
      state: 'degraded',
      admission: 'allowed',
      reason: 'FrontendTURNPathNotReady',
      backendState: 'ready',
      frontendState: 'degraded',
    },
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock('@/shared/components/layout/FeatureHeader', () => ({
  FeatureHeader: ({ actions }: { actions?: ReactNode }) => (
    <div data-testid="feature-header">{actions}</div>
  ),
}));

vi.mock('./components/BrowserExtensionPairingButton', () => ({
  BrowserExtensionPairingButton: () => null,
}));

vi.mock('../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: mocks.workspaceRuntime,
  }),
}));

vi.mock('../../api/workspaceLifecycleApi', () => ({
  workspaceLifecycleApi: {
    accessBrowser: mocks.accessBrowser,
    restartComponent: vi.fn(),
  },
}));

vi.mock('./hooks/useNekoStream', () => ({
  useNekoStream: mocks.useNekoStream,
}));

vi.mock('./hooks/useBrowserAccessRecovery', () => ({
  useBrowserAccessRecovery: mocks.useBrowserAccessRecovery,
}));

import { BrowserPage } from './BrowserPage';

describe('BrowserPage', () => {
  const workspaceId = 'e0e4aba0-8442-4851-a9c4-5c45f9e74fb6';

  beforeEach(() => {
    mocks.accessBrowser.mockReset();
    mocks.useNekoStream.mockReset();
    mocks.useBrowserAccessRecovery.mockReset();
    mocks.useBrowserAccessRecovery.mockReturnValue({
      access: {
        browserUrl: `/workspaces/${workspaceId}/browser`,
        password: 'derived-user-password',
        credentialRevision: 7,
        iceServers: [],
      },
      generation: 3,
      state: 'connected',
      errorKey: null,
      retry: vi.fn(),
    });
    mocks.useNekoStream.mockReturnValue({
      connectionState: 'disconnected',
      isConnected: false,
      error: null,
      videoRef: { current: null },
      audioRef: { current: null },
    });
  });

  it('passes recovered access generation and credential to Neko', async () => {
    mocks.workspaceRuntime.workspaceId = workspaceId;
    render(<BrowserPage />);

    expect(mocks.useBrowserAccessRecovery).toHaveBeenCalledWith({
      workspaceId,
      enabled: true,
      connectionState: 'disconnected',
      requestAccess: mocks.accessBrowser,
    });
    await waitFor(() => {
      expect(mocks.useNekoStream).toHaveBeenLastCalledWith({
        url: `ws://${window.location.host}/workspaces/${workspaceId}/browser/ws`,
        password: 'derived-user-password',
        iceServers: [],
        displayname: 'user',
        generation: 3,
      });
    });
    expect(screen.getByTestId('browser-connectivity-state')).toHaveTextContent(
      'workspace.browser.connectivity.state.degraded'
    );
  });
});
