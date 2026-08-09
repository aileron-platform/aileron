import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SettingsOpenCodeTab } from './SettingsOpenCodeTab';
import type { UserSettingsOpenCode } from '@/shared/types/user';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const opencodeSettings: UserSettingsOpenCode = {
  modelSelection: {
    customModels: [],
    availableModels: ['qwen3-coder'],
    allowedModels: ['qwen3-coder'],
    defaultModel: 'qwen3-coder',
  },
  environmentVariables: [],
};

const expectOnlyOuterCard = (container: HTMLElement) => {
  expect(container.querySelectorAll('.bg-card')).toHaveLength(1);
  expect(
    Array.from(container.querySelectorAll('[class]')).some((element) =>
      element.getAttribute('class')?.includes('bg-muted/30'),
    ),
  ).toBe(false);
};

describe('SettingsOpenCodeTab', () => {
  it('renders model and environment variable sections without nested cards', () => {
    const { container } = render(
      <SettingsOpenCodeTab
        opencodeSettings={opencodeSettings}
        onOpenCodeSettingsChange={vi.fn()}
      />,
    );

    expect(screen.getByText('pages.settings.tabs.opencode')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.opencode.models.title')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.opencode.environmentVariables.title')).toBeInTheDocument();
    expectOnlyOuterCard(container);
  });
});
