// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ThreadSummary } from '../model/threadModel';
import { ThreadSwitcher } from './ThreadSwitcher';

const i18nMock = vi.hoisted(() => ({
  t: vi.fn((key: string) => key),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: i18nMock.t }),
}));

const buildSummary = (
  id: string,
  updatedAt: string,
  agenticTool: ThreadSummary['agenticTool'] = 'claude',
  status: ThreadSummary['status'] = 'complete',
): ThreadSummary => ({
  id,
  workspaceId: 'workspace-switcher',
  userId: 'user-switcher',
  title: `aiChat.mock.threadTitles.${id}`,
  agenticTool,
  model: 'sonnet-5',
  claudeMode: 'execute',
  status,
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: null,
  contextWindow: null,
  createdAt: updatedAt,
  updatedAt,
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  i18nMock.t.mockClear();
});

describe('ThreadSwitcher', () => {
  it('renders the selected thread as a single switcher menu and forwards selection', () => {
    const onSelect = vi.fn();
    render(
      <ThreadSwitcher
        workspaceId="workspace-switcher"
        userId="user-switcher"
        threads={[
          buildSummary('first', '2026-07-09T01:00:00.000Z'),
          buildSummary('second', '2026-07-09T02:00:00.000Z'),
        ]}
        selectedThreadId="first"
        onSelect={onSelect}
        onNewThread={vi.fn()}
      />,
    );

    const switcher = screen.getByRole('combobox', { name: 'aiChat.companion.switchThread' });
    expect(switcher).toHaveTextContent('aiChat.mock.threadTitles.first');
    expect(screen.queryByRole('button', { name: 'aiChat.mock.threadTitles.second' })).not.toBeInTheDocument();
    expect(i18nMock.t).not.toHaveBeenCalledWith('aiChat.mock.threadTitles.first');

    fireEvent.click(switcher);
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.mock.threadTitles.second' }));

    expect(onSelect).toHaveBeenCalledWith('second');
    expect(i18nMock.t).not.toHaveBeenCalledWith('aiChat.mock.threadTitles.second');
  });

  it('translates the controlled untitled title key', () => {
    render(
      <ThreadSwitcher
        workspaceId="workspace-switcher"
        userId="user-switcher"
        threads={[
          {
            ...buildSummary('untitled', '2026-07-09T01:00:00.000Z'),
            title: 'aiChat.thread.untitled',
          },
        ]}
        selectedThreadId="untitled"
        onSelect={vi.fn()}
        onNewThread={vi.fn()}
      />,
    );

    expect(screen.getByRole('combobox', { name: 'aiChat.companion.switchThread' }))
      .toHaveTextContent('aiChat.thread.untitled');
    expect(i18nMock.t).toHaveBeenCalledWith('aiChat.thread.untitled');
  });

  it('renders processing status icons in the selected thread and menu items', () => {
    render(
      <ThreadSwitcher
        workspaceId="workspace-switcher"
        userId="user-switcher"
        threads={[
          buildSummary('claude-thread', '2026-07-09T01:00:00.000Z', 'claude'),
          buildSummary('codex-thread', '2026-07-09T02:00:00.000Z', 'codex', 'working'),
          buildSummary('opencode-thread', '2026-07-09T03:00:00.000Z', 'opencode'),
        ]}
        selectedThreadId="codex-thread"
        onSelect={vi.fn()}
        onNewThread={vi.fn()}
      />,
    );

    expect(screen.getByTestId('status-active')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('combobox', { name: 'aiChat.companion.switchThread' }));

    const opencodeOption = screen.getByRole('button', { name: 'aiChat.mock.threadTitles.opencode-thread' });
    const claudeOption = screen.getByRole('button', { name: 'aiChat.mock.threadTitles.claude-thread' });
    expect(opencodeOption.querySelector('svg.lucide-check')).toBeInTheDocument();
    expect(claudeOption.querySelector('svg.lucide-check')).toBeInTheDocument();
  });

  it('shows the selected thread agentic icon in the trigger', () => {
    render(
      <ThreadSwitcher
        workspaceId="workspace-switcher"
        userId="user-switcher"
        threads={[buildSummary('first', '2026-07-09T01:00:00.000Z', 'claude')]}
        selectedThreadId="first"
        onSelect={vi.fn()}
        onNewThread={vi.fn()}
      />,
    );

    expect(screen.getByRole('combobox', { name: 'aiChat.companion.switchThread' })).toBeInTheDocument();
    expect(screen.getByTestId('ai-chat-thread-switcher-agent-icon')).toBeInTheDocument();
  });

  it('shows agentic icons for dropdown thread items', () => {
    render(
      <ThreadSwitcher
        workspaceId="workspace-switcher"
        userId="user-switcher"
        threads={[
          buildSummary('first', '2026-07-09T01:00:00.000Z', 'claude'),
          buildSummary('second', '2026-07-09T02:00:00.000Z', 'codex'),
        ]}
        selectedThreadId="first"
        onSelect={vi.fn()}
        onNewThread={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('combobox', { name: 'aiChat.companion.switchThread' }));

    expect(screen.getAllByTestId('ai-chat-thread-switcher-item-agent-icon')).toHaveLength(2);
  });
});
