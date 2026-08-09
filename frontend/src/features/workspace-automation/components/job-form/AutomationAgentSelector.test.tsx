import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AutomationAgentSelector } from './AutomationAgentSelector';

const { getCapabilities } = vi.hoisted(() => ({ getCapabilities: vi.fn() }));

getCapabilities.mockResolvedValue({
  defaultTool: 'claude',
  tools: [
    {
      id: 'claude',
      models: ['claude-sonnet'],
      defaultModel: 'claude-sonnet',
      modes: ['execute', 'plan'],
      defaultMode: 'execute',
      contextWindow: 200000,
    },
    {
      id: 'codex',
      models: ['gpt-5-codex'],
      defaultModel: 'gpt-5-codex',
      modes: null,
      defaultMode: null,
      contextWindow: 128000,
    },
  ],
});

vi.mock('../../api/automationWorkspaceApi', () => ({
  automationWorkspaceApi: { getCapabilities },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

describe('AutomationAgentSelector', () => {
  it('loads workspace capabilities and lets the user choose an agent', async () => {
    const onChange = vi.fn();
    render(
      <AutomationAgentSelector
        workspaceId="workspace-1"
        value={{ agenticTool: 'claude', model: 'claude-sonnet', mode: 'execute' }}
        onChange={onChange}
      />,
    );

    await userEvent.click(await screen.findByRole('button', { name: 'aiChat.settings.tool' }));
    await userEvent.click(screen.getByRole('button', { name: /codex/i }));

    expect(onChange).toHaveBeenCalledWith({
      agenticTool: 'codex',
      model: 'gpt-5-codex',
      mode: null,
    });
  });
});
