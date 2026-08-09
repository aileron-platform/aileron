import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SettingsGitTab } from './SettingsGitTab';
import type { UserSettingsGit } from '@/shared/types/user';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const gitSettings: UserSettingsGit = {
  userName: 'Dev User',
  userEmail: 'dev@example.com',
  signingKey: null,
};

describe('SettingsGitTab', () => {
  it('renders Git fields with i18n keys', () => {
    render(<SettingsGitTab gitSettings={gitSettings} onGitSettingsChange={vi.fn()} />);

    expect(screen.getByText('pages.settings.sections.git.title')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.git.description')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.git.userName.label')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.git.userEmail.label')).toBeInTheDocument();
  });

  it('dispatches Git identity updates', async () => {
    const user = userEvent.setup();
    const onGitSettingsChange = vi.fn();

    render(<SettingsGitTab gitSettings={gitSettings} onGitSettingsChange={onGitSettingsChange} />);

    await user.type(screen.getByDisplayValue('Dev User'), 'x');
    await user.type(screen.getByDisplayValue('dev@example.com'), 'x');

    expect(onGitSettingsChange).toHaveBeenCalledWith({
      ...gitSettings,
      userName: 'Dev Userx',
    });
    expect(onGitSettingsChange).toHaveBeenLastCalledWith({
      ...gitSettings,
      userEmail: 'dev@example.comx',
    });
  });
});
