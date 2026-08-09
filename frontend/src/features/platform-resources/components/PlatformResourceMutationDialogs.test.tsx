import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseQuotaDialog } from './KnowledgeBaseQuotaDialog';
import { OwnerReassignmentDialog } from './OwnerReassignmentDialog';
import { WorkspaceCapacityExpansionDialog } from './WorkspaceCapacityExpansionDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
  useOptionalI18n: () => ({ t: (key: string) => key }),
}));

const owner = {
  id: 'owner-1',
  username: 'owner',
  displayName: 'Owner',
  avatarUrl: null,
};

const workspace = {
  id: 'ws-1',
  name: 'Workspace One',
  owner,
  runtimeStatus: 'running' as const,
  workspaceData: {
    usedBytes: 10,
    allocatedBytes: 20,
    utilizationPercent: 50,
    risk: 'normal' as const,
    measuredAt: 'now',
    expansionSupported: true,
  },
  runtimeHome: null,
  capacityRisk: 'normal' as const,
  provisioner: 'kubernetes' as const,
};

const knowledgeBase = {
  id: 'kb-1',
  name: 'Knowledge Base One',
  owner,
  visibility: 'private' as const,
  currentSizeBytes: 2 * 1024 ** 3,
  quotaBytes: 4 * 1024 ** 3,
  effectiveQuotaBytes: 4 * 1024 ** 3,
  quotaSource: 'custom' as const,
  utilizationPercent: 50,
  capacityRisk: 'normal' as const,
  indexingHealth: 'success' as const,
};

const deferred = () => {
  let resolve!: () => void;
  const promise = new Promise<void>(resolvePromise => { resolve = resolvePromise; });
  return { promise, resolve };
};

const getDialogCloseButton = (dialog: HTMLElement) => {
  const closeButton = within(dialog)
    .getAllByRole('button', { name: 'common.close' })
    .find(button => button.querySelector('.sr-only'));
  if (!closeButton) throw new Error('Dialog close button not found');
  return closeButton;
};

const getFooterAction = (dialog: HTMLElement, name: string) => {
  const footerAction = within(dialog)
    .getAllByRole('button', { name })
    .find(button => !button.querySelector('.sr-only'));
  if (!footerAction) throw new Error(`Dialog footer action not found: ${name}`);
  return footerAction;
};

const attemptDismissal = (dialog: HTMLElement, footerActionName: string) => {
  fireEvent.keyDown(document, { key: 'Escape' });
  fireEvent.pointerDown(document.body);
  fireEvent.click(getDialogCloseButton(dialog));
  fireEvent.click(getFooterAction(dialog, footerActionName));
};

