import { render, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import React from 'react';
import AgentsMdPage from './AgentsMdPage';
import { ApiError } from '@/shared/api/apiClient';
import { getAgentToolConfig } from '../utils';

const toastMock = vi.fn();
const getAgentsMdMock = vi.fn();

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'https://runtime.test',
      workspaceId: 'ws-1',
      isLoading: false,
      error: null,
    },
  }),
}));

vi.mock('@/features/workspace/events/templateInstallCoordinator', () => ({
  useWorkspaceTemplateInstallRefresh: vi.fn(),
}));

vi.mock('../services/agentSettingsApi', () => ({
  createAgentSettingsApi: () => ({
    getAgentsMd: getAgentsMdMock,
    updateAgentsMd: vi.fn(),
  }),
}));

vi.mock('@/shared/components/document-workflow', () => ({
  MarkdownDocumentShell: ({ value, statusMessage }: { value: string; statusMessage?: React.ReactNode }) => (
    <div>
      <div data-testid="content">{value}</div>
      <div data-testid="status">{statusMessage ?? ''}</div>
    </div>
  ),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params && 'defaultValue' in params) return String(params.defaultValue);
      return key;
    },
  }),
}));

const claudeConfig = getAgentToolConfig('claude');

describe('AgentsMdPage 404 handling', () => {
  beforeEach(() => {
    toastMock.mockReset();
    getAgentsMdMock.mockReset();
  });

  it('does not show loadFailed toast when API returns ApiError 404', async () => {
    // 後端對 CLAUDE.md 不存在會回 404，且 detail 為 object，errorMessage 不含 "404" 字串。
    getAgentsMdMock.mockRejectedValue(
      new ApiError('Claude.md not found', 404, '404_NOT_FOUND'),
    );

    render(<AgentsMdPage config={claudeConfig} />);

    await waitFor(() => {
      expect(getAgentsMdMock).toHaveBeenCalled();
    });

    // 給 setState 一個 microtask 機會
    await Promise.resolve();

    expect(toastMock).not.toHaveBeenCalled();
  });

  it('still shows loadFailed toast when API returns non-404 ApiError (e.g. 500)', async () => {
    getAgentsMdMock.mockRejectedValue(
      new ApiError('boom', 500, 'INTERNAL_SERVER_ERROR'),
    );

    render(<AgentsMdPage config={claudeConfig} />);

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(
        expect.objectContaining({ variant: 'destructive' }),
      );
    });
  });

  it('does not show loadFailed toast when legacy error message contains "404"', async () => {
    // Gemini/OpenCode/Codex 後端 message 含 "404:" 前綴，舊的字串檢查路徑也要保留可用。
    getAgentsMdMock.mockRejectedValue(new Error('404: AGENTS.md not found'));

    render(<AgentsMdPage config={claudeConfig} />);

    await waitFor(() => {
      expect(getAgentsMdMock).toHaveBeenCalled();
    });
    await Promise.resolve();

    expect(toastMock).not.toHaveBeenCalled();
  });
});
