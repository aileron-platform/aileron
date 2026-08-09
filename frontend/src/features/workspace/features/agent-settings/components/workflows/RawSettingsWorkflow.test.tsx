import React from 'react';
import userEvent from '@testing-library/user-event';
import {
  createTestQueryClient,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RawSettingsWorkflow from './RawSettingsWorkflow';
import type { RawSettingsSource } from '../../model/rawSettingsSource';

const workspaceRuntimeState = vi.hoisted(() => ({
  runtimeBaseUrl: 'http://runtime.test',
  workspaceId: 'ws-1',
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: workspaceRuntimeState.runtimeBaseUrl,
      workspaceId: workspaceRuntimeState.workspaceId,
      isLoading: false,
      error: null,
    },
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock('../SettingsDocumentEditor', () => ({
  SettingsDocumentEditor: ({
    value,
    onChange,
  }: {
    value: string;
    onChange: (value: string) => void;
  }) => (
    <textarea
      aria-label="raw-settings-editor"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

describe('RawSettingsWorkflow', () => {
  const source: RawSettingsSource = {
    format: 'json',
    scopes: [
      { id: 'project', labelKey: 'scope.project' },
      { id: 'user', labelKey: 'scope.user' },
    ],
    load: vi.fn(),
    save: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    workspaceRuntimeState.runtimeBaseUrl = 'http://runtime.test';
    workspaceRuntimeState.workspaceId = 'ws-1';
    vi.mocked(source.load).mockResolvedValue({ content: '{\n  "mode": "test"\n}' });
    vi.mocked(source.save).mockResolvedValue(undefined);
  });

  it('loads the default scope content and saves edited content', async () => {
    const user = userEvent.setup();
    render(
      <RawSettingsWorkflow
        queryKey={['raw-settings-test']}
        source={source}
        titleKey="settings.title"
        scopeLabelKey="settings.scope"
        dirtyLabelKey="settings.dirty"
        refreshLabelKey="settings.refresh"
        saveLabelKey="settings.save"
        savingLabelKey="settings.saving"
        saveSuccessKey="settings.saved"
        saveFailedKey="settings.failed"
        loadFailedKey="settings.loadFailed"
        unsavedChangesConfirmKey="settings.unsaved"
      />,
    );

    const editor = await screen.findByLabelText('raw-settings-editor');
    await waitFor(() => {
      expect(editor).toHaveValue('{\n  "mode": "test"\n}');
    });
    expect(source.load).toHaveBeenCalledWith('project', expect.any(AbortSignal));

    fireEvent.change(editor, { target: { value: '{"mode":"updated"}' } });
    await user.click(screen.getByRole('button', { name: 'settings.save' }));

    await waitFor(() => {
      expect(source.save).toHaveBeenCalledWith('project', '{"mode":"updated"}');
    });
  });

  it('isolates raw settings cache by Workspace identity', async () => {
    const queryClient = createTestQueryClient();
    queryClient.setQueryDefaults(['raw-settings-test'], { gcTime: Infinity });
    const rendered = render(
      <RawSettingsWorkflow
        queryKey={['raw-settings-test']}
        source={source}
        titleKey="settings.title"
        scopeLabelKey="settings.scope"
        dirtyLabelKey="settings.dirty"
        refreshLabelKey="settings.refresh"
        saveLabelKey="settings.save"
        savingLabelKey="settings.saving"
        saveSuccessKey="settings.saved"
        saveFailedKey="settings.failed"
        loadFailedKey="settings.loadFailed"
        unsavedChangesConfirmKey="settings.unsaved"
      />,
      { queryClient },
    );

    await screen.findByLabelText('raw-settings-editor');
    const firstWorkspaceKey = [
      'raw-settings-test',
      'http://runtime.test',
      'ws-1',
      'project',
    ];
    await waitFor(() => {
      expect(queryClient.getQueryData(firstWorkspaceKey)).toEqual({
        content: '{\n  "mode": "test"\n}',
      });
    });

    workspaceRuntimeState.runtimeBaseUrl = 'http://runtime-2.test';
    workspaceRuntimeState.workspaceId = 'ws-2';
    rendered.rerender(
      <RawSettingsWorkflow
        queryKey={['raw-settings-test']}
        source={source}
        titleKey="settings.title"
        scopeLabelKey="settings.scope"
        dirtyLabelKey="settings.dirty"
        refreshLabelKey="settings.refresh"
        saveLabelKey="settings.save"
        savingLabelKey="settings.saving"
        saveSuccessKey="settings.saved"
        saveFailedKey="settings.failed"
        loadFailedKey="settings.loadFailed"
        unsavedChangesConfirmKey="settings.unsaved"
      />,
    );

    await waitFor(() => {
      expect(source.load).toHaveBeenCalledTimes(2);
    });
    expect(queryClient.getQueryData(firstWorkspaceKey)).toEqual({
      content: '{\n  "mode": "test"\n}',
    });
    const secondWorkspaceKey = [
      'raw-settings-test',
      'http://runtime-2.test',
      'ws-2',
      'project',
    ];
    await waitFor(() => {
      expect(queryClient.getQueryData(secondWorkspaceKey)).toEqual({
        content: '{\n  "mode": "test"\n}',
      });
    });
  });
});
