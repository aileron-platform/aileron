import React from 'react';
import userEvent from '@testing-library/user-event';
import { act, fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsPage from './SettingsPage';
import { claudeCodeApi } from '../services/claudeCodeApi';
import { I18nProvider } from '@/app/providers/I18nProvider';

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
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
    theme,
    onChange,
    onMount,
  }: {
    value?: string;
    theme?: string;
    onChange?: (value?: string) => void;
    onMount?: (editor: unknown, monaco: unknown) => void;
  }) => {
    React.useEffect(() => {
      onMount?.({}, {
        languages: {
          json: {
            jsonDefaults: {
              setDiagnosticsOptions: vi.fn(),
            },
          },
        },
      });
    }, [onMount]);

    return (
      <textarea
        aria-label="json-editor"
        data-theme={theme}
        value={value ?? ''}
        onChange={(event) => onChange?.(event.target.value)}
      />
    );
  },
}));

vi.mock('../services/claudeCodeApi', () => ({
  claudeCodeApi: {
    getRawSettings: vi.fn(),
    updateRawSettings: vi.fn(),
  },
}));

const getRawSettingsMock = vi.mocked(claudeCodeApi.getRawSettings);
const updateRawSettingsMock = vi.mocked(claudeCodeApi.updateRawSettings);

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

describe('Claude SettingsPage JSON editor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.classList.remove('dark');
    installSelectPolyfills();
    getRawSettingsMock.mockResolvedValue({ content: { model: 'claude-sonnet-4-5' } });
    updateRawSettingsMock.mockImplementation(async (_baseUrl, _workspaceId, _scope, content) => ({
      content,
    }));
  });

  it('loads the local scope by default and switches scopes', async () => {
    const user = userEvent.setup();
    getRawSettingsMock
      .mockResolvedValueOnce({ content: { model: 'local-model' } })
      .mockResolvedValueOnce({ content: { model: 'user-model' } });

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText('json-editor')).toHaveValue('{\n  "model": "local-model"\n}');
    });

    expect(screen.queryByText(/workspace\.claudeCode\.settings/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'User' }));

    await waitFor(() => {
      expect(screen.getByLabelText('json-editor')).toHaveValue('{\n  "model": "user-model"\n}');
    });
    expect(getRawSettingsMock).toHaveBeenNthCalledWith(1, 'http://runtime.test', 'ws-1', 'local');
    expect(getRawSettingsMock).toHaveBeenNthCalledWith(2, 'http://runtime.test', 'ws-1', 'user');
  });

  it('renders an empty object when raw settings content is null', async () => {
    getRawSettingsMock.mockResolvedValueOnce({ content: null as never });

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText('json-editor')).toHaveValue('{}');
    });
    expect(screen.queryByText(/workspace\.claudeCode\.settings/)).not.toBeInTheDocument();
  });

  it('uses the resolved app theme for the editor', async () => {
    document.documentElement.classList.add('dark');

    renderPage();

    expect(await screen.findByLabelText('json-editor')).toHaveAttribute('data-theme', 'vs-dark');

    act(() => {
      document.documentElement.classList.remove('dark');
    });

    await waitFor(() => {
      expect(screen.getByLabelText('json-editor')).toHaveAttribute('data-theme', 'vs');
    });
  });

  it('enables save only when JSON is dirty and valid', async () => {
    renderPage();

    const editor = await screen.findByLabelText('json-editor');
    const saveButton = screen.getByRole('button', { name: /Save settings/ });

    await waitFor(() => {
      expect(saveButton).toBeDisabled();
    });

    fireEvent.change(editor, { target: { value: '{\n  "model": "updated"\n}' } });

    expect(saveButton).toBeEnabled();

    await act(async () => {
      fireEvent.click(saveButton);
    });

    expect(updateRawSettingsMock).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'local',
      { model: 'updated' },
    );
    await waitFor(() => {
      expect(saveButton).toBeDisabled();
    });
  });

  it('shows parse errors and disables save for invalid JSON', async () => {
    renderPage();

    const editor = await screen.findByLabelText('json-editor');
    const saveButton = screen.getByRole('button', { name: /Save settings/ });

    fireEvent.change(editor, { target: { value: '{ invalid' } });

    expect(screen.getByText('The editor contains invalid JSON.')).toBeInTheDocument();
    expect(saveButton).toBeDisabled();
  });

  it('confirms before discarding dirty changes on scope switch', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderPage();

    const editor = await screen.findByLabelText('json-editor');
    fireEvent.change(editor, { target: { value: '{\n  "model": "dirty"\n}' } });

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Project' }));

    expect(confirmSpy).toHaveBeenCalledWith('Discard unsaved settings changes?');
    expect(getRawSettingsMock).toHaveBeenCalledTimes(1);

    confirmSpy.mockReturnValue(true);
    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Project' }));

    await waitFor(() => {
      expect(getRawSettingsMock).toHaveBeenCalledTimes(2);
    });
    expect(getRawSettingsMock).toHaveBeenLastCalledWith('http://runtime.test', 'ws-1', 'project');
  });
});
