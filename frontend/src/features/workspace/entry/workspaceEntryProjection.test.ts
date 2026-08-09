import { describe, expect, it } from 'vitest';
import { projectWorkspaceEntry } from './workspaceEntryProjection';
import { projectPlatformIdentityEntry } from '@/shared/components/entry/platformIdentityEntryProjection';
import {
  WORKSPACE_ENTRY_STAGE_IDS,
  type WorkspaceEntryProjectionInput,
} from '@/shared/components/entry/workspaceEntryTypes';

const baseInput = (
  overrides: Partial<WorkspaceEntryProjectionInput> = {},
): WorkspaceEntryProjectionInput => ({
  identity: {
    status: 'authenticated',
  },
  workspace: {
    status: 'checking',
    canCreate: false,
  },
  execution: {
    status: 'checking',
    allowedActions: [],
  },
  ...overrides,
});

describe('workspace entry projection', () => {
  it('projects the fixed workspace stages while identity is checking', () => {
    const projection = projectWorkspaceEntry(baseInput({
      identity: { status: 'checking' },
    }));

    expect(projection.stages).toEqual([
      { id: 'identity', status: 'active' },
      { id: 'workspace', status: 'pending' },
      { id: 'execution', status: 'pending' },
    ]);
    expect(projection.activeStage).toBe('identity');
    expect(projection.actions).toEqual([]);
  });

  it('requires login after an identity failure without exposing the raw error', () => {
    const projection = projectPlatformIdentityEntry({
      status: 'failed',
      reasonCode: 'AUTH_CALLBACK_FAILED',
    });

    expect(projection.stages).toEqual([
      { id: 'identity', status: 'failed' },
    ]);
    expect(projection.actions).toEqual([
      { id: 'login', emphasis: 'primary' },
    ]);
    expect(projection.reasonCode).toBe('AUTH_CALLBACK_FAILED');
    expect(projection.reasonCode).not.toContain('Error');
  });

  it('keeps an unauthenticated identity active until login completes', () => {
    const projection = projectPlatformIdentityEntry({
      status: 'unauthenticated',
    });

    expect(projection.stages).toEqual([
      { id: 'identity', status: 'active' },
    ]);
    expect(projection.actions).toEqual([
      { id: 'login', emphasis: 'primary' },
    ]);
  });

  it('offers create only when the platform confirms creation permission', () => {
    const projection = projectWorkspaceEntry(baseInput({
      workspace: { status: 'empty', canCreate: true },
    }));

    expect(projection.activeStage).toBe('workspace');
    expect(projection.stages[1]).toEqual({
      id: 'workspace',
      status: 'action_required',
    });
    expect(projection.actions).toEqual([
      { id: 'create', emphasis: 'primary' },
    ]);
  });

  it('keeps an empty workspace actionable without inventing create permission', () => {
    const projection = projectWorkspaceEntry(baseInput({
      workspace: { status: 'empty', canCreate: false },
    }));

    expect(projection.actions).toEqual([]);
    expect(projection.stages[1].status).toBe('action_required');
  });

  it('maps stopped Runtime to start and keeps lifecycle actions API-owned', () => {
    const projection = projectWorkspaceEntry(baseInput({
      workspace: { status: 'ready', canCreate: false },
      execution: {
        status: 'stopped',
        reasonCode: 'WORKSPACE_RUNTIME_STOPPED',
        allowedActions: ['start', 'rebuild', 'unknown-action'],
      },
    }));

    expect(projection.stages).toEqual([
      { id: 'identity', status: 'complete' },
      { id: 'workspace', status: 'complete' },
      { id: 'execution', status: 'action_required' },
    ]);
    expect(projection.actions).toEqual([
      { id: 'start', emphasis: 'primary' },
      { id: 'rebuild', emphasis: 'danger-secondary' },
    ]);
  });

  it('preserves API-owned actions while Runtime is transitioning', () => {
    const projection = projectWorkspaceEntry(baseInput({
      workspace: { status: 'ready', canCreate: false },
      execution: {
        status: 'transitioning',
        reasonCode: 'WORKSPACE_RUNTIME_STARTING',
        allowedActions: ['retry', 'return'],
      },
    }));

    expect(projection.actions).toEqual([
      { id: 'retry', emphasis: 'primary' },
      { id: 'return', emphasis: 'secondary' },
    ]);
  });

  it('preserves API-owned actions while deletion progress is shown', () => {
    const projection = projectWorkspaceEntry(baseInput({
      workspace: {
        status: 'deleting',
        allowedActions: ['start', 'return'],
        reasonCode: 'WORKSPACE_DELETING',
      },
      execution: {
        status: 'checking',
        allowedActions: [],
      },
    }));

    expect(projection.actions).toEqual([
      { id: 'start', emphasis: 'primary' },
      { id: 'return', emphasis: 'secondary' },
    ]);
    expect(projection.reasonCode).toBe('WORKSPACE_DELETING');
  });

  it('uses local refresh for uncertain evidence and never marks it failed', () => {
    const projection = projectWorkspaceEntry(baseInput({
      workspace: { status: 'ready', canCreate: false },
      execution: {
        status: 'uncertain',
        reasonCode: 'WORKSPACE_AVAILABILITY_UNCERTAIN',
        allowedActions: ['retry', 'return'],
      },
    }));

    expect(projection.stages[2]).toEqual({
      id: 'execution',
      status: 'uncertain',
    });
    expect(projection.actions).toEqual([
      { id: 'refresh', emphasis: 'primary' },
      { id: 'return', emphasis: 'secondary' },
    ]);
  });

  it('keeps a ready workspace out of the entry gate', () => {
    const projection = projectWorkspaceEntry(baseInput({
      workspace: { status: 'ready', canCreate: false },
      execution: {
        status: 'ready',
        allowedActions: [],
      },
    }));

    expect(projection.stages).toEqual([
      { id: 'identity', status: 'complete' },
      { id: 'workspace', status: 'complete' },
      { id: 'execution', status: 'complete' },
    ]);
    expect(projection.activeStage).toBe('execution');
  });

  it('preserves the canonical stage order as a fixed public contract', () => {
    expect(WORKSPACE_ENTRY_STAGE_IDS).toEqual([
      'identity',
      'workspace',
      'execution',
    ]);
  });
});
