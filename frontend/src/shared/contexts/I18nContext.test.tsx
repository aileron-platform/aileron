// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '@/shared/api/apiClient';
import { I18nProvider, useI18n } from './I18nContext';

const Probe = ({ mode }: { mode: 'missing' | 'object-key' }) => {
  const { t } = useI18n();
  const value = mode === 'missing'
    ? t('test.missing.key')
    : (t as (key: unknown, params?: { defaultValue?: string }) => string)({ nested: 'key' });

  return <div data-testid="translation">{value}</div>;
};

const LanguageProbe = () => {
  const { state, changeLanguage, t } = useI18n();

  return (
    <>
      <div data-testid="current-language">{state.currentLanguage}</div>
      <div data-testid="save-label">{t('common.save')}</div>
      <button type="button" onClick={() => void changeLanguage('zh-TW')}>
        Change language
      </button>
    </>
  );
};

const TranslationContractProbe = () => {
  const { t } = useI18n();

  return (
    <>
      <div data-testid="interpolation">{t('common.welcome', { name: 'Ada' })}</div>
      <div data-testid="plural-one">
        {t('workspace.versionControl.commitHistory.fileCount', { count: 1 })}
      </div>
      <div data-testid="plural-other">
        {t('workspace.versionControl.commitHistory.fileCount', { count: 2 })}
      </div>
      <div data-testid="default-value">
        {t('test.missing.default', {
          defaultValue: 'Fallback for {{name}}',
          name: 'Ada',
        })}
      </div>
    </>
  );
};

describe('I18nProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.lang = '';
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    document.documentElement.lang = '';
  });

  it('initializes the saved locale and matching translations', async () => {
    localStorage.setItem('preferred-language', 'zh-TW');

    render(
      <I18nProvider>
        <LanguageProbe />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('current-language')).toHaveTextContent('zh-TW');
    });
    expect(screen.getByTestId('save-label')).toHaveTextContent('\u5132\u5b58');
    expect(document.documentElement.lang).toBe('zh-TW');
  });

  it('persists changeLanguage and updates the document language', async () => {
    render(
      <I18nProvider>
        <LanguageProbe />
      </I18nProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Change language' }));

    await waitFor(() => {
      expect(screen.getByTestId('current-language')).toHaveTextContent('zh-TW');
    });
    expect(localStorage.getItem('preferred-language')).toBe('zh-TW');
    expect(document.documentElement.lang).toBe('zh-TW');
    expect(screen.getByTestId('save-label')).toHaveTextContent('\u5132\u5b58');
  });

  it('supports interpolation, plural forms, and interpolated default values', async () => {
    render(
      <I18nProvider>
        <TranslationContractProbe />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(document.documentElement.lang).toBe('en');
    });
    expect(screen.getByTestId('interpolation')).toHaveTextContent('Welcome, Ada');
    expect(screen.getByTestId('plural-one')).toHaveTextContent('1 file');
    expect(screen.getByTestId('plural-other')).toHaveTextContent('2 files');
    expect(screen.getByTestId('default-value')).toHaveTextContent('Fallback for Ada');
  });

  it('registers the current locale for API request headers and unregisters on unmount', async () => {
    const client = new ApiClient();
    const { unmount } = render(
      <I18nProvider>
        <LanguageProbe />
      </I18nProvider>,
    );

    await waitFor(async () => {
      expect((await client.getRequestHeaders())['X-Language']).toBe('en');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Change language' }));

    await waitFor(async () => {
      expect((await client.getRequestHeaders())['X-Language']).toBe('zh-TW');
    });

    unmount();
    expect(await client.getRequestHeaders()).not.toHaveProperty('X-Language');
  });

  it('logs missing string keys with the key in the message', async () => {
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    render(
      <I18nProvider>
        <Probe mode="missing" />
      </I18nProvider>,
    );

    expect(screen.getByTestId('translation')).toHaveTextContent('test.missing.key');
    await waitFor(() => {
      expect(consoleWarn).toHaveBeenCalledWith(
        expect.stringContaining(
          '[I18nProvider] Translation not found for key: test.missing.key',
        ),
      );
    });
  });

  it('does not render object keys as [object Object]', async () => {
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    render(
      <I18nProvider>
        <Probe mode="object-key" />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(document.documentElement.lang).toBe('en');
    });
    expect(screen.getByTestId('translation').textContent).toBe('');
    expect(consoleWarn).toHaveBeenCalledWith(
      expect.stringContaining('[I18nProvider] Translation key must be a string'),
      { keyType: 'object' },
    );
  });
});
