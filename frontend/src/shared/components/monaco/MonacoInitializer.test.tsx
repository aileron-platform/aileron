import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MonacoInitializer } from './MonacoInitializer';
import { disableMonacoDiagnostics } from './disableMonacoDiagnostics';

const { loaderConfigMock, loaderInitMock, currentLanguageMock } = vi.hoisted(() => ({
  loaderConfigMock: vi.fn(),
  loaderInitMock: vi.fn(),
  currentLanguageMock: vi.fn(() => 'zh-TW'),
}));

vi.mock('@monaco-editor/react', () => ({
  loader: {
    config: loaderConfigMock,
    init: loaderInitMock,
  },
}));

vi.mock('../../hooks/useI18n', () => ({
  useI18n: () => ({
    state: {
      currentLanguage: currentLanguageMock(),
    },
  }),
}));

vi.mock('./disableMonacoDiagnostics', () => ({
  disableMonacoDiagnostics: vi.fn(),
}));

describe('MonacoInitializer', () => {
  beforeEach(() => {
    loaderConfigMock.mockReset();
    loaderInitMock.mockReset();
    currentLanguageMock.mockReset();
    currentLanguageMock.mockReturnValue('zh-TW');
    vi.mocked(disableMonacoDiagnostics).mockReset();
  });

  it('keeps Monaco localization config and disables diagnostics after loader init', async () => {
    const monaco = { languages: {}, editor: {} };
    loaderInitMock.mockResolvedValue(monaco);

    render(<MonacoInitializer />);

    expect(loaderConfigMock).toHaveBeenCalledWith({
      'vs/nls': {
        availableLanguages: {
          '*': 'zh-tw',
        },
      },
    });

    await waitFor(() => {
      expect(disableMonacoDiagnostics).toHaveBeenCalledWith(monaco);
    });
  });

  it('maps non Traditional Chinese locale to English while keeping diagnostics disabled', async () => {
    const monaco = { languages: {}, editor: {} };
    currentLanguageMock.mockReturnValue('en');
    loaderInitMock.mockResolvedValue(monaco);

    render(<MonacoInitializer />);

    expect(loaderConfigMock).toHaveBeenCalledWith({
      'vs/nls': {
        availableLanguages: {
          '*': 'en',
        },
      },
    });

    await waitFor(() => {
      expect(disableMonacoDiagnostics).toHaveBeenCalledWith(monaco);
    });
  });
});
