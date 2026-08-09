import { describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import {
  getWorkspaceKnowledgeBaseErrorTranslationKey,
  MountedKnowledgeBasesPanel,
} from './MountedKnowledgeBasesPanel';

const { translateMock } = vi.hoisted(() => ({
  translateMock: vi.fn((key: string) => {
    const translations: Record<string, string> = {
      'workspace.workspaceSettings.knowledgeBases.mounted.title': 'Runtime synchronization',
      'workspace.workspaceSettings.knowledgeBases.mounted.mount.title': 'Knowledge base mounts',
      'workspace.workspaceSettings.knowledgeBases.mounted.access.title': 'Workspace access recycle',
      'workspace.workspaceSettings.knowledgeBases.mounted.mount.status.ready': 'Ready',
      'workspace.workspaceSettings.knowledgeBases.mounted.mount.status.syncing': 'Syncing',
      'workspace.workspaceSettings.knowledgeBases.mounted.mount.status.degraded': 'Degraded',
      'workspace.workspaceSettings.knowledgeBases.mounted.access.status.ready': 'Access ready',
      'workspace.workspaceSettings.knowledgeBases.mounted.access.status.recycling': 'Recycling',
      'workspace.workspaceSettings.knowledgeBases.mounted.desiredRevision': 'Desired revision',
      'workspace.workspaceSettings.knowledgeBases.mounted.observedRevision': 'Observed revision',
      'workspace.workspaceSettings.knowledgeBases.mounted.lastKnownGoodRevision': 'Last-known-good revision',
      'workspace.workspaceSettings.knowledgeBases.mounted.degradedTitle': 'Mount synchronization is degraded',
      'workspace.workspaceSettings.knowledgeBases.mounted.compensating.title':
        'Restoring the last-known-good mounts',
      'workspace.workspaceSettings.knowledgeBases.mounted.compensating.description':
        'The failed candidate is being rolled back.',
      'workspace.workspaceSettings.knowledgeBases.mounted.retry': 'Retry synchronization',
      'workspace.workspaceSettings.knowledgeBases.mounted.retrying': 'Retrying...',
      'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_KB_MOUNT_RECONCILE_FAILED':
        'Knowledge base mount reconciliation failed.',
      'workspace.workspaceSettings.knowledgeBases.errors.unknown':
        'The knowledge base operation failed.',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: translateMock }),
}));

describe('MountedKnowledgeBasesPanel', () => {
  it.each([
    'WORKSPACE_KB_MOUNT_RECONCILE_FAILED',
    'WORKSPACE_KB_MOUNT_JOB_INVALID',
    'WORKSPACE_KB_MOUNT_SNAPSHOT_INVALID',
    'WORKSPACE_KB_MOUNT_STATE_INVALID',
    'WORKSPACE_LIFECYCLE_FAILED',
  ])('maps the persisted mount error code %s to an explicit i18n key', (errorCode) => {
    expect(getWorkspaceKnowledgeBaseErrorTranslationKey(errorCode)).toBe(
      `workspace.workspaceSettings.knowledgeBases.errors.${errorCode}`,
    );
  });

  it('renders mount and access revisions with their independent ready states', () => {
    render(
      <MountedKnowledgeBasesPanel
        mountSync={{
          status: 'ready',
          desiredRevision: 12,
          observedRevision: 12,
          lastKnownGoodRevision: 12,
          errorCode: null,
          compensating: false,
        }}
        runtimeAccessRevision={7}
        runtimeAccessObservedRevision={7}
        canRetry
        isRetrying={false}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('Runtime synchronization')).toBeInTheDocument();
    expect(screen.getByText('Knowledge base mounts')).toBeInTheDocument();
    expect(screen.getByText('Workspace access recycle')).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('Access ready')).toBeInTheDocument();
    expect(screen.getAllByText('12')).toHaveLength(3);
    expect(screen.getAllByText('7')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Retry synchronization' })).not.toBeInTheDocument();
  });

  it('maps a degraded errorCode to i18n and offers retry', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn().mockResolvedValue(undefined);

    render(
      <MountedKnowledgeBasesPanel
        mountSync={{
          status: 'degraded',
          desiredRevision: 13,
          observedRevision: 12,
          lastKnownGoodRevision: 12,
          errorCode: 'WORKSPACE_KB_MOUNT_RECONCILE_FAILED',
          compensating: false,
        }}
        runtimeAccessRevision={8}
        runtimeAccessObservedRevision={7}
        canRetry
        isRetrying={false}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText('Recycling')).toBeInTheDocument();
    expect(screen.getByText('Knowledge base mount reconciliation failed.')).toBeInTheDocument();
    expect(screen.queryByText('WORKSPACE_KB_MOUNT_RECONCILE_FAILED')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry synchronization' }));

    await waitFor(() => expect(onRetry).toHaveBeenCalledTimes(1));
  });

  it('does not offer retry to a read-only workspace member', () => {
    render(
      <MountedKnowledgeBasesPanel
        mountSync={{
          status: 'degraded',
          desiredRevision: 2,
          observedRevision: 1,
          lastKnownGoodRevision: 1,
          errorCode: 'UNRECOGNIZED_CODE',
          compensating: false,
        }}
        canRetry={false}
        isRetrying={false}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('The knowledge base operation failed.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry synchronization' })).not.toBeInTheDocument();
  });

  it('shows compensation progress without exposing a conflicting retry action', () => {
    render(
      <MountedKnowledgeBasesPanel
        mountSync={{
          status: 'syncing',
          desiredRevision: 14,
          observedRevision: 12,
          lastKnownGoodRevision: 12,
          errorCode: 'WORKSPACE_KB_MOUNT_RECONCILE_FAILED',
          compensating: true,
        }}
        canRetry
        isRetrying={false}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('Restoring the last-known-good mounts')).toBeInTheDocument();
    expect(screen.getByText('The failed candidate is being rolled back.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry synchronization' })).not.toBeInTheDocument();
  });
});
