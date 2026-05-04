import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import ClaudeCodeFeature from './ClaudeCodeFeature';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../agent-settings/pages/AgentsMdPage', () => ({
  default: () => <div data-testid="claude-agents-md-page" />,
}));

vi.mock('../agent-settings/pages/ScriptsPage', () => ({
  default: () => <div data-testid="claude-scripts-page" />,
}));

describe('ClaudeCodeFeature', () => {
  it('keeps Claude-only routing in the legacy dispatcher for shared pages', () => {
    const { rerender } = render(<ClaudeCodeFeature subView="claude-md" />);

    expect(screen.getByTestId('claude-agents-md-page')).toBeInTheDocument();

    rerender(<ClaudeCodeFeature subView="scripts" />);

    expect(screen.getByTestId('claude-scripts-page')).toBeInTheDocument();
  });
});
