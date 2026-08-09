// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThreadActionMenu } from './ThreadActionMenu';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

afterEach(() => {
  cleanup();
});

describe('ThreadActionMenu', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  it('calls archive and delete for an active thread', async () => {
    const user = userEvent.setup();
    const onArchive = vi.fn();
    const onDelete = vi.fn();

    render(
      <ThreadActionMenu
        thread={{ id: 'thread-1', archived: false }}
        onArchive={onArchive}
        onDelete={onDelete}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.archive' }));
    expect(onArchive).toHaveBeenCalledWith('thread-1');

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.delete' }));
    expect(onDelete).toHaveBeenCalledWith('thread-1');
  });

  it('hides archive for archived threads', async () => {
    const user = userEvent.setup();

    render(
      <ThreadActionMenu
        thread={{ id: 'thread-1', archived: true }}
        onArchive={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));

    expect(screen.queryByRole('menuitem', { name: 'aiChat.threadActions.archive' })).not.toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'aiChat.threadActions.delete' })).toBeInTheDocument();
  });

  it('keeps copy Thread ID as an optional secondary action', async () => {
    const user = userEvent.setup();
    const onCopyThreadId = vi.fn();

    render(
      <ThreadActionMenu
        thread={{ id: 'thread-1', archived: false }}
        onDelete={vi.fn()}
        onCopyThreadId={onCopyThreadId}
        includeCopyThreadId
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.copyThreadId' }));

    expect(onCopyThreadId).toHaveBeenCalledWith('thread-1');
  });

  it('disables action items when no thread is selected', async () => {
    const user = userEvent.setup();

    render(
      <ThreadActionMenu
        thread={null}
        onArchive={vi.fn()}
        onDelete={vi.fn()}
        onCopyThreadId={vi.fn()}
        includeCopyThreadId
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));

    expect(screen.getByRole('menuitem', { name: 'aiChat.threadActions.archive' })).toHaveAttribute('data-disabled');
    expect(screen.getByRole('menuitem', { name: 'aiChat.threadActions.delete' })).toHaveAttribute('data-disabled');
    expect(screen.getByRole('menuitem', { name: 'aiChat.threadActions.copyThreadId' })).toHaveAttribute('data-disabled');
  });

  it('does not render the init message visibility toggle by default', async () => {
    const user = userEvent.setup();

    render(
      <ThreadActionMenu
        thread={{ id: 'thread-1', archived: false }}
        onArchive={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));

    expect(
      screen.queryByRole('menuitemcheckbox', { name: 'aiChat.threadActions.showInitMessages' }),
    ).not.toBeInTheDocument();
  });

  it('toggles and persists the init message visibility preference when display settings are enabled', async () => {
    const user = userEvent.setup();

    render(
      <ThreadActionMenu
        thread={{ id: 'thread-1', archived: false }}
        includeDisplaySettings
      />,
    );

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    const toggle = screen.getByRole('menuitemcheckbox', { name: 'aiChat.threadActions.showInitMessages' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');

    await user.click(toggle);

    expect(localStorage.getItem('aichat.showInitMessages')).toBe('true');
  });

  it('keeps the init message visibility toggle independent of thread selection', async () => {
    const user = userEvent.setup();

    render(<ThreadActionMenu thread={null} includeDisplaySettings />);

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));

    expect(
      screen.getByRole('menuitemcheckbox', { name: 'aiChat.threadActions.showInitMessages' }),
    ).not.toHaveAttribute('aria-disabled');
  });
});
