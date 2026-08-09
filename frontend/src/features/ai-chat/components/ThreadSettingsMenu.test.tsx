// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { AgentSettingsMenu, ModelSettingsMenu, ModeSettingsMenu } from './ThreadSettingsMenu';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

afterEach(() => {
  cleanup();
});

const caps: WorkspaceCapabilities = {
  defaultTool: 'claude',
  tools: [
    {
      id: 'claude',
      models: ['claude-alpha', 'claude-beta'],
      defaultModel: 'claude-alpha',
      modes: ['execute', 'plan'],
      defaultMode: 'execute',
      contextWindow: 200000,
    },
    {
      id: 'codex',
      models: ['codex-alpha'],
      defaultModel: 'codex-alpha',
      modes: null,
      defaultMode: null,
      contextWindow: 128000,
    },
  ],
};

describe('ThreadSettingsMenu', () => {
  it('renders agent choices with marketplace provider icons', () => {
    const onChange = vi.fn();
    render(
      <AgentSettingsMenu
        capabilities={caps}
        settings={{ agenticTool: 'claude', model: 'claude-alpha', claudeMode: 'execute' }}
        locked={false}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.tool' }));

    expect(screen.getByText('aiChat.settings.tool')).toBeInTheDocument();
    expect(screen.queryByText('aiChat.settings.model')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /codex/i }).querySelector('img')).toHaveAttribute(
      'src',
      '/marketplace/providers/codex.png',
    );

    fireEvent.click(screen.getByRole('button', { name: /codex/i }));

    expect(onChange).toHaveBeenCalledWith({ agenticTool: 'codex', model: 'codex-alpha', claudeMode: null });
    expect(screen.queryByText('aiChat.settings.tool')).not.toBeInTheDocument();
  });

  it('renders model choices in a separate menu without option icons', () => {
    const onChange = vi.fn();
    render(
      <ModelSettingsMenu
        capabilities={caps}
        settings={{ agenticTool: 'claude', model: 'claude-alpha', claudeMode: 'execute' }}
        locked={false}
        onChange={onChange}
      />,
    );

    const modelButton = screen.getByRole('button', { name: 'aiChat.settings.model' });
    expect(modelButton.querySelector('svg')).toBeInTheDocument();

    fireEvent.click(modelButton);

    expect(screen.getByText('aiChat.settings.model')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'claude-beta' }).querySelector('img,svg')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'claude-beta' }));

    expect(onChange).toHaveBeenCalledWith({ agenticTool: 'claude', model: 'claude-beta', claudeMode: 'execute' });
    expect(screen.queryByText('aiChat.settings.model')).not.toBeInTheDocument();
  });

  it('renders mode choices in a separate menu', () => {
    const onChange = vi.fn();
    render(
      <ModeSettingsMenu
        capabilities={caps}
        settings={{ agenticTool: 'claude', model: 'claude-alpha', claudeMode: 'execute' }}
        locked={false}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.mode' }));
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.settings.plan' }));

    expect(onChange).toHaveBeenCalledWith({ agenticTool: 'claude', model: 'claude-alpha', claudeMode: 'plan' });
    expect(screen.queryByRole('button', { name: 'aiChat.settings.plan' })).not.toBeInTheDocument();
  });

  it('does not render the mode menu when codex is selected', () => {
    render(
      <ModeSettingsMenu
        capabilities={caps}
        settings={{ agenticTool: 'codex', model: 'codex-alpha', claudeMode: null }}
        locked={false}
        onChange={vi.fn()}
      />,
    );

    expect(screen.queryByRole('button', { name: 'aiChat.settings.mode' })).not.toBeInTheDocument();
  });

  it('renders a disabled agent trigger when locked', () => {
    render(
      <AgentSettingsMenu
        capabilities={caps}
        settings={{ agenticTool: 'claude', model: 'claude-alpha', claudeMode: 'execute' }}
        locked
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'aiChat.settings.tool' })).toBeDisabled();
  });
});
