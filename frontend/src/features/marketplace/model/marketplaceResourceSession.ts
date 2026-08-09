import React from 'react';
import type { MarketplaceProvider } from './marketplaceTypes';
import {
  createFileTreeResourceIdentity,
  FileTreeAsyncCoordinator,
  serializeFileTreeResourceIdentity,
  StaleFileTreeRequestError,
  type FileTreeAsyncRequest,
} from '@/shared/components/file-workbench';
import type { MarketplacePackageMutationResult } from './marketplaceMutation';

export interface MarketplaceResourceIdentity {
  provider: MarketplaceProvider | null;
  packageId: string;
  resourceType: string;
}

export interface MarketplaceResourceQueryLifecycle<T> {
  onSuccess(value: T): void | Promise<void>;
  onError?(error: unknown): void | Promise<void>;
  onSettled?(): void | Promise<void>;
}

const toFileTreeIdentity = (identity: MarketplaceResourceIdentity) => (
  createFileTreeResourceIdentity('marketplace-resource', {
    provider: identity.provider ?? 'unresolved',
    packageId: identity.packageId,
    resourceType: identity.resourceType,
  })
);

interface MarketplaceResourceSessionOptions {
  identityGeneration?: number;
  isIdentityCommitted?: () => boolean;
}

export class MarketplaceResourceSession {
  private readonly coordinator: FileTreeAsyncCoordinator;
  private readonly isIdentityCommitted: () => boolean;
  private currentRevision: string;

  constructor(
    identity: MarketplaceResourceIdentity,
    initialRevision: string,
    options: MarketplaceResourceSessionOptions = {},
  ) {
    this.coordinator = new FileTreeAsyncCoordinator(
      toFileTreeIdentity(identity),
      options.identityGeneration,
    );
    this.isIdentityCommitted = options.isIdentityCommitted ?? (() => true);
    this.currentRevision = initialRevision;
  }

  get identityKey(): string {
    return this.coordinator.identityKey;
  }

  get identityGeneration(): number {
    return this.coordinator.identityGeneration;
  }

  get revision(): string {
    return this.currentRevision;
  }

  updateIdentity(
    identity: MarketplaceResourceIdentity,
    initialRevision: string,
  ): boolean {
    const changed = this.coordinator.updateIdentity(toFileTreeIdentity(identity));
    if (changed) {
      this.currentRevision = initialRevision;
    }
    return changed;
  }

  acceptMutation(
    generation: number,
    result: MarketplacePackageMutationResult,
  ): void {
    this.assertCommittedGeneration(generation);
    this.currentRevision = result.revision;
  }

  async run<T>(
    generation: number,
    channel: string,
    operation: () => Promise<T>,
  ): Promise<T> {
    this.assertCommittedGeneration(generation);
    try {
      const result = await this.coordinator.runForGeneration(
        generation,
        channel,
        operation,
      );
      this.assertCommittedGeneration(generation);
      return result;
    } catch (error) {
      this.assertCommittedGeneration(generation);
      throw error;
    }
  }

  async query<T>(
    generation: number,
    channel: string,
    operation: () => Promise<T>,
    lifecycle: MarketplaceResourceQueryLifecycle<T>,
  ): Promise<void> {
    const request = this.beginForGeneration(generation, channel);
    if (!request) {
      return;
    }

    try {
      const value = await operation();
      if (this.isCurrent(request)) {
        await lifecycle.onSuccess(value);
      }
    } catch (error) {
      if (this.isCurrent(request)) {
        await lifecycle.onError?.(error);
      }
    } finally {
      const settlement = this.coordinator.finishRequest(request);
      if (
        this.isCommittedGeneration(request.generation)
        && settlement.isCurrent
      ) {
        await lifecycle.onSettled?.();
      }
    }
  }

  async mutate<T extends MarketplacePackageMutationResult>(
    generation: number,
    channel: string,
    operation: () => Promise<T>,
    onCurrent?: (result: T) => void | Promise<void>,
    onSettled?: () => void | Promise<void>,
  ): Promise<T> {
    const request = this.beginForGeneration(generation, channel);
    if (!request) {
      throw new StaleFileTreeRequestError();
    }

    try {
      const result = await operation();
      this.assertCurrent(request);
      this.currentRevision = result.revision;
      await onCurrent?.(result);
      this.assertCurrent(request);
      return result;
    } catch (error) {
      this.assertCurrent(request);
      throw error;
    } finally {
      const settlement = this.coordinator.finishRequest(request);
      if (
        this.isCommittedGeneration(request.generation)
        && settlement.isCurrent
      ) {
        await onSettled?.();
      }
    }
  }

  private beginForGeneration(
    generation: number,
    channel: string,
  ): FileTreeAsyncRequest | null {
    try {
      this.assertCommittedGeneration(generation);
      return this.coordinator.beginRequestForGeneration(generation, channel);
    } catch (error) {
      if (error instanceof StaleFileTreeRequestError) {
        return null;
      }
      throw error;
    }
  }

  private isCommittedGeneration(generation: number): boolean {
    return (
      this.isIdentityCommitted()
      && generation === this.coordinator.identityGeneration
    );
  }

  private assertCommittedGeneration(generation: number): void {
    if (!this.isCommittedGeneration(generation)) {
      throw new StaleFileTreeRequestError();
    }
  }

  private isCurrent(request: FileTreeAsyncRequest): boolean {
    return (
      this.isIdentityCommitted()
      && this.coordinator.isCurrent(request)
    );
  }

  private assertCurrent(request: FileTreeAsyncRequest): void {
    if (!this.isCurrent(request)) {
      throw new StaleFileTreeRequestError();
    }
  }
}

export const useMarketplaceResourceSession = (
  identity: MarketplaceResourceIdentity,
  initialRevision: string,
): {
  identityGeneration: number;
  identityKey: string;
  session: MarketplaceResourceSession;
} => {
  const identityKey = serializeFileTreeResourceIdentity(toFileTreeIdentity(identity));
  const committedIdentityKeyRef = React.useRef(identityKey);
  const committedSessionRef = React.useRef<MarketplaceResourceSession | null>(null);
  if (!committedSessionRef.current) {
    committedSessionRef.current = new MarketplaceResourceSession(
      identity,
      initialRevision,
      {
        isIdentityCommitted: () => committedIdentityKeyRef.current === identityKey,
      },
    );
  }
  const session = React.useMemo(() => {
    const committedSession = committedSessionRef.current!;
    if (committedSession.identityKey === identityKey) {
      return committedSession;
    }
    return new MarketplaceResourceSession(identity, initialRevision, {
      identityGeneration: committedSession.identityGeneration + 1,
      isIdentityCommitted: () => committedIdentityKeyRef.current === identityKey,
    });
  }, [identity, identityKey, initialRevision]);
  React.useLayoutEffect(() => {
    committedIdentityKeyRef.current = identityKey;
    committedSessionRef.current = session;
  }, [identityKey, session]);

  return {
    identityGeneration: session.identityGeneration,
    identityKey: session.identityKey,
    session,
  };
};