describe('Platform Resource mutation dialogs', () => {
  it('blocks reassignment dismissal while its mutation is pending', async () => {
    const request = deferred();
    const onClose = vi.fn();
    const Harness = () => {
      const [isSubmitting, setIsSubmitting] = React.useState(false);
      return (
        <OwnerReassignmentDialog
          selectionIdentity="subject-1:workspaces:management:0:1"
          resource={workspace}
          candidates={[{ id: 'owner-2', username: 'next', displayName: 'Next Owner' }]}
          isSearching={false}
          searchError={false}
          isSubmitting={isSubmitting}
          submitError={false}
          onSearch={() => undefined}
          onSubmit={async () => {
            setIsSubmitting(true);
            await request.promise;
            setIsSubmitting(false);
          }}
          onClose={onClose}
        />
      );
    };
    render(<Harness />);
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Next Owner/ }));
    fireEvent.change(within(dialog).getByRole('textbox', {
      name: 'platformResources.ownerReassignment.reasonLabel',
    }), { target: { value: 'Operational ownership change' } });
    fireEvent.click(within(dialog).getByRole('button', {
      name: 'platformResources.ownerReassignment.confirm',
    }));
    await waitFor(() => expect(within(dialog).getByRole('button', {
      name: 'common.cancel',
    })).toBeDisabled());

    attemptDismissal(dialog, 'common.cancel');
    expect(onClose).not.toHaveBeenCalled();
    expect(dialog).toBeInTheDocument();

    await act(async () => { request.resolve(); });
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it('blocks quota dismissal while its mutation is pending', async () => {
    const request = deferred();
    const onClose = vi.fn();
    const Harness = () => {
      const [isSubmitting, setIsSubmitting] = React.useState(false);
      return (
        <KnowledgeBaseQuotaDialog
          selectionIdentity="subject-1:knowledge-bases:management:0:1"
          resource={knowledgeBase}
          isSubmitting={isSubmitting}
          hasError={false}
          onSubmit={async () => {
            setIsSubmitting(true);
            await request.promise;
            setIsSubmitting(false);
          }}
          onClose={onClose}
        />
      );
    };
    render(<Harness />);
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(
      'platformResources.quotaDialog.quotaGiBLabel',
    ), { target: { value: '8' } });
    fireEvent.click(within(dialog).getByRole('button', {
      name: 'platformResources.quotaDialog.confirm',
    }));
    await waitFor(() => expect(within(dialog).getByRole('button', {
      name: 'common.cancel',
    })).toBeDisabled());

    attemptDismissal(dialog, 'common.cancel');
    expect(onClose).not.toHaveBeenCalled();
    expect(dialog).toBeInTheDocument();

    await act(async () => { request.resolve(); });
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it('blocks expansion dismissal while its mutation is pending', async () => {
    const request = deferred();
    const onClose = vi.fn();
    const Harness = () => {
      const [isSubmitting, setIsSubmitting] = React.useState(false);
      return (
        <WorkspaceCapacityExpansionDialog
          resource={workspace}
          status={null}
          isSubmitting={isSubmitting}
          hasError={false}
          onSubmit={async () => {
            setIsSubmitting(true);
            await request.promise;
            setIsSubmitting(false);
          }}
          onClose={onClose}
        />
      );
    };
    render(<Harness />);
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(
      'platformResources.expansionDialog.requestedGiBLabel',
    ), { target: { value: '30' } });
    fireEvent.click(within(dialog).getByRole('button', {
      name: 'platformResources.expansionDialog.confirm',
    }));
    await waitFor(() => expect(getFooterAction(dialog, 'common.close')).toBeDisabled());

    attemptDismissal(dialog, 'common.close');
    expect(onClose).not.toHaveBeenCalled();
    expect(dialog).toBeInTheDocument();

    await act(async () => { request.resolve(); });
  });

  it('does not let an old reassignment completion close a new context dialog', async () => {
    const request = deferred();
    const onClose = vi.fn();
    const props = {
      candidates: [{ id: 'owner-2', username: 'next', displayName: 'Next Owner' }],
      isSearching: false,
      searchError: false,
      submitError: false,
      onSearch: () => undefined,
      onSubmit: () => request.promise,
      onClose,
    };
    const view = render(
      <OwnerReassignmentDialog
        {...props}
        selectionIdentity="subject-1:workspaces:management:0:1"
        resource={workspace}
        isSubmitting={false}
      />,
    );
    const oldDialog = screen.getByRole('dialog');
    fireEvent.click(within(oldDialog).getByRole('button', { name: /Next Owner/ }));
    fireEvent.change(within(oldDialog).getByRole('textbox', {
      name: 'platformResources.ownerReassignment.reasonLabel',
    }), { target: { value: 'Operational ownership change' } });
    fireEvent.click(within(oldDialog).getByRole('button', {
      name: 'platformResources.ownerReassignment.confirm',
    }));

    view.rerender(
      <OwnerReassignmentDialog
        {...props}
        selectionIdentity="subject-2:workspaces:management:1:2"
        resource={{ ...workspace, id: 'ws-2', name: 'Workspace Two' }}
        isSubmitting={false}
      />,
    );
    await act(async () => { request.resolve(); });

    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('does not let an old quota completion close a new context dialog', async () => {
    const request = deferred();
    const onClose = vi.fn();
    const props = {
      isSubmitting: false,
      hasError: false,
      onSubmit: () => request.promise,
      onClose,
    };
    const view = render(
      <KnowledgeBaseQuotaDialog
        {...props}
        selectionIdentity="subject-1:knowledge-bases:management:0:1"
        resource={knowledgeBase}
      />,
    );
    const oldDialog = screen.getByRole('dialog');
    fireEvent.change(within(oldDialog).getByLabelText(
      'platformResources.quotaDialog.quotaGiBLabel',
    ), { target: { value: '8' } });
    fireEvent.click(within(oldDialog).getByRole('button', {
      name: 'platformResources.quotaDialog.confirm',
    }));

    view.rerender(
      <KnowledgeBaseQuotaDialog
        {...props}
        selectionIdentity="subject-2:knowledge-bases:management:1:2"
        resource={{ ...knowledgeBase, id: 'kb-2', name: 'Knowledge Base Two' }}
      />,
    );
    await act(async () => { request.resolve(); });

    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
