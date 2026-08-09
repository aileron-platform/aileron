// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setLastReadAt } from '../storage/aiChatStorage';
import type { ThreadSummary } from '../model/threadModel';
import { ThreadListItem } from './ThreadListItem';

const i18nMock = vi.hoisted(() => ({
  t: vi.fn((key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${params.count}` : key,
  ),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: i18nMock.t }),
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
});

beforeEach(() => {
  i18nMock.t.mockClear();
  vi.setSystemTime(new Date('2026-07-09T10:00:00.000Z'));
});

const thread: ThreadSummary = {
  id: 'thread-1',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  title: 'aiChat.mock.threadTitles.complete',
  agenticTool: 'claude',
  model: 'sonnet-5',
  claudeMode: 'plan',
  status: 'complete',
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: 100,
  contextWindow: 1000,
  createdAt: '2026-07-09T08:00:00.000Z',
  updatedAt: '2026-07-09T09:30:00.000Z',
};

const renderItem = (overrides: Partial<Parameters<typeof ThreadListItem>[0]> = {}) => {
  const props = {
    thread,
    workspaceId: 'workspace-1',
    userId: 'user-1',
    selected: false,
    onSelect: vi.fn(),
    onArchive: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  render(<ThreadListItem {...props} />);
  return props;
};

describe('ThreadListItem', () => {
  it('shows the thread status icon before the title and truncates the title text', () => {
    renderItem();

    const item = screen.getByRole('button', { name: /aiChat\.mock\.threadTitles\.complete/ });
    const title = screen.getByTestId('ai-chat-thread-title');

    expect(item).toHaveClass('flex', 'flex-col', 'gap-2', 'px-3', 'py-2');
    expect(item.querySelector('svg.lucide-check')).toBeInTheDocument();
    expect(title).toHaveTextContent('aiChat.mock.threadTitles.complete');
    expect(title).toHaveClass('min-w-0', 'flex-1', 'truncate');
    expect(i18nMock.t).not.toHaveBeenCalledWith(thread.title);
  });

  it('translates the controlled untitled title key', () => {
    renderItem({ thread: { ...thread, title: 'aiChat.thread.untitled' } });

    expect(screen.getByTestId('ai-chat-thread-title')).toHaveTextContent('aiChat.thread.untitled');
    expect(i18nMock.t).toHaveBeenCalledWith('aiChat.thread.untitled');
  });

  it('keeps borderless agent and model tags in the metadata row', () => {
    renderItem();

    const agentTag = screen.getByTestId('ai-chat-thread-agent-tag');
    const modelTag = screen.getByTestId('ai-chat-thread-model-tag');

    expect(agentTag).toHaveTextContent('claude');
    expect(agentTag).not.toHaveClass('border');
    expect(agentTag).not.toHaveClass('bg-muted');
    expect(modelTag).toHaveTextContent('sonnet-5');
    expect(modelTag).not.toHaveClass('border');
    expect(modelTag).not.toHaveClass('bg-muted');
    expect(agentTag.querySelector('span')).not.toHaveClass('truncate');
    expect(modelTag.querySelector('span')).not.toHaveClass('truncate');
    expect(screen.getByTestId('ai-chat-thread-agent-icon')).toHaveAttribute(
      'src',
      '/marketplace/providers/claude-code.png',
    );
    expect(screen.getByTestId('ai-chat-thread-model-icon')).toBeInTheDocument();
  });

  it('shows unread status marker when the thread updated after the last read timestamp', () => {
    setLastReadAt('user-1', 'workspace-1', 'thread-1', '2026-07-09T09:00:00.000Z');

    renderItem();

    expect(screen.getByTestId('status-unread')).toBeInTheDocument();
  });

  it('does not show unread status marker for a read thread', () => {
    setLastReadAt('user-1', 'workspace-1', 'thread-1', '2026-07-09T09:30:00.000Z');

    renderItem();

    expect(screen.queryByTestId('status-unread')).not.toBeInTheDocument();
  });

  it('exposes archive and delete actions without selecting the row', async () => {
    const user = userEvent.setup();
    const props = renderItem();

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.archive' }));
    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.delete' }));

    expect(props.onArchive).toHaveBeenCalledWith('thread-1');
    expect(props.onDelete).toHaveBeenCalledWith('thread-1');
    expect(props.onSelect).not.toHaveBeenCalled();
  });
});
