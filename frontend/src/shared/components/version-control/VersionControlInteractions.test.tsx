import { fireEvent, render, screen, within } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  VersionControlActionMenu,
  VersionControlBranchSelector,
  VersionControlDiscardDialog,
  VersionControlFileChangeItem,
  VersionControlHistorySidebar,
  useVersionControlWorkbenchModel,
} from './index';
import { act, renderHook } from '@testing-library/react';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => (
      params ? `${key}:${JSON.stringify(params)}` : key
    ),
  }),
}));

describe('version control shared interactions', () => {
  it('preserves staged selection metadata for Knowledge Base and Marketplace consumers', () => {
    const { result } = renderHook(() => useVersionControlWorkbenchModel({
      changes: {
        staged: {
          items: [{ name: 'new-report.md', path: 'new-report.md', status: 'A' }],
          total: 1,
          nextCursor: null,
          hasMore: false,
        },
        unstaged: { items: [], total: 0, nextCursor: null, hasMore: false },
        untracked: { items: [], total: 0, nextCursor: null, hasMore: false },
        conflicts: { items: [], total: 0, nextCursor: null, hasMore: false },
      },
    }));

    act(() => {
      result.current.controller.selection.selectFile(
        result.current.stagedFiles[0],
        'staged',
      );
    });

    expect(result.current.controller.selection.selectedGroup).toBe('staged');
    expect(result.current.controller.selection.selectedFile).toMatchObject({
      path: 'new-report.md',
      changeType: 'staged',
    });
  });

  it('uses the fixed top action order and separators for every product', async () => {
    const user = userEvent.setup();
    render(
      <VersionControlActionMenu
        actions={[
          { id: 'remoteSettings', onClick: vi.fn() },
          { id: 'push', onClick: vi.fn() },
          { id: 'refresh', onClick: vi.fn() },
          { id: 'lfs', onClick: vi.fn() },
          { id: 'pull', onClick: vi.fn() },
          { id: 'fetch', onClick: vi.fn() },
        ]}
      />,
    );

    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.actions.menu.label',
    }));

    expect(screen.getAllByRole('menuitem').map((item) => item.textContent)).toEqual([
      'shared.versionControl.actions.refresh.label',
      'shared.versionControl.actions.fetch.label',
      'shared.versionControl.actions.pull.label',
      'shared.versionControl.actions.push.label',
      'shared.versionControl.actions.remoteSettings.label',
      'shared.versionControl.actions.lfs.label',
    ]);
    expect(screen.getAllByRole('separator')).toHaveLength(1);
  });

  it('offers local branch actions and remote tracking from branch capabilities', async () => {
    const user = userEvent.setup();
    const onBranchChange = vi.fn();
    const onRenameBranch = vi.fn();
    const onDeleteBranch = vi.fn();
    const onCreateTrackingBranch = vi.fn();

    render(
      <VersionControlBranchSelector
        branches={[
          {
            name: 'feature/local',
            displayName: 'feature/local',
            kind: 'local',
            isCurrent: false,
            upstream: null,
            ahead: 0,
            behind: 0,
            checkedOutTarget: null,
            capabilities: {
              switch: { allowed: true },
              rename: { allowed: true },
              delete: { allowed: true },
            },
          },
          {
            name: 'origin/feature/remote',
            displayName: 'origin/feature/remote',
            kind: 'remote',
            isCurrent: false,
            upstream: null,
            ahead: 0,
            behind: 0,
            checkedOutTarget: null,
            capabilities: {
              switch: { allowed: false },
              rename: { allowed: false },
              delete: { allowed: false },
            },
          },
        ]}
        currentBranch="main"
        onBranchChange={onBranchChange}
        onRenameBranch={onRenameBranch}
        onDeleteBranch={onDeleteBranch}
        onCreateTrackingBranch={onCreateTrackingBranch}
      />,
    );

    await user.click(screen.getByRole('button', { name: /main/i }));
    await user.click(screen.getByRole('button', {
      name: /shared\.versionControl\.branch\.actions\.menu:.*feature\/local/,
    }));
    const localActions = screen.getByRole('menu', {
      name: /shared\.versionControl\.branch\.actions\.menu:.*feature\/local/,
    });
    expect(within(localActions).getAllByRole('menuitem').map((item) => item.textContent)).toEqual([
      'shared.versionControl.branch.actions.switch',
      'shared.versionControl.branch.actions.rename',
      'shared.versionControl.branch.actions.delete',
    ]);
    await user.click(within(localActions).getByRole('menuitem', {
      name: 'shared.versionControl.branch.actions.rename',
    }));
    expect(onRenameBranch).toHaveBeenCalledWith(expect.objectContaining({ name: 'feature/local' }));

    await user.click(screen.getByRole('button', { name: /main/i }));
    await user.click(screen.getByRole('button', {
      name: /shared\.versionControl\.branch\.actions\.menu:.*origin\/feature\/remote/,
    }));
    const remoteActions = screen.getByRole('menu', {
      name: /shared\.versionControl\.branch\.actions\.menu:.*origin\/feature\/remote/,
    });
    expect(within(remoteActions).getAllByRole('menuitem').map((item) => item.textContent)).toEqual([
      'shared.versionControl.branch.actions.createTracking',
    ]);
    await user.click(within(remoteActions).getByRole('menuitem'));
    expect(onCreateTrackingBranch).toHaveBeenCalledWith(expect.objectContaining({
      name: 'origin/feature/remote',
    }));

    await user.click(screen.getByRole('button', { name: /main/i }));
    fireEvent.contextMenu(screen.getByText('feature/local'));
    const contextActions = screen.getByRole('menu', {
      name: /shared\.versionControl\.branch\.actions\.menu:.*feature\/local/,
    });
    expect(within(contextActions).getAllByRole('menuitem')).toHaveLength(3);
  });

  it('keeps file context menu slots stable in read-only mode', async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const onStageToggle = vi.fn();
    const onDiscard = vi.fn();
    const onCopyPath = vi.fn();

    render(
      <VersionControlFileChangeItem
        file={{ name: 'README.md', path: 'docs/README.md', status: 'M' }}
        isSelected={false}
        isMultiSelected={false}
        type="unstaged"
        onSelect={vi.fn()}
        onStageToggle={onStageToggle}
        onDiscard={onDiscard}
        onOpen={onOpen}
        onCopyPath={onCopyPath}
        selectedCount={1}
        readOnly
      />,
    );

    await user.pointer({ keys: '[MouseRight]', target: screen.getByText('README.md') });
    const items = screen.getAllByRole('menuitem');
    expect(items.map((item) => item.textContent)).toEqual([
      'shared.versionControl.fileItem.open',
      'shared.versionControl.fileItem.stage',
      'shared.versionControl.fileItem.discard',
      'shared.versionControl.fileItem.copyPath',
    ]);
    expect(items[0]).toHaveAttribute('data-disabled', 'false');
    expect(items[1]).toHaveAttribute('data-disabled', 'true');
    expect(items[2]).toHaveAttribute('data-disabled', 'true');
    expect(items[3]).toHaveAttribute('data-disabled', 'false');
    expect(screen.getAllByRole('separator')).toHaveLength(2);
  });

  it('preserves a discard dialog after failure and locks dismissal while pending', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onConfirm = vi.fn(async () => {
      throw new Error('DISCARD_FAILED');
    });

    render(
      <VersionControlDiscardDialog
        open
        paths={['a.md', 'b.md']}
        onOpenChange={onOpenChange}
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.discardDialog.confirm',
    }));

    expect(await screen.findByText('DISCARD_FAILED')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it('uses the shared commit context menu order and disables revert in read-only mode', async () => {
    const user = userEvent.setup();
    render(
      <VersionControlHistorySidebar
        commits={[{
          id: 'abc123456789',
          message: 'Update docs',
          author: 'Maintainer',
          timestamp: Date.now(),
        }]}
        files={[]}
        onCommitSelect={vi.fn()}
        onFileSelect={vi.fn()}
        onRevertCommit={vi.fn()}
        mutationDisabled
      />,
    );

    await user.pointer({ keys: '[MouseRight]', target: screen.getByText('Update docs') });
    const items = screen.getAllByRole('menuitem');
    expect(items.map((item) => item.textContent)).toEqual([
      'shared.versionControl.commit.actions.view',
      'shared.versionControl.commit.actions.copySha',
      'shared.versionControl.commit.actions.revert',
    ]);
    expect(items[2]).toHaveAttribute('data-disabled', 'true');
  });
});
