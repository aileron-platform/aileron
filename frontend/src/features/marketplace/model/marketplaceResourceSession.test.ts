import React from 'react';
import { act, render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  MarketplaceResourceSession,
  type MarketplaceResourceIdentity,
  useMarketplaceResourceSession,
} from './marketplaceResourceSession';
import { StaleFileTreeRequestError } from '@/shared/components/file-workbench';

const identity = (
  packageId: string,
  resourceType = 'commands',
): MarketplaceResourceIdentity => ({
  targetClient: 'codex',
  packageId,
  resourceType,
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const mutationResult = () => ({
  success: true as const,
  path: 'commands/stale.md',
  revision: 'stale-rev',
  ownerFilePath: null,
  baseEntryFingerprint: null,
});

describe('MarketplaceResourceSession interface', () => {
  it('resets revision only when the semantic resource identity changes', () => {
    const session = new MarketplaceResourceSession(identity('first'), 'rev1');

    expect(session.updateIdentity(identity('first'), 'ignored')).toBe(false);
    expect(session.revision).toBe('rev1');

    expect(session.updateIdentity(identity('second'), 'rev2')).toBe(true);
    expect(session.revision).toBe('rev2');
  });

  it('uses the mutation response as the canonical revision source', async () => {
    const session = new MarketplaceResourceSession(identity('first'), 'rev1');
    const onCurrent = vi.fn();

    const result = await session.mutate(
      session.identityGeneration,
      'mutation',
      async () => ({
        success: true as const,
        path: 'commands/greet.md',
        revision: 'rev2',
        ownerFilePath: null,
        baseEntryFingerprint: null,
      }),
      onCurrent,
    );

    expect(result.path).toBe('commands/greet.md');
    expect(session.revision).toBe('rev2');
    expect(onCurrent).toHaveBeenCalledWith(result);
  });

  it('fences stale query success, error, and settled callbacks', async () => {
    const session = new MarketplaceResourceSession(identity('first'), 'rev1');
    const success = deferred<string>();
    const failure = deferred<string>();
    const firstLifecycle = {
      onSuccess: vi.fn(),
      onError: vi.fn(),
      onSettled: vi.fn(),
    };
    const secondLifecycle = {
      onSuccess: vi.fn(),
      onError: vi.fn(),
      onSettled: vi.fn(),
    };

    const staleSuccess = session.query(
      session.identityGeneration,
      'tree',
      () => success.promise,
      firstLifecycle,
    );
    const staleFailure = session.query(
      session.identityGeneration,
      'content',
      () => failure.promise,
      secondLifecycle,
    );

    session.updateIdentity(identity('second'), 'rev2');
    success.resolve('stale');
    failure.reject(new Error('stale'));
    await Promise.all([staleSuccess, staleFailure]);

    expect(firstLifecycle.onSuccess).not.toHaveBeenCalled();
    expect(firstLifecycle.onError).not.toHaveBeenCalled();
    expect(firstLifecycle.onSettled).not.toHaveBeenCalled();
    expect(secondLifecycle.onSuccess).not.toHaveBeenCalled();
    expect(secondLifecycle.onError).not.toHaveBeenCalled();
    expect(secondLifecycle.onSettled).not.toHaveBeenCalled();
  });

  it('does not consume a mutation result after identity changes', async () => {
    const session = new MarketplaceResourceSession(identity('first'), 'rev1');
    const pending = deferred<ReturnType<typeof mutationResult>>();
    const onCurrent = vi.fn();
    const mutation = session.mutate(
      session.identityGeneration,
      'mutation',
      () => pending.promise,
      onCurrent,
    );

    session.updateIdentity(identity('second'), 'current-rev');
    pending.resolve(mutationResult());

    await expect(mutation).rejects.toBeInstanceOf(StaleFileTreeRequestError);
    expect(onCurrent).not.toHaveBeenCalled();
    expect(session.revision).toBe('current-rev');
  });

  it('settles only the latest same-identity query', async () => {
    const session = new MarketplaceResourceSession(identity('first'), 'rev1');
    const older = deferred<string>();
    const latest = deferred<string>();
    const olderSettled = vi.fn();
    const latestSettled = vi.fn();

    const olderRequest = session.query(
      session.identityGeneration,
      'tree',
      () => older.promise,
      { onSuccess: vi.fn(), onSettled: olderSettled },
    );
    const latestRequest = session.query(
      session.identityGeneration,
      'tree',
      () => latest.promise,
      { onSuccess: vi.fn(), onSettled: latestSettled },
    );

    latest.resolve('latest');
    await latestRequest;
    expect(latestSettled).toHaveBeenCalledTimes(1);

    older.resolve('older');
    await olderRequest;
    expect(olderSettled).not.toHaveBeenCalled();
  });

  it('keeps the committed session active when another render is abandoned', async () => {
    const pending = deferred<string>();
    const suspended = new Promise<never>(() => undefined);
    const onSuccess = vi.fn();
    const onSettled = vi.fn();
    let committed: ReturnType<typeof useMarketplaceResourceSession> | undefined;

    const Harness: React.FC<{
      packageId: string;
      shouldSuspend: boolean;
    }> = ({ packageId, shouldSuspend }) => {
      const current = useMarketplaceResourceSession(identity(packageId), 'rev1');
      React.useLayoutEffect(() => {
        committed = current;
      }, [current]);
      if (shouldSuspend) {
        throw suspended;
      }
      return null;
    };
    const renderHarness = (packageId: string, shouldSuspend: boolean) => (
      React.createElement(
        React.Suspense,
        { fallback: null },
        React.createElement(Harness, { packageId, shouldSuspend }),
      )
    );

    const view = render(renderHarness('first', false));
    const query = committed!.session.query(
      committed!.identityGeneration,
      'tree',
      () => pending.promise,
      { onSuccess, onSettled },
    );

    view.rerender(renderHarness('second', true));
    view.rerender(renderHarness('first', false));

    await act(async () => {
      pending.resolve('current');
      await query;
    });

    expect(onSuccess).toHaveBeenCalledWith('current');
    expect(onSettled).toHaveBeenCalledTimes(1);
    expect(committed?.identityGeneration).toBe(0);
    expect(committed?.session.revision).toBe('rev1');
  });

  it('fences the previous session after a new identity commits', async () => {
    const pending = deferred<string>();
    const onSuccess = vi.fn();
    const onSettled = vi.fn();
    let committed: ReturnType<typeof useMarketplaceResourceSession> | undefined;

    const Harness: React.FC<{ packageId: string }> = ({ packageId }) => {
      const current = useMarketplaceResourceSession(identity(packageId), 'rev1');
      React.useLayoutEffect(() => {
        committed = current;
      }, [current]);
      return null;
    };
    const view = render(React.createElement(Harness, { packageId: 'first' }));
    const query = committed!.session.query(
      committed!.identityGeneration,
      'tree',
      () => pending.promise,
      { onSuccess, onSettled },
    );

    view.rerender(React.createElement(Harness, { packageId: 'second' }));

    await act(async () => {
      pending.resolve('stale');
      await query;
    });

    expect(onSuccess).not.toHaveBeenCalled();
    expect(onSettled).not.toHaveBeenCalled();
    expect(committed?.identityGeneration).toBe(1);
  });
});
