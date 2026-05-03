import React from 'react';
import { act } from '@testing-library/react';
import { render, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ClaudeCodeProvider, useClaudeCode } from './ClaudeCodeProvider';
import type { ClaudeDocument } from '../types';

const apiMock = vi.hoisted(() => ({
  listSlashCommands: vi.fn(),
  listOutputStyles: vi.fn(),
  listSubagents: vi.fn(),
  listMemoryDocuments: vi.fn(),
}));
const workspaceRuntimeMock = vi.hoisted(() => ({
  runtimeBaseUrl: 'http://runtime.test',
  workspaceId: 'ws-1',
  error: null as string | null,
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: workspaceRuntimeMock,
  }),
}));

vi.mock('../services/claudeCodeApi', () => ({
  claudeCodeApi: apiMock,
}));

vi.mock('@/features/workspace/events/templateInstallCoordinator', () => ({
  useWorkspaceTemplateInstallRefresh: vi.fn(),
}));

const Probe: React.FC = () => {
  useClaudeCode();
  return null;
};

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
};

const createDocument = (id: string): ClaudeDocument => ({
  id,
  scope: 'project',
  title: id,
  content: '',
});

describe('ClaudeCodeProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspaceRuntimeMock.runtimeBaseUrl = 'http://runtime.test';
    workspaceRuntimeMock.workspaceId = 'ws-1';
    workspaceRuntimeMock.error = null;
    apiMock.listSlashCommands.mockResolvedValue([]);
    apiMock.listOutputStyles.mockResolvedValue([]);
    apiMock.listSubagents.mockResolvedValue([]);
    apiMock.listMemoryDocuments.mockResolvedValue([]);
  });

  it('loads only the active document collection when activated', async () => {
    render(
      <ClaudeCodeProvider isActive activeSubView="slash-commands">
        <Probe />
      </ClaudeCodeProvider>,
    );

    await waitFor(() => expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(1));
    expect(apiMock.listOutputStyles).not.toHaveBeenCalled();
    expect(apiMock.listSubagents).not.toHaveBeenCalled();
    expect(apiMock.listMemoryDocuments).not.toHaveBeenCalled();
  });

  it('reuses a loaded collection when navigating away and back', async () => {
    const { rerender } = render(
      <ClaudeCodeProvider isActive activeSubView="slash-commands">
        <Probe />
      </ClaudeCodeProvider>,
    );

    await waitFor(() => expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(1));

    rerender(
      <ClaudeCodeProvider isActive activeSubView="subagents">
        <Probe />
      </ClaudeCodeProvider>,
    );
    await waitFor(() => expect(apiMock.listSubagents).toHaveBeenCalledTimes(1));

    rerender(
      <ClaudeCodeProvider isActive activeSubView="slash-commands">
        <Probe />
      </ClaudeCodeProvider>,
    );

    await waitFor(() => expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(1));
  });

  it('does not automatically retry a failed lazy load', async () => {
    apiMock.listSlashCommands.mockRejectedValue(new Error('request failed'));

    render(
      <ClaudeCodeProvider isActive activeSubView="slash-commands">
        <Probe />
      </ClaudeCodeProvider>,
    );

    await waitFor(() => expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(1));
    await new Promise((resolve) => {
      window.setTimeout(resolve, 25);
    });
    expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(1);
  });

  it('reloads collections after the workspace changes', async () => {
    const { rerender } = render(
      <ClaudeCodeProvider isActive activeSubView="slash-commands">
        <Probe />
      </ClaudeCodeProvider>,
    );

    await waitFor(() => expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(1));

    workspaceRuntimeMock.workspaceId = 'ws-2';
    rerender(
      <ClaudeCodeProvider isActive activeSubView="slash-commands">
        <Probe />
      </ClaudeCodeProvider>,
    );

    await waitFor(() => expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(2));
    expect(apiMock.listSlashCommands).toHaveBeenLastCalledWith('http://runtime.test', 'ws-2');
  });

  it('ignores stale lazy-load responses from a previous workspace', async () => {
    const firstRequest = createDeferred<ClaudeDocument[]>();
    const secondRequest = createDeferred<ClaudeDocument[]>();
    apiMock.listSlashCommands
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise);
    let currentIds: string[] = [];
    const StateProbe: React.FC = () => {
      currentIds = useClaudeCode().slashCommands.items.map((item) => item.id);
      return null;
    };

    const { rerender } = render(
      <ClaudeCodeProvider isActive activeSubView="slash-commands">
        <StateProbe />
      </ClaudeCodeProvider>,
    );
    await waitFor(() => expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(1));

    workspaceRuntimeMock.workspaceId = 'ws-2';
    rerender(
      <ClaudeCodeProvider isActive activeSubView="slash-commands">
        <StateProbe />
      </ClaudeCodeProvider>,
    );
    await waitFor(() => expect(apiMock.listSlashCommands).toHaveBeenCalledTimes(2));

    await act(async () => {
      firstRequest.resolve([createDocument('ws-1-command')]);
      await firstRequest.promise;
    });
    expect(currentIds).toEqual([]);

    await act(async () => {
      secondRequest.resolve([createDocument('ws-2-command')]);
      await secondRequest.promise;
    });
    await waitFor(() => expect(currentIds).toEqual(['ws-2-command']));
  });
});
