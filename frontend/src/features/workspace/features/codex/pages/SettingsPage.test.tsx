import React from 'react';
import userEvent from '@testing-library/user-event';
import { act, fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { I18nProvider } from '@/app/providers/I18nProvider';
import SettingsPage from './SettingsPage';
import { codexSettingsApi } from '../services/codexSettingsApi';

const toastMock = vi.fn();

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.test',
      isLoading: false,
      error: null,
    },
  }),
}));

vi.mock('@/shared/components/monaco/LocalizedMonacoEditor', () => ({
  LocalizedMonacoEditor: ({
    value,
    language,
    theme,
    onChange,
  }: {
    value?: string;
    language?: string;
    theme?: string;
    onChange?: (value?: string) => void;
  }) => (
    <textarea
      aria-label="toml-editor"
      data-language={language}
      data-theme={theme}
      value={value ?? ''}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

vi.mock('../services/codexSettingsApi', () => ({
  codexSettingsApi: {
    getRawConfig: vi.fn(),
    updateRawConfig: vi.fn(),
  },
}));

const getRawConfigMock = vi.mocked(codexSettingsApi.getRawConfig);
const updateRawConfigMock = vi.mocked(codexSettingsApi.updateRawConfig);

const renderPage = () => render(
  <I18nProvider>
    <SettingsPage />
  </I18nProvider>,
);

const installSelectPolyfills = () => {
  [Element.prototype, HTMLElement.prototype].forEach((prototype) => {
    Object.defineProperty(prototype, 'scrollIntoView', {
      configurable: true,
      value: () => undefined,
    });
    Object.defineProperty(prototype, 'hasPointerCapture', {
      configurable: true,
      value: () => false,
    });
    Object.defineProperty(prototype, 'setPointerCapture', {
      configurable: true,
      value: () => undefined,
    });
    Object.defineProperty(prototype, 'releasePointerCapture', {
      configurable: true,
      value: () => undefined,
    });
  });
};

describe('Codex SettingsPage TOML editor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.classList.remove('dark');
    installSelectPolyfills();
    getRawConfigMock.mockResolvedValue({
      workspaceId: 'ws-1',
      layer: 'user',
      content: 'model = "gpt-5.3-codex"\n',
    });
    updateRawConfigMock.mockImplementation(async (_baseUrl, _workspaceId, layer, content) => ({
      workspaceId: 'ws-1',
      layer,
      content,
    }));
  });

  it('loads the user layer by default and switches layers', async () => {
    const user = userEvent.setup();
    getRawConfigMock
      .mockResolvedValueOnce({ workspaceId: 'ws-1', layer: 'user', content: 'model = "user"\n' })
      .mockResolvedValueOnce({ workspaceId: 'ws-1', layer: 'project', content: 'model = "project"\n' });

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText('toml-editor')).toHaveValue('model = "user"\n');
    });
    expect(screen.getByLabelText('toml-editor')).toHaveAttribute('data-language', 'ini');
    expect(screen.queryByText(/workspace\.codex\.settings/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Project' }));

    await waitFor(() => {
      expect(screen.getByLabelText('toml-editor')).toHaveValue('model = "project"\n');
    });
    expect(getRawConfigMock).toHaveBeenNthCalledWith(1, 'http://runtime.test', 'ws-1', 'user');
    expect(getRawConfigMock).toHaveBeenNthCalledWith(2, 'http://runtime.test', 'ws-1', 'project');
  });

  it('enables save only when TOML is dirty and clears dirty state after saving', async () => {
    renderPage();

    const editor = await screen.findByLabelText('toml-editor');
    const saveButton = screen.getByRole('button', { name: /Save settings/ });

    await waitFor(() => {
      expect(saveButton).toBeDisabled();
    });

    fireEvent.change(editor, { target: { value: 'model = "updated"\n' } });

    expect(saveButton).toBeEnabled();

    await act(async () => {
      fireEvent.click(saveButton);
    });

    expect(updateRawConfigMock).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'user',
      'model = "updated"\n',
    );
    await waitFor(() => {
      expect(saveButton).toBeDisabled();
    });
  });

  it('confirms before discarding dirty changes on layer switch', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderPage();

    const editor = await screen.findByLabelText('toml-editor');
    fireEvent.change(editor, { target: { value: 'model = "dirty"\n' } });

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Project' }));

    expect(confirmSpy).toHaveBeenCalledWith('Discard unsaved settings changes?');
    expect(getRawConfigMock).toHaveBeenCalledTimes(1);

    confirmSpy.mockReturnValue(true);
    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Project' }));

    await waitFor(() => {
      expect(getRawConfigMock).toHaveBeenCalledTimes(2);
    });
    expect(getRawConfigMock).toHaveBeenLastCalledWith('http://runtime.test', 'ws-1', 'project');
  });

  it('shows a localized save failure toast and keeps the draft content', async () => {
    updateRawConfigMock.mockRejectedValueOnce(new Error('invalid TOML'));
    renderPage();

    const editor = await screen.findByLabelText('toml-editor');
    fireEvent.change(editor, { target: { value: 'model = [\n' } });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Save settings/ }));
    });

    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
      variant: 'destructive',
      title: 'Unable to save Codex settings.',
      description: 'invalid TOML',
    }));
    expect(editor).toHaveValue('model = [\n');
  });

  it('uses the resolved app theme for the editor', async () => {
    document.documentElement.classList.add('dark');

    renderPage();

    expect(await screen.findByLabelText('toml-editor')).toHaveAttribute('data-theme', 'vs-dark');

    act(() => {
      document.documentElement.classList.remove('dark');
    });

    await waitFor(() => {
      expect(screen.getByLabelText('toml-editor')).toHaveAttribute('data-theme', 'vs');
    });
  });
});
