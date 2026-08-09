import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsGeneralTab } from './SettingsGeneralTab';
import type { UserSettingsGeneral } from '@/shared/types/user';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const generalSettings: UserSettingsGeneral = {
  theme: 'system',
  language: 'zh-TW',
  timezone: 'Asia/Taipei',
  notifications: { desktop: true, email: true, updates: true },
  performance: { autoSave: true, animationsEnabled: true },
  privacy: { analytics: false, crashReports: true, usageData: false },
};

describe('SettingsGeneralTab', () => {
  beforeEach(() => {
    if (!HTMLElement.prototype.hasPointerCapture) {
      HTMLElement.prototype.hasPointerCapture = () => false;
    }
    if (!HTMLElement.prototype.scrollIntoView) {
      HTMLElement.prototype.scrollIntoView = vi.fn();
    }
  });

  it('renders appearance fields with i18n keys', () => {
    render(
      <SettingsGeneralTab
        generalSettings={generalSettings}
        onGeneralSettingsChange={vi.fn()}
        onThemeChange={vi.fn()}
        onLanguageChange={vi.fn()}
      />,
    );

    expect(screen.getByText('pages.settings.sections.appearance.title')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.appearance.theme.label')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.appearance.language.label')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.appearance.timezone.label')).toBeInTheDocument();
  });

  it('dispatches timezone changes without hardcoding labels in the page', async () => {
    const user = userEvent.setup();
    const onGeneralSettingsChange = vi.fn();

    render(
      <SettingsGeneralTab
        generalSettings={generalSettings}
        onGeneralSettingsChange={onGeneralSettingsChange}
        onThemeChange={vi.fn()}
        onLanguageChange={vi.fn()}
      />,
    );

    await user.click(screen.getAllByRole('combobox')[2]);
    await user.click(screen.getByText('pages.settings.sections.appearance.timezone.options.tokyo'));

    expect(onGeneralSettingsChange).toHaveBeenCalledWith({
      ...generalSettings,
      timezone: 'Asia/Tokyo',
    });
  });
});
