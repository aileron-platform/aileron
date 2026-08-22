import { afterEach, describe, expect, it, vi } from 'vitest';
import { NekoClient } from './nekoClient';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('NekoClient', () => {
  it('encodes keyboard input using the Neko binary data protocol', () => {
    const sent: ArrayBuffer[] = [];
    const client = new NekoClient();
    Object.defineProperty(client, 'dataChannel', {
      value: {
        readyState: 'open',
        send: (buffer: ArrayBuffer) => sent.push(buffer),
      },
    });

    client.sendKey(0x61, true);
    client.sendKey(0x61, false);

    expect(toBytes(sent[0])).toEqual([0x03, 0x08, 0x00, 0x61, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
    expect(toBytes(sent[1])).toEqual([0x04, 0x08, 0x00, 0x61, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
  });

  it('encodes mouse clicks with the same key event payload expected by Neko', () => {
    const sent: ArrayBuffer[] = [];
    const client = new NekoClient();
    Object.defineProperty(client, 'dataChannel', {
      value: {
        readyState: 'open',
        send: (buffer: ArrayBuffer) => sent.push(buffer),
      },
    });

    client.sendMouseButton(0, true);
    client.sendMouseButton(0, false);

    expect(toBytes(sent[0])).toEqual([0x03, 0x08, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
    expect(toBytes(sent[1])).toEqual([0x04, 0x08, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
  });

  it('encodes signed wheel deltas using the Neko binary data protocol', () => {
    const sent = attachOpenDataChannel(new NekoClient());
    const client = sent.client;

    client.sendWheel(-120, 240);

    expect(toBytes(sent.buffers[0])).toEqual([0x02, 0x04, 0x00, 0x88, 0xff, 0xf0, 0x00]);
  });

  it('encodes non-ASCII text as X11 Unicode keysyms', () => {
    const sent: ArrayBuffer[] = [];
    const client = new NekoClient();
    Object.defineProperty(client, 'dataChannel', {
      value: {
        readyState: 'open',
        send: (buffer: ArrayBuffer) => sent.push(buffer),
      },
    });

    client.sendText('\u4e2d');

    expect(toBytes(sent[0])).toEqual([0x03, 0x08, 0x00, 0x2d, 0x4e, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]);
    expect(toBytes(sent[1])).toEqual([0x04, 0x08, 0x00, 0x2d, 0x4e, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]);
  });

  it('encodes each Unicode code point exactly once, including supplementary CJK', () => {
    const sent = attachOpenDataChannel(new NekoClient());

    sent.client.sendText('A\u{20000}');

    expect(sent.buffers).toHaveLength(4);
    expect(toBytes(sent.buffers[0]).slice(3)).toEqual([0x41, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
    expect(toBytes(sent.buffers[2]).slice(3)).toEqual([0x00, 0x00, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00]);
  });

  it('reports an i18n key when WebRTC enters a terminal failure state', async () => {
    const peerConnection = new FakePeerConnection();
    vi.stubGlobal('MediaStream', FakeMediaStream);
    vi.stubGlobal('RTCPeerConnection', function RTCPeerConnection() {
      return peerConnection;
    });
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    const errors: Error[] = [];
    const client = new NekoClient({ onError: (error) => errors.push(error) });
    const internals = client as unknown as {
      handleSignalProvide(message: {
        event: 'signal/provide';
        id: string;
        lite: boolean;
        sdp: string;
      }): Promise<void>;
    };

    await internals.handleSignalProvide({
      event: 'signal/provide',
      id: 'peer-1',
      lite: true,
      sdp: 'v=0',
    });
    peerConnection.connectionState = 'failed';
    peerConnection.emit('connectionstatechange');

    expect(errors.map((error) => error.message)).toEqual([
      'workspace.browser.error.nekoWebrtcFailed',
    ]);
  });

  it('uses access-scoped TURN credentials instead of the Neko startup ICE list', async () => {
    const peerConnection = new FakePeerConnection();
    const configurations: RTCConfiguration[] = [];
    vi.stubGlobal('MediaStream', FakeMediaStream);
    vi.stubGlobal('RTCPeerConnection', function RTCPeerConnection(
      configuration: RTCConfiguration,
    ) {
      configurations.push(configuration);
      return peerConnection;
    });
    const client = new NekoClient();
    Object.defineProperty(client, 'frontendIceServers', {
      value: [{
        urls: ['turns:turn.example.test:5349'],
        username: 'fresh-username',
        credential: 'fresh-credential',
      }],
    });
    const internals = client as unknown as {
      handleSignalProvide(message: {
        event: 'signal/provide';
        id: string;
        lite: boolean;
        sdp: string;
        ice?: RTCIceServer[];
      }): Promise<void>;
    };

    await internals.handleSignalProvide({
      event: 'signal/provide',
      id: 'peer-1',
      lite: false,
      sdp: 'v=0',
      ice: [{
        urls: ['turn:stale.example.test:3478'],
        username: 'stale-username',
        credential: 'stale-credential',
      }],
    });

    expect(configurations[0].iceServers).toEqual([{
      urls: ['turns:turn.example.test:5349'],
      username: 'fresh-username',
      credential: 'fresh-credential',
    }]);
  });

  it('blames an unreachable ICE server when no relay candidate was gathered', async () => {
    vi.useFakeTimers();
    const peerConnection = new FakePeerConnection();
    vi.stubGlobal('MediaStream', FakeMediaStream);
    vi.stubGlobal('RTCPeerConnection', function RTCPeerConnection() {
      return peerConnection;
    });
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    const errors: Error[] = [];
    const client = new NekoClient({ onError: (error) => errors.push(error) });
    const internals = client as unknown as {
      startConnectionTimer(): void;
      handleSignalProvide(message: {
        event: 'signal/provide';
        id: string;
        lite: boolean;
        sdp: string;
        ice?: RTCIceServer[];
      }): Promise<void>;
    };

    internals.startConnectionTimer();
    await internals.handleSignalProvide({
      event: 'signal/provide',
      id: 'peer-1',
      lite: false,
      sdp: 'v=0',
      ice: [{ urls: ['turn:turn.example.test:3478'] }],
    });
    peerConnection.emitCandidateError('turn:turn.example.test:3478', 701);
    peerConnection.emitCandidate('candidate:1 1 udp 1 10.0.0.1 5000 typ host');
    vi.advanceTimersByTime(20_000);

    expect(errors.map((error) => error.message)).toEqual([
      'workspace.browser.error.nekoIceServerUnreachable',
    ]);
  });

  it('reports a plain timeout when relay candidates were available', async () => {
    vi.useFakeTimers();
    const peerConnection = new FakePeerConnection();
    vi.stubGlobal('MediaStream', FakeMediaStream);
    vi.stubGlobal('RTCPeerConnection', function RTCPeerConnection() {
      return peerConnection;
    });
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    const errors: Error[] = [];
    const client = new NekoClient({ onError: (error) => errors.push(error) });
    const internals = client as unknown as {
      startConnectionTimer(): void;
      handleSignalProvide(message: {
        event: 'signal/provide';
        id: string;
        lite: boolean;
        sdp: string;
        ice?: RTCIceServer[];
      }): Promise<void>;
    };

    internals.startConnectionTimer();
    await internals.handleSignalProvide({
      event: 'signal/provide',
      id: 'peer-1',
      lite: false,
      sdp: 'v=0',
      ice: [{ urls: ['turn:turn.example.test:3478'] }],
    });
    peerConnection.emitCandidate('candidate:1 1 udp 1 10.0.0.1 5000 typ relay');
    vi.advanceTimersByTime(20_000);

    expect(errors.map((error) => error.message)).toEqual([
      'workspace.browser.error.nekoConnectionTimeout',
    ]);
  });

  it('queues ICE candidates until the remote description is ready', async () => {
    const peerConnection = new FakePeerConnection();
    const remoteDescription = deferred<void>();
    const setRemoteDescription = vi
      .spyOn(peerConnection, 'setRemoteDescription')
      .mockReturnValue(remoteDescription.promise);
    const addIceCandidate = vi.spyOn(peerConnection, 'addIceCandidate');
    vi.stubGlobal('MediaStream', FakeMediaStream);
    vi.stubGlobal('RTCPeerConnection', function RTCPeerConnection() {
      return peerConnection;
    });

    const client = new NekoClient();
    const internals = client as unknown as {
      handleSignalProvide(message: {
        event: 'signal/provide';
        id: string;
        lite: boolean;
        sdp: string;
      }): Promise<void>;
      handleSignalCandidate(message: {
        event: 'signal/candidate';
        data: string;
      }): Promise<void>;
    };

    const provide = internals.handleSignalProvide({
      event: 'signal/provide',
      id: 'peer-1',
      lite: true,
      sdp: 'v=0',
    });
    await Promise.resolve();
    await internals.handleSignalCandidate({
      event: 'signal/candidate',
      data: JSON.stringify({ candidate: 'candidate:1' }),
    });

    expect(setRemoteDescription).toHaveBeenCalledTimes(1);
    expect(addIceCandidate).not.toHaveBeenCalled();

    remoteDescription.resolve(undefined);
    await provide;

    expect(addIceCandidate).toHaveBeenCalledWith({ candidate: 'candidate:1' });
  });

  it('stops aggregated media tracks and clears peer handlers on disconnect', async () => {
    const peerConnection = new FakePeerConnection();
    const track = { stop: vi.fn() } as unknown as MediaStreamTrack;
    const mediaStream = new FakeMediaStream();
    vi.stubGlobal('MediaStream', function MediaStream() {
      return mediaStream;
    });
    vi.stubGlobal('RTCPeerConnection', function RTCPeerConnection() {
      return peerConnection;
    });

    const client = new NekoClient();
    const internals = client as unknown as {
      handleSignalProvide(message: {
        event: 'signal/provide';
        id: string;
        lite: boolean;
        sdp: string;
      }): Promise<void>;
    };
    await internals.handleSignalProvide({
      event: 'signal/provide',
      id: 'peer-1',
      lite: true,
      sdp: 'v=0',
    });
    peerConnection.ontrack?.({ track } as RTCTrackEvent);

    client.disconnect();

    expect(track.stop).toHaveBeenCalledTimes(1);
    expect(peerConnection.ontrack).toBeNull();
    expect(peerConnection.onicecandidate).toBeNull();
    expect(peerConnection.onconnectionstatechange).toBeNull();
    expect(peerConnection.dataChannel.onopen).toBeNull();
    expect(peerConnection.dataChannel.onerror).toBeNull();
    expect(peerConnection.dataChannel.onclose).toBeNull();
  });

  it('fails a connection that never completes instead of remaining stuck', () => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    const errors: Error[] = [];
    const client = new NekoClient({ onError: (error) => errors.push(error) });

    client.connect('ws://browser.example/ws', 'derived-password');
    vi.advanceTimersByTime(20_000);

    expect(errors.map((error) => error.message)).toEqual([
      'workspace.browser.error.nekoConnectionTimeout',
    ]);
    client.disconnect();
  });

  it('reports one failure when multiple terminal events race', () => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);

    const errors: Error[] = [];
    const states: string[] = [];
    const client = new NekoClient({
      onError: (error) => errors.push(error),
      onConnectionStateChange: (state) => states.push(state),
    });
    const internals = client as unknown as {
      handleSocketError(): void;
    };

    client.connect('ws://browser.example/ws', 'derived-password');
    internals.handleSocketError();
    internals.handleSocketError();
    vi.advanceTimersByTime(20_000);

    expect(errors).toHaveLength(1);
    expect(states.filter((state) => state === 'failed')).toHaveLength(1);
    client.disconnect();
  });

  it('reports WebSocket open and cleanup state without exposing the URL', () => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);
    const states: boolean[] = [];
    const client = new NekoClient({
      onWebSocketStateChange: (open) => states.push(open),
    });

    client.connect('ws://browser.example/ws', 'derived-password');
    FakeWebSocket.latest?.emit('open');
    client.disconnect();

    expect(states).toContain(true);
    expect(states.at(-1)).toBe(false);
  });

  it('reports data-channel open, close, and disconnect cleanup', async () => {
    const peerConnection = new FakePeerConnection();
    vi.stubGlobal('MediaStream', FakeMediaStream);
    vi.stubGlobal('RTCPeerConnection', function RTCPeerConnection() {
      return peerConnection;
    });
    const states: boolean[] = [];
    const client = new NekoClient({
      onDataChannelStateChange: (open) => states.push(open),
    });
    const internals = client as unknown as {
      handleSignalProvide(message: {
        event: 'signal/provide';
        id: string;
        lite: boolean;
        sdp: string;
      }): Promise<void>;
    };

    await internals.handleSignalProvide({
      event: 'signal/provide',
      id: 'peer-1',
      lite: true,
      sdp: 'v=0',
    });
    peerConnection.dataChannel.onopen?.();
    peerConnection.dataChannel.onclose?.();
    client.disconnect();

    expect(states[0]).toBe(true);
    expect(states.at(-1)).toBe(false);
  });
});

class FakePeerConnection {
  connectionState: RTCPeerConnectionState = 'new';
  onconnectionstatechange: (() => void) | null = null;
  onicecandidate: ((event: RTCPeerConnectionIceEvent) => void) | null = null;
  onicecandidateerror: ((event: RTCPeerConnectionIceErrorEvent) => void) | null = null;
  ontrack: ((event: RTCTrackEvent) => void) | null = null;
  readonly dataChannel = new FakeDataChannel();

  emit(event: string): void {
    if (event === 'connectionstatechange') {
      this.onconnectionstatechange?.();
    }
  }

  emitCandidate(candidate: string): void {
    this.onicecandidate?.({
      candidate: { candidate } as RTCIceCandidate,
    } as RTCPeerConnectionIceEvent);
  }

  emitCandidateError(url: string, errorCode: number): void {
    this.onicecandidateerror?.({
      url,
      errorCode,
      errorText: 'unreachable',
    } as RTCPeerConnectionIceErrorEvent);
  }

  createDataChannel(): RTCDataChannel {
    return this.dataChannel as unknown as RTCDataChannel;
  }

  async setRemoteDescription(): Promise<void> {}

  async addIceCandidate(): Promise<void> {}

  async createAnswer(): Promise<RTCSessionDescriptionInit> {
    return { type: 'answer', sdp: 'v=0' };
  }

  async setLocalDescription(): Promise<void> {}

  close(): void {}
}

class FakeDataChannel {
  readonly readyState = 'connecting';
  onopen: (() => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: (() => void) | null = null;

  close(): void {}
}

class FakeMediaStream {
  private readonly tracks: MediaStreamTrack[] = [];

  addTrack(track: MediaStreamTrack): void {
    this.tracks.push(track);
  }

  getTracks(): MediaStreamTrack[] {
    return this.tracks;
  }
}

class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;

  static latest: FakeWebSocket | null = null;

  readonly readyState = FakeWebSocket.CONNECTING;
  private readonly listeners = new Map<string, Set<EventListener>>();

  constructor() {
    FakeWebSocket.latest = this;
  }

  addEventListener(type: string, listener: EventListener): void {
    const listeners = this.listeners.get(type) ?? new Set<EventListener>();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: EventListener): void {
    this.listeners.get(type)?.delete(listener);
  }

  emit(type: string): void {
    for (const listener of this.listeners.get(type) ?? []) listener(new Event(type));
  }

  close(): void {}

  send(): void {}
}

function attachOpenDataChannel(client: NekoClient): { client: NekoClient; buffers: ArrayBuffer[] } {
  const buffers: ArrayBuffer[] = [];
  Object.defineProperty(client, 'dataChannel', {
    value: {
      readyState: 'open',
      send: (buffer: ArrayBuffer) => buffers.push(buffer),
    },
  });
  return { client, buffers };
}

function toBytes(buffer: ArrayBuffer): number[] {
  return Array.from(new Uint8Array(buffer));
}

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T | PromiseLike<T>) => void;
} {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}
