// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ThreadSummary } from '../model/threadModel';
import { ThreadListSidebar } from './ThreadListSidebar';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) =>
      params ? `${key}:${params.count}` : key,
  }),
}));

afterEach(() => {
  cleanup();
});

const buildThread = (overrides: Partial<ThreadSummary> = {}): ThreadSummary => ({
  id: 'thread-active',
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
  ...overrides,
});

const renderSidebar = (overrides: Partial<Parameters<typeof ThreadListSidebar>[0]> = {}) => {
  const props = {
    workspaceId: 'workspace-1',
    userId: 'user-1',
    selectedThreadId: null,
    threads: [buildThread()],
    isLoading: false,
    onSelect: vi.fn(),
    onArchive: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };

  render(<ThreadListSidebar {...props} />);
  return props;
};

describe('ThreadListSidebar', () => {
  it('renders threads in the order supplied by the page owner', () => {
    renderSidebar({
      threads: [
        buildThread({ id: 'thread-z', title: 'Zeta' }),
        buildThread({ id: 'thread-a', title: 'Alpha' }),
      ],
    });

    expect(screen.getByTestId('ai-chat-thread-list-content')).toHaveClass('w-full', 'min-w-0', 'max-w-full');
    expect(screen.getAllByTestId('ai-chat-thread-title').map((item) => item.textContent)).toEqual([
      'Zeta',
      'Alpha',
    ]);
  });

  it('forwards thread selection to the page owner', () => {
    const props = renderSidebar({
      threads: [buildThread({ id: 'thread-selected' })],
    });

    fireEvent.click(screen.getByRole('button', { name: /aiChat.mock.threadTitles.complete/ }));

    expect(props.onSelect).toHaveBeenCalledWith('thread-selected');
  });

  it('renders the existing loading state from the page query', () => {
    renderSidebar({ isLoading: true });

    expect(screen.getByText('aiChat.threadList.loading')).toBeInTheDocument();
    expect(screen.queryByTestId('ai-chat-thread-list-empty')).not.toBeInTheDocument();
  });

  it('uses a centered second-column empty state when no threads exist', () => {
    renderSidebar({ threads: [] });

    expect(screen.getByTestId('ai-chat-thread-list-empty')).toHaveClass(
      'flex',
      'h-full',
      'flex-col',
      'items-center',
      'justify-center',
      'gap-3',
      'p-6',
      'text-center',
    );
    expect(screen.getByText('aiChat.threadList.emptyTitle')).toBeInTheDocument();
    expect(screen.getByText('aiChat.threadList.emptyDescription')).toBeInTheDocument();
  });
});
