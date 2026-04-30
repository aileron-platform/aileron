import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LocalizedMonacoEditor } from './LocalizedMonacoEditor';

const { loaderConfigMock, currentLanguageMock } = vi.hoisted(() => ({
  loaderConfigMock: vi.fn(),
  currentLanguageMock: vi.fn(() => 'zh-TW'),
}));

vi.mock('@monaco-editor/react', () => ({
  default: () => <div data-testid="mock-monaco-editor" />,
  loader: {
    config: loaderConfigMock,
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    state: {
      currentLanguage: currentLanguageMock(),
    },
  }),
}));

describe('LocalizedMonacoEditor', () => {
  beforeEach(() => {
    loaderConfigMock.mockReset();
    currentLanguageMock.mockReset();
    currentLanguageMock.mockReturnValue('zh-TW');
  });

  it('configures Traditional Chinese before rendering Monaco', () => {
    render(<LocalizedMonacoEditor />);

    expect(loaderConfigMock).toHaveBeenCalledWith({
      'vs/nls': {
        availableLanguages: {
          '*': 'zh-tw',
        },
      },
    });
  });

  it('maps non Traditional Chinese locale to English', () => {
    currentLanguageMock.mockReturnValue('en');

    render(<LocalizedMonacoEditor />);

    expect(loaderConfigMock).toHaveBeenCalledWith({
      'vs/nls': {
        availableLanguages: {
          '*': 'en',
        },
      },
    });
  });
});
