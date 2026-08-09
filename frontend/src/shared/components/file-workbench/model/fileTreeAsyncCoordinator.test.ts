import { describe, expect, it, vi } from 'vitest';
import {
  createFileTreeResourceIdentity,
  FileTreeAsyncCoordinator,
  isStaleFileTreeRequestError,
  serializeFileTreeResourceIdentity,
} from './fileTreeAsyncCoordinator';

const workspaceIdentity = (
  workspaceId: string,
  includeHidden = false,
) => createFileTreeResourceIdentity('workspace', {
  contextId: null,
  includeHidden,
  runtimeBaseUrl: 'https://runtime.example.test',
  workspaceId,
});

describe('FileTreeAsyncCoordinator', () => {
  it('serializes semantic attributes in a stable order', () => {
    const left = createFileTreeResourceIdentity('workspace', {
      workspaceId: 'ws-1',
      includeHidden: false,
    });
    const right = createFileTreeResourceIdentity('workspace', {
      includeHidden: false,
      workspaceId: 'ws-1',
    });

    expect(serializeFileTreeResourceIdentity(left))
      .toBe(serializeFileTreeResourceIdentity(right));
  });

  it('keeps the generation when the semantic identity is unchanged', () => {
    const coordinator = new FileTreeAsyncCoordinator(workspaceIdentity('ws-1'));

    expect(coordinator.updateIdentity(workspaceIdentity('ws-1'))).toBe(false);
    expect(coordinator.identityGeneration).toBe(0);
  });

  it('starts at an explicitly committed identity generation', () => {
    const coordinator = new FileTreeAsyncCoordinator(workspaceIdentity('ws-2'), 3);

    expect(coordinator.identityGeneration).toBe(3);
    expect(coordinator.identityKey)
      .toBe(serializeFileTreeResourceIdentity(workspaceIdentity('ws-2')));
  });

  it('invalidates every request from the previous identity', () => {
    const coordinator = new FileTreeAsyncCoordinator(workspaceIdentity('ws-1'));
    const previousRequest = coordinator.beginRequest('tree');

    expect(coordinator.updateIdentity(workspaceIdentity('ws-2'))).toBe(true);
    expect(coordinator.isCurrent(previousRequest)).toBe(false);
    expect(() => coordinator.assertCurrent(previousRequest))
      .toThrow('File tree request became stale before it settled');
  });

  it('only lets the latest request in a channel publish its result', () => {
    const coordinator = new FileTreeAsyncCoordinator(workspaceIdentity('ws-1'));
    const previousRequest = coordinator.beginRequest('tree');
    const latestRequest = coordinator.beginRequest('tree');

    expect(coordinator.isCurrent(previousRequest)).toBe(false);
    expect(coordinator.isCurrent(latestRequest)).toBe(true);
  });

  it('does not let a stale settlement change current loading counts', () => {
    const coordinator = new FileTreeAsyncCoordinator(workspaceIdentity('ws-1'));
    const previousRequest = coordinator.beginRequest('tree');
    coordinator.updateIdentity(workspaceIdentity('ws-2'));
    const currentRequest = coordinator.beginRequest('tree');

    const staleSettlement = coordinator.finishRequest(previousRequest);

    expect(staleSettlement).toEqual({
      currentChannelRequestCount: 1,
      isCurrent: false,
      isCurrentChannelIdle: false,
    });
    expect(coordinator.currentRequestCount('tree')).toBe(1);

    const currentSettlement = coordinator.finishRequest(currentRequest);
    expect(currentSettlement).toEqual({
      currentChannelRequestCount: 0,
      isCurrent: true,
      isCurrentChannelIdle: true,
    });
  });

  it('turns both stale success and stale failure into one identity error', async () => {
    const successCoordinator = new FileTreeAsyncCoordinator(workspaceIdentity('ws-1'));
    const success = successCoordinator.run('content', async () => 'old content');
    successCoordinator.updateIdentity(workspaceIdentity('ws-2'));

    await expect(success).rejects.toSatisfy(isStaleFileTreeRequestError);

    const failureCoordinator = new FileTreeAsyncCoordinator(workspaceIdentity('ws-1'));
    const failure = failureCoordinator.run('content', async () => {
      throw new Error('old failure');
    });
    failureCoordinator.updateIdentity(workspaceIdentity('ws-2'));

    await expect(failure).rejects.toSatisfy(isStaleFileTreeRequestError);
  });

  it('rejects work captured for a previous generation before executing it', async () => {
    const coordinator = new FileTreeAsyncCoordinator(workspaceIdentity('ws-1'));
    const generation = coordinator.identityGeneration;
    coordinator.updateIdentity(workspaceIdentity('ws-2'));
    const currentRequest = coordinator.beginRequest('content');
    const operation = vi.fn(async () => 'old content');

    await expect(
      coordinator.runForGeneration(generation, 'content', operation),
    ).rejects.toSatisfy(isStaleFileTreeRequestError);
    expect(operation).not.toHaveBeenCalled();
    expect(coordinator.isCurrent(currentRequest)).toBe(true);
  });
});
