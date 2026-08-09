// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ThreadSummary } from '../model/threadModel';
import { ChatThreadFeatureHeader } from './ChatThreadFeatureHeader';

const i18nMock = vi.hoisted(() => ({
  t: vi.fn((key: string) => key),
}));
const toastMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: i18nMock.t }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

const thread: ThreadSummary = {
  id: 'thread-1',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  title: 'User-provided thread title',
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

describe('ChatThreadFeatureHeader', () => {
  beforeEach(() => {
    i18nMock.t.mockClear();
    toastMock.mockClear();
  });

  it('renders dynamic thread titles verbatim without translating them', () => {
    render(
      <ChatThreadFeatureHeader
        thread={thread}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: thread.title })).toBeInTheDocument();
    expect(i18nMock.t).not.toHaveBeenCalledWith(thread.title);
  });

  it('translates the controlled untitled title key', () => {
    render(
      <ChatThreadFeatureHeader
        thread={{ ...thread, title: 'aiChat.thread.untitled' }}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'aiChat.thread.untitled' })).toBeInTheDocument();
    expect(i18nMock.t).toHaveBeenCalledWith('aiChat.thread.untitled');
  });

  it('copies the thread id through the shared action menu', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });

    render(
      <ChatThreadFeatureHeader
        thread={thread}
        onRetry={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.copyThreadId' }));

    expect(writeText).toHaveBeenCalledWith('thread-1');
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith({
        title: 'aiChat.threadActions.copyThreadIdSuccess.title',
        description: 'aiChat.threadActions.copyThreadIdSuccess.description',
        variant: 'success',
      });
    });
  });

  it('archives through the shared action menu when archive is available', async () => {
    const user = userEvent.setup();
    const onArchive = vi.fn();

    render(
      <ChatThreadFeatureHeader
        thread={thread}
        onRetry={vi.fn()}
        onArchive={onArchive}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.archive' }));

    expect(onArchive).toHaveBeenCalledTimes(1);
  });

  it('renders the init message visibility toggle in the shared action menu', async () => {
    const user = userEvent.setup();

    render(
      <ChatThreadFeatureHeader
        thread={thread}
        onRetry={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));

    expect(
      screen.getByRole('menuitemcheckbox', { name: 'aiChat.threadActions.showInitMessages' }),
    ).toBeInTheDocument();
  });
});
