import React from 'react';
import userEvent from '@testing-library/user-event';
import { act, fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { I18nProvider } from '@/app/providers/I18nProvider';
import { ApiError } from '@/shared/api/apiClient';
import SettingsPage from './SettingsPage';
import { geminiSettingsApi } from '../services/geminiSettingsApi';

const toastMock = vi.fn();
const schemaOptionsMock = vi.fn();

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
    onMount,
  }: {
    value?: string;
    language?: string;
    theme?: string;
    onChange?: (value?: string) => void;
    onMount?: (editor: unknown, monaco: unknown) => void;
  }) => {
    React.useEffect(() => {
      onMount?.({}, {
        languages: {
          json: {
            jsonDefaults: {
              setDiagnosticsOptions: schemaOptionsMock,
            },
          },
        },
      });
    }, [onMount]);

    return (
      <textarea
        aria-label="json-editor"
        data-language={language}
        data-theme={theme}
        value={value ?? ''}
        onChange={(event) => onChange?.(event.target.value)}
      />
    );
  },
}));

vi.mock('../services/geminiSettingsApi', () => ({
  geminiSettingsApi: {
    getRawSettings: vi.fn(),
    updateRawSettings: vi.fn(),
  },
}));

const getRawSettingsMock = vi.mocked(geminiSettingsApi.getRawSettings);
const updateRawSettingsMock = vi.mocked(geminiSettingsApi.updateRawSettings);

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

describe('Gemini SettingsPage JSON editor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.classList.remove('dark');
    installSelectPolyfills();
    getRawSettingsMock.mockResolvedValue({
      content: { model: 'gemini-2.5-pro' },
    });
    updateRawSettingsMock.mockImplementation(async (_baseUrl, _workspaceId, _scope, content) => ({
      content,
    }));
  });

  it('loads the user scope by default, configures Gemini schema, and switches scopes', async () => {
    const user = userEvent.setup();
    getRawSettingsMock
      .mockResolvedValueOnce({ content: { model: 'user-model' } })
      .mockResolvedValueOnce({ content: { model: 'project-model' } });

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText('json-editor')).toHaveValue('{\n  "model": "user-model"\n}');
    });
    expect(screen.getByLabelText('json-editor')).toHaveAttribute('data-language', 'json');
    expect(schemaOptionsMock).toHaveBeenCalledWith(expect.objectContaining({
      schemas: [expect.objectContaining({
        uri: 'https://raw.githubusercontent.com/google-gemini/gemini-cli/main/schemas/settings.schema.json',
      })],
    }));
    expect(screen.queryByText(/workspace\.gemini\.settings/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Project' }));

    await waitFor(() => {
      expect(screen.getByLabelText('json-editor')).toHaveValue('{\n  "model": "project-model"\n}');
    });
    expect(getRawSettingsMock).toHaveBeenNthCalledWith(1, 'http://runtime.test', 'ws-1', 'user');
    expect(getRawSettingsMock).toHaveBeenNthCalledWith(2, 'http://runtime.test', 'ws-1', 'project');
  });

  it('enables save only when JSON is dirty and valid, then clears dirty state after saving', async () => {
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
      'user',
      { model: 'updated' },
    );
    await waitFor(() => {
      expect(saveButton).toBeDisabled();
    });
  });

  it('disables save and displays a parse error for invalid JSON', async () => {
    renderPage();

    const editor = await screen.findByLabelText('json-editor');
    const saveButton = screen.getByRole('button', { name: /Save settings/ });

    fireEvent.change(editor, { target: { value: '{' } });

    expect(saveButton).toBeDisabled();
    expect(screen.getByText('The editor contains invalid JSON.')).toBeInTheDocument();
  });

  it('renders an empty object without a load failure when the settings file is missing', async () => {
    getRawSettingsMock.mockRejectedValueOnce(
      new ApiError('settings.json not found', 404, 'GEMINI_SETTINGS_NOT_FOUND'),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText('json-editor')).toHaveValue('{}');
    });
    expect(screen.queryByText('Unable to load Gemini settings.')).not.toBeInTheDocument();
  });

  it('treats a generic not found response as an empty settings file', async () => {
    getRawSettingsMock.mockRejectedValueOnce(new ApiError('Not Found', 404));

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText('json-editor')).toHaveValue('{}');
    });
    expect(screen.queryByText('Unable to load Gemini settings.')).not.toBeInTheDocument();
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
  });
});
