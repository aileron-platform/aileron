import { describe, expect, it } from 'vitest';
import type { WorkspaceAvailabilityResponse } from '../api/workspaceLifecycleApi';
import {
  createWorkspaceAvailabilityMachine,
  transitionWorkspaceAvailability,
  type WorkspaceAvailabilityMachine,
} from './workspaceAvailabilityMachine';

const knowledgeMountStatus = {
  status: 'ready' as const,
  desiredRevision: 2,
  observedRevision: 2,
  lastKnownGoodRevision: 2,
  errorCode: null,
  compensating: false,
};

const availabilityFixture = (
  overrides: Partial<WorkspaceAvailabilityResponse> = {},
): WorkspaceAvailabilityResponse => ({
  workspaceId: 'ws-1',
  availability: 'ready',
  reasonCode: 'WORKSPACE_READY',
  runtimeStatus: 'running',
  runtimeInstanceId: 'runtime-1',
  runtimeAccessDesiredRevision: 2,
  runtimeAccessObservedRevision: 2,
  retryable: false,
  allowedActions: [],
  retryAfterMs: 10_000,
  knowledgeMountStatus,
  deletion: {
    availability: 'ready',
    allowedActions: ['delete'],
    phase: null,
    status: null,
    errorCode: null,
  },
  ...overrides,
});

const createMachine = (
  workspaceId = 'ws-1',
  epoch = 1,
): WorkspaceAvailabilityMachine =>
  createWorkspaceAvailabilityMachine({
    workspaceId,
    authorizationResolved: true,
    canRead: true,
    canRunLifecycle: true,
    route: {
      pathname: `/workspaces/${workspaceId}/files`,
      returnTarget: `/workspaces/${workspaceId}/files?open=%2FREADME.md`,
    },
    restoredReturnTarget: null,
    epoch,
  });

const resolveReady = (
  machine: WorkspaceAvailabilityMachine,
  requestId: number,
  runtimeInstanceId = 'runtime-1',
  now = 1_000,
): WorkspaceAvailabilityMachine => transitionWorkspaceAvailability(
  transitionWorkspaceAvailability(machine, {
    type: 'availability-request-started',
    epoch: machine.state.epoch,
    requestId,
  }),
  {
    type: 'availability-resolved',
    epoch: machine.state.epoch,
    requestId,
    availability: availabilityFixture({ runtimeInstanceId }),
    now,
  },
);

describe('Workspace availability machine', () => {
  it('uses request identity rather than timestamps to release a generation fence', () => {
    let machine = resolveReady(createMachine(), 1, 'runtime-1', 1_000);
    machine = transitionWorkspaceAvailability(machine, {
      type: 'runtime-generation-mismatch',
      epoch: machine.state.epoch,
      affectedWorkspaceId: 'ws-1',
      now: 1_000,
    });

    machine = resolveReady(machine, 2, 'runtime-2', 1_000);

    expect(machine.state.generationFence).toBeNull();
    expect(machine.state.gate).toMatchObject({
      kind: 'ready-waiting-for-loading',
      availability: { runtimeInstanceId: 'runtime-2' },
    });
    const minimumLoading = machine.state.pendingCommands.find(
      command => command.kind === 'schedule-minimum-loading',
    );
    expect(minimumLoading?.kind).toBe('schedule-minimum-loading');
    if (!minimumLoading || minimumLoading.kind !== 'schedule-minimum-loading') return;

    machine = transitionWorkspaceAvailability(machine, {
      type: 'minimum-loading-elapsed',
      epoch: machine.state.epoch,
      loadingToken: minimumLoading.loadingToken,
      commandId: minimumLoading.id,
    });
    expect(machine.state.gate).toMatchObject({
      kind: 'ready',
      availability: { runtimeInstanceId: 'runtime-2' },
    });
  });

  it('keeps a late ready response from the fenced request closed', () => {
    let machine = resolveReady(createMachine(), 1);
    machine = transitionWorkspaceAvailability(machine, {
      type: 'runtime-generation-mismatch',
      epoch: machine.state.epoch,
      affectedWorkspaceId: 'ws-1',
      now: 2_000,
    });

    machine = transitionWorkspaceAvailability(machine, {
      type: 'availability-resolved',
      epoch: machine.state.epoch,
      requestId: 1,
      availability: availabilityFixture({ runtimeInstanceId: 'runtime-late' }),
      now: 3_000,
    });

    expect(machine.state.gate.kind).toBe('generation-fenced');
    expect(machine.state.generationFence).not.toBeNull();
  });

  it('ignores a runtime mismatch belonging to another workspace', () => {
    const ready = resolveReady(createMachine(), 1);
    const next = transitionWorkspaceAvailability(ready, {
      type: 'runtime-generation-mismatch',
      epoch: ready.state.epoch,
      affectedWorkspaceId: 'ws-2',
      now: 2_000,
    });

    expect(next.state.gate.kind).toBe('ready');
    expect(next.state.generationFence).toBeNull();
  });

  it('ignores a lifecycle rejection from the previous workspace epoch', () => {
    let machine = createMachine();
    machine = transitionWorkspaceAvailability(machine, {
      type: 'availability-resolved',
      epoch: machine.state.epoch,
      requestId: 1,
      availability: availabilityFixture({
        availability: 'blocked',
        reasonCode: 'WORKSPACE_RUNTIME_ERROR',
        runtimeStatus: 'error',
        allowedActions: ['retry', 'return'],
      }),
      now: 1_000,
    });
    machine = transitionWorkspaceAvailability(machine, {
      type: 'lifecycle-requested',
      action: 'retry',
    });
    const oldEpoch = machine.state.epoch;
    const oldCommandId = machine.state.actionCommandId;
    expect(oldCommandId).not.toBeNull();

    machine = createMachine('ws-2', oldEpoch + 1);
    machine = transitionWorkspaceAvailability(machine, {
      type: 'lifecycle-rejected',
      epoch: oldEpoch,
      commandId: oldCommandId!,
      errorCode: 'WORKSPACE_NOT_FOUND',
    });

    expect(machine.state.workspaceId).toBe('ws-2');
    expect(machine.state.actionErrorCode).toBeNull();
    expect(machine.state.actionInFlight).toBeNull();
  });

  it('drops a queued lifecycle command when lifecycle access is revoked', () => {
    let machine = createMachine();
    machine = transitionWorkspaceAvailability(machine, {
      type: 'availability-resolved',
      epoch: machine.state.epoch,
      requestId: 1,
      availability: availabilityFixture({
        availability: 'blocked',
        reasonCode: 'WORKSPACE_RUNTIME_ERROR',
        runtimeStatus: 'error',
        allowedActions: ['retry', 'return'],
      }),
      now: 1_000,
    });
    machine = transitionWorkspaceAvailability(machine, {
      type: 'lifecycle-requested',
      action: 'retry',
    });
    expect(machine.state.pendingCommands.some(
      command => command.kind === 'run-lifecycle-action',
    )).toBe(true);

    machine = transitionWorkspaceAvailability(machine, {
      type: 'authorization-changed',
      authorizationResolved: true,
      canRead: true,
      canRunLifecycle: false,
    });

    expect(machine.state.pendingCommands.some(
      command => command.kind === 'run-lifecycle-action',
    )).toBe(false);
    expect(machine.state.actionInFlight).toBeNull();
    expect(machine.state.actionCommandId).toBeNull();
  });
});
