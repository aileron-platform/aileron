import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import AgentSettingsFeature from './AgentSettingsFeature';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params?.feature && params?.toolName) {
        return `${String(params.feature)}:${String(params.toolName)}`;
      }
      return key;
    },
  }),
}));

vi.mock('./pages/AgentsMdPage', () => ({
  default: () => <div data-testid="agents-md-page" />,
}));

vi.mock('./pages/MCPSettingsPage', () => ({
  default: () => <div data-testid="mcp-settings-page" />,
}));

vi.mock('./pages/HooksSettingsPage', () => ({
  default: () => <div data-testid="hooks-settings-page" />,
}));

vi.mock('./pages/SlashCommandsPage', () => ({
  default: () => <div data-testid="slash-commands-page" />,
}));

vi.mock('./pages/SkillsPage', () => ({
  default: () => <div data-testid="skills-page" />,
}));

vi.mock('./pages/CodexAgentsMdPage', () => ({
  default: () => <div data-testid="codex-agents-md-page" />,
}));

vi.mock('./pages/CodexRulesPage', () => ({
  default: () => <div data-testid="codex-rules-page" />,
}));

vi.mock('./pages/CodexHooksPage', () => ({
  default: () => <div data-testid="codex-hooks-page" />,
}));

vi.mock('./pages/CodexPluginsPage', () => ({
  default: () => <div data-testid="codex-plugins-page" />,
}));

vi.mock('./pages/CodexDocumentResourcePage', () => ({
  default: ({ resource }: { resource: string }) => <div data-testid={`codex-document-resource-${resource}`} />,
}));

vi.mock('./pages/SubagentsPage', () => ({
  default: ({ apiPrefix }: { apiPrefix: string }) => <div data-testid={`subagents-page-${apiPrefix}`} />,
}));

vi.mock('./pages/GeminiExtensionsPage', () => ({
  default: () => <div data-testid="gemini-extensions-page" />,
}));

describe('AgentSettingsFeature shared rendering', () => {
  it('does not render removed Claude scripts settings through the shared feature surface', async () => {
    render(<AgentSettingsFeature cliType="claude" subView="scripts" />);

    expect(await screen.findByText('workspace.agentSettings.common.comingSoon.title')).toBeInTheDocument();
  });

  it('renders Gemini settings after shared component extraction', async () => {
    render(<AgentSettingsFeature cliType="gemini" subView="gemini-md" />);

    expect(await screen.findByTestId('agents-md-page')).toBeInTheDocument();
  });

  it('routes every registered Gemini subview through the page registry', async () => {
    const cases = [
      ['gemini-md', 'agents-md-page'],
      ['mcp', 'mcp-settings-page'],
      ['hooks', 'hooks-settings-page'],
      ['slash-commands', 'slash-commands-page'],
      ['skills', 'skills-page'],
      ['subagents', 'subagents-page-gemini'],
      ['extensions', 'gemini-extensions-page'],
    ];

    for (const [subView, testId] of cases) {
      const { unmount } = render(<AgentSettingsFeature cliType="gemini" subView={subView} />);
      expect(await screen.findByTestId(testId)).toBeInTheDocument();
      unmount();
    }
  });

  it('routes every registered OpenCode subview through the page registry', async () => {
    const cases = [
      ['agents-md', 'agents-md-page'],
      ['mcp', 'mcp-settings-page'],
      ['slash-commands', 'slash-commands-page'],
      ['skills', 'skills-page'],
    ];

    for (const [subView, testId] of cases) {
      const { unmount } = render(<AgentSettingsFeature cliType="opencode" subView={subView} />);
      expect(await screen.findByTestId(testId)).toBeInTheDocument();
      unmount();
    }
  });

  it('renders unsupported OpenCode hooks with localized placeholder labels', () => {
    render(<AgentSettingsFeature cliType="opencode" subView="hooks" />);

    expect(screen.getByText('workspace.agentSettings.common.comingSoon.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.hooks:workspace.navigation.main.opencodeSettings')).toBeInTheDocument();
  });

  it('routes Codex settings subviews to Codex-specific pages', async () => {
    const cases = [
      ['agents-md', 'codex-agents-md-page'],
      ['mcp', 'mcp-settings-page'],
      ['rules', 'codex-rules-page'],
      ['hooks', 'codex-hooks-page'],
      ['plugins', 'codex-plugins-page'],
      ['skills', 'skills-page'],
      ['subagents', 'codex-document-resource-subagents'],
      ['prompts', 'codex-document-resource-prompts'],
    ];

    for (const [subView, testId] of cases) {
      const { unmount } = render(<AgentSettingsFeature cliType="codex" subView={subView} />);
      expect(await screen.findByTestId(testId)).toBeInTheDocument();
      unmount();
    }
  });

  it('renders placeholders for unmapped Gemini and Codex subviews', () => {
    const gemini = render(<AgentSettingsFeature cliType="gemini" subView="rules" />);
    expect(screen.getByText('workspace.agentSettings.common.subViews.rules:workspace.navigation.main.geminiSettings')).toBeInTheDocument();
    gemini.unmount();

    render(<AgentSettingsFeature cliType="codex" subView="extensions" />);
    expect(screen.getByText('workspace.agentSettings.common.subViews.extensions:workspace.navigation.main.codexSettings')).toBeInTheDocument();
  });
});
