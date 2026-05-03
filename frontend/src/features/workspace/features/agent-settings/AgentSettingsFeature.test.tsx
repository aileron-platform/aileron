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

vi.mock('./pages/ScriptsPage', () => ({
  default: () => <div data-testid="scripts-page" />,
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

describe('AgentSettingsFeature shared rendering', () => {
  it('renders Claude Code settings through the shared feature surface', async () => {
    render(<AgentSettingsFeature cliType="claude" subView="scripts" />);

    expect(await screen.findByTestId('scripts-page')).toBeInTheDocument();
  });

  it('renders Gemini settings after shared component extraction', () => {
    render(<AgentSettingsFeature cliType="gemini" subView="gemini-md" />);

    expect(screen.getByTestId('agents-md-page')).toBeInTheDocument();
  });

  it('renders Gemini subagents through the shared subagents page', async () => {
    render(<AgentSettingsFeature cliType="gemini" subView="subagents" />);

    expect(await screen.findByTestId('subagents-page-gemini')).toBeInTheDocument();
  });

  it('renders OpenCode settings after shared component extraction', async () => {
    render(<AgentSettingsFeature cliType="opencode" subView="mcp" />);

    expect(await screen.findByTestId('mcp-settings-page')).toBeInTheDocument();
  });

  it('renders unsupported OpenCode hooks with localized placeholder labels', () => {
    render(<AgentSettingsFeature cliType="opencode" subView="hooks" />);

    expect(screen.getByText('workspace.agentSettings.common.comingSoon.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.hooks:workspace.navigation.main.opencodeSettings')).toBeInTheDocument();
  });

  it('routes Codex settings subviews to Codex-specific pages', async () => {
    const cases = [
      ['agents-md', 'codex-agents-md-page'],
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
});
