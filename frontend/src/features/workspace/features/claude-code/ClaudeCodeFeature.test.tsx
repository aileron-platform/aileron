import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import ClaudeCodeFeature from './ClaudeCodeFeature';

const { hooksSettingsPageMock } = vi.hoisted(() => ({
  hooksSettingsPageMock: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../agent-settings/pages/AgentsMdPage', () => ({
  default: () => <div data-testid="claude-agents-md-page" />,
}));

vi.mock('../agent-settings/pages/SkillsPage', () => ({
  default: () => <div data-testid="claude-skills-page" />,
}));

vi.mock('../agent-settings/pages/HooksSettingsPage', () => ({
  default: (props: unknown) => {
    hooksSettingsPageMock(props);
    return <div data-testid="claude-hooks-page" />;
  },
}));

vi.mock('../agent-settings/pages/ClaudePluginsPage', () => ({
  default: () => <div data-testid="claude-plugins-page" />,
}));

describe('ClaudeCodeFeature', () => {
  it('keeps Claude-only routing in the legacy dispatcher for shared pages', () => {
    const { rerender } = render(<ClaudeCodeFeature subView="claude-md" />);

    expect(screen.getByTestId('claude-agents-md-page')).toBeInTheDocument();

    rerender(<ClaudeCodeFeature subView="skills" />);

    expect(screen.getByTestId('claude-skills-page')).toBeInTheDocument();
  });

  it('routes Claude plugins from the dynamic extensions submenu', () => {
    render(<ClaudeCodeFeature subView="plugins" />);

    expect(screen.getByTestId('claude-plugins-page')).toBeInTheDocument();
  });

  it('passes Claude hook scopes without the Gemini extension scope', () => {
    render(<ClaudeCodeFeature subView="hooks" />);

    expect(screen.getByTestId('claude-hooks-page')).toBeInTheDocument();
    expect(hooksSettingsPageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        apiPrefix: 'claude-code',
        availableScopes: ['project', 'user', 'local', 'plugin'],
      }),
    );
  });
});
