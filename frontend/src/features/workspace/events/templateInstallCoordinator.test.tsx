import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceTemplateInstallRefresh } from './templateInstallCoordinator';
import { dispatchWorkspaceTemplateInstalledEvent } from './templateInstallEvents';

describe('template install refresh coordinator', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('只刷新相同 workspace 且受影響的 feature', async () => {
    const refreshSlashCommands = vi.fn();
    const refreshMcp = vi.fn();
    const refreshOtherWorkspace = vi.fn();

    renderHook(() =>
      useWorkspaceTemplateInstallRefresh({
        workspaceId: 'ws-1',
        features: ['slashCommands'],
        onRefresh: refreshSlashCommands,
      }),
    );
    renderHook(() =>
      useWorkspaceTemplateInstallRefresh({
        workspaceId: 'ws-1',
        features: ['mcp'],
        onRefresh: refreshMcp,
      }),
    );
    renderHook(() =>
      useWorkspaceTemplateInstallRefresh({
        workspaceId: 'ws-2',
        features: ['slashCommands'],
        onRefresh: refreshOtherWorkspace,
      }),
    );

    dispatchWorkspaceTemplateInstalledEvent({
      workspaceId: 'ws-1',
      templateId: 'tpl-1',
      installedFeatures: ['slashCommands', 'skills'],
    });

    await waitFor(() => {
      expect(refreshSlashCommands).toHaveBeenCalledTimes(1);
    });
    expect(refreshMcp).not.toHaveBeenCalled();
    expect(refreshOtherWorkspace).not.toHaveBeenCalled();
  });

  it('dirty editor 只標記 stale 不自動 refresh', async () => {
    const onRefresh = vi.fn();
    const onDeferredRefresh = vi.fn();

    renderHook(() =>
      useWorkspaceTemplateInstallRefresh({
        workspaceId: 'ws-1',
        features: ['claudeMd'],
        onRefresh,
        shouldDeferRefresh: () => true,
        onDeferredRefresh,
      }),
    );

    dispatchWorkspaceTemplateInstalledEvent({
      workspaceId: 'ws-1',
      templateId: 'tpl-2',
      installedFeatures: ['claudeMd'],
    });

    await waitFor(() => {
      expect(onDeferredRefresh).toHaveBeenCalledTimes(1);
    });
    expect(onRefresh).not.toHaveBeenCalled();
  });
});
