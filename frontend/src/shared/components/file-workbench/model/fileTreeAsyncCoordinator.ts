export type FileTreeResourceIdentityValue =
  | string
  | number
  | boolean
  | null
  | readonly string[];

export interface FileTreeResourceIdentity {
  kind: string;
  attributes: Readonly<Record<string, FileTreeResourceIdentityValue>>;
}

export const createFileTreeResourceIdentity = (
  kind: string,
  attributes: Readonly<Record<string, FileTreeResourceIdentityValue>>,
): FileTreeResourceIdentity => ({
  kind,
  attributes,
});

export const serializeFileTreeResourceIdentity = (
  identity: FileTreeResourceIdentity,
): string => JSON.stringify({
  kind: identity.kind,
  attributes: Object.fromEntries(
    Object.entries(identity.attributes).sort(([left], [right]) => left.localeCompare(right)),
  ),
});

export class StaleFileTreeRequestError extends Error {
  constructor() {
    super('File tree request became stale before it settled');
    this.name = 'StaleFileTreeRequestError';
  }
}

export const isStaleFileTreeRequestError = (error: unknown): boolean => (
  error instanceof StaleFileTreeRequestError
);

export interface FileTreeAsyncRequest {
  channel: string;
  generation: number;
  identityKey: string;
  requestId: number;
}

export interface FileTreeAsyncRequestSettlement {
  currentChannelRequestCount: number;
  isCurrent: boolean;
  isCurrentChannelIdle: boolean;
}

export class FileTreeAsyncCoordinator {
  private currentIdentityKey: string;
  private generation: number;
  private nextRequestId = 0;
  private readonly activeRequestKeys = new Set<string>();
  private readonly activeRequestCounts = new Map<string, number>();
  private readonly latestRequestIds = new Map<string, number>();

  constructor(identity: FileTreeResourceIdentity, initialGeneration = 0) {
    this.currentIdentityKey = serializeFileTreeResourceIdentity(identity);
    this.generation = initialGeneration;
  }

  get identityKey(): string {
    return this.currentIdentityKey;
  }

  get identityGeneration(): number {
    return this.generation;
  }

  updateIdentity(identity: FileTreeResourceIdentity): boolean {
    const nextIdentityKey = serializeFileTreeResourceIdentity(identity);
    if (nextIdentityKey === this.currentIdentityKey) {
      return false;
    }

    this.currentIdentityKey = nextIdentityKey;
    this.generation += 1;
    return true;
  }

  beginRequest(channel: string): FileTreeAsyncRequest {
    const request: FileTreeAsyncRequest = {
      channel,
      generation: this.generation,
      identityKey: this.currentIdentityKey,
      requestId: this.nextRequestId + 1,
    };
    this.nextRequestId = request.requestId;

    const requestKey = this.requestKey(request);
    const countKey = this.countKey(request.generation, channel);
    this.activeRequestKeys.add(requestKey);
    this.activeRequestCounts.set(countKey, (this.activeRequestCounts.get(countKey) ?? 0) + 1);
    this.latestRequestIds.set(countKey, request.requestId);

    return request;
  }

  beginRequestForGeneration(
    generation: number,
    channel: string,
  ): FileTreeAsyncRequest {
    if (this.generation !== generation) {
      throw new StaleFileTreeRequestError();
    }
    return this.beginRequest(channel);
  }

  isCurrent(request: FileTreeAsyncRequest): boolean {
    const countKey = this.countKey(request.generation, request.channel);
    return (
      request.generation === this.generation
      && request.identityKey === this.currentIdentityKey
      && this.latestRequestIds.get(countKey) === request.requestId
    );
  }

  assertCurrent(request: FileTreeAsyncRequest): void {
    if (!this.isCurrent(request)) {
      throw new StaleFileTreeRequestError();
    }
  }

  finishRequest(request: FileTreeAsyncRequest): FileTreeAsyncRequestSettlement {
    const requestKey = this.requestKey(request);
    const countKey = this.countKey(request.generation, request.channel);
    const wasCurrent = this.isCurrent(request);
    if (this.activeRequestKeys.delete(requestKey)) {
      const remaining = Math.max(0, (this.activeRequestCounts.get(countKey) ?? 1) - 1);
      if (remaining === 0) {
        this.activeRequestCounts.delete(countKey);
        this.latestRequestIds.delete(countKey);
      } else {
        this.activeRequestCounts.set(countKey, remaining);
      }
    }

    const currentChannelRequestCount = this.currentRequestCount(request.channel);
    return {
      currentChannelRequestCount,
      isCurrent: wasCurrent,
      isCurrentChannelIdle: currentChannelRequestCount === 0,
    };
  }

  currentRequestCount(channel: string): number {
    return this.activeRequestCounts.get(this.countKey(this.generation, channel)) ?? 0;
  }

  async run<T>(channel: string, operation: () => Promise<T>): Promise<T> {
    const request = this.beginRequest(channel);
    return this.runRequest(request, operation);
  }

  async runForGeneration<T>(
    generation: number,
    channel: string,
    operation: () => Promise<T>,
  ): Promise<T> {
    const request = this.beginRequestForGeneration(generation, channel);
    return this.runRequest(request, operation);
  }

  private async runRequest<T>(
    request: FileTreeAsyncRequest,
    operation: () => Promise<T>,
  ): Promise<T> {
    try {
      const result = await operation();
      this.assertCurrent(request);
      return result;
    } catch (error) {
      this.assertCurrent(request);
      throw error;
    } finally {
      this.finishRequest(request);
    }
  }

  private countKey(generation: number, channel: string): string {
    return `${generation}:${channel}`;
  }

  private requestKey(request: FileTreeAsyncRequest): string {
    return `${request.generation}:${request.channel}:${request.requestId}`;
  }
}
