import {
  NEKO_EVENT,
  type NekoClientCallbacks,
  type NekoConnectionState,
  type NekoInboundMessage,
  type NekoOutboundMessage,
  type NekoSignalCandidateMessage,
  type NekoSignalProvideMessage,
} from './nekoProtocol';

const DEFAULT_RTC_CONFIGURATION: RTCConfiguration = {
  bundlePolicy: 'max-bundle',
  rtcpMuxPolicy: 'require',
};

const CONNECTION_TIMEOUT_MS = 20_000;

export class NekoClient {
  private readonly callbacks: NekoClientCallbacks;
  private websocket: WebSocket | null = null;
  private peerConnection: RTCPeerConnection | null = null;
  private dataChannel: RTCDataChannel | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private connectionTimer: ReturnType<typeof setTimeout> | null = null;
  private mediaStream: MediaStream | null = null;
  private pendingCandidates: RTCIceCandidateInit[] = [];
  private remoteDescriptionReady = false;
  private connectionState: NekoConnectionState = 'disconnected';
  private iceServersConfigured = false;
  private relayCandidateCount = 0;
  private iceServerErrors: string[] = [];
  private displayname = 'user';
  private screenWidth = 1440;
  private screenHeight = 900;
  private frontendIceServers: RTCIceServer[] = [];

  constructor(callbacks: NekoClientCallbacks = {}) {
    this.callbacks = callbacks;
  }

  connect(
    url: string,
    password?: string,
    displayname: string = 'user',
    iceServers: RTCIceServer[] = [],
  ): void {
    this.disconnect();

    if (!password) {
      this.fail(new Error('workspace.browser.error.credentialUnavailable'));
      return;
    }
    this.displayname = displayname;
    this.frontendIceServers = iceServers;
    this.setConnectionState('connecting');
    this.startConnectionTimer();

    try {
      const wsUrl = new URL(url);
      wsUrl.searchParams.set('password', password);
      wsUrl.searchParams.set('username', displayname);
      this.websocket = new WebSocket(wsUrl.toString());
      this.websocket.addEventListener('message', this.handleMessage);
      this.websocket.addEventListener('error', this.handleSocketError);
      this.websocket.addEventListener('close', this.handleClose);
    } catch (error) {
      console.error('[neko] connect failed', error);
      this.fail(new Error('workspace.browser.error.nekoConnectionFailed'));
    }
  }

  disconnect(): void {
    this.stopConnectionTimer();
    this.closeTransport();
    this.setConnectionState('disconnected');
  }

  getScreenResolution(): { width: number; height: number } {
    return { width: this.screenWidth, height: this.screenHeight };
  }

  sendMouseMove(x: number, y: number): void {
    this.sendDataMessage('mousemove', { x, y });
  }

  sendMouseButton(button: number, pressed: boolean): void {
    // Browser event.button is 0-based; Neko/X11 button numbers are 1-based.
    this.sendDataMessage(pressed ? 'mousedown' : 'mouseup', { key: button + 1 });
  }

  sendWheel(deltaX: number, deltaY: number): void {
    this.sendDataMessage('wheel', { x: deltaX, y: deltaY });
  }

  sendKey(keysym: number, pressed: boolean): void {
    this.sendDataMessage(pressed ? 'mousedown' : 'mouseup', { key: keysym });
  }

  sendText(text: string): void {
    for (const char of text) {
      const keysym = characterToX11Keysym(char);
      if (keysym === 0) {
        continue;
      }

      this.sendKey(keysym, true);
      this.sendKey(keysym, false);
    }
  }

  private readonly handleMessage = async (event: MessageEvent): Promise<void> => {
    if (typeof event.data !== 'string') {
      return;
    }

    let message: NekoInboundMessage;
    try {
      message = JSON.parse(event.data) as NekoInboundMessage;
    } catch {
      return;
    }

    console.debug('[neko] rx', message.event);
    try {
      switch (message.event) {
        case NEKO_EVENT.systemInit:
          this.startHeartbeat(message.heartbeat_interval ?? 0);
          break;
        case NEKO_EVENT.systemError:
        case NEKO_EVENT.systemDisconnect:
          this.fail(new Error('workspace.browser.error.nekoConnectionFailed'));
          break;
        case NEKO_EVENT.screenResolution:
          if (message.width > 0 && message.height > 0) {
            this.screenWidth = message.width;
            this.screenHeight = message.height;
            console.debug('[neko] screen resolution:', message.width, 'x', message.height);
          }
          break;
        case NEKO_EVENT.signalProvide:
          await this.handleSignalProvide(message);
          break;
        case NEKO_EVENT.signalOffer:
          await this.handleSignalOffer(message.sdp);
          break;
        case NEKO_EVENT.signalAnswer:
          await this.handleSignalAnswer(message.sdp);
          break;
        case NEKO_EVENT.signalCandidate:
          await this.handleSignalCandidate(message);
          break;
        default:
          break;
      }
    } catch (err) {
      console.error('[neko] handleMessage error for event', message.event, err);
      this.fail(new Error('workspace.browser.error.nekoConnectionFailed'));
    }
  };

  private readonly handleSocketError = (): void => {
    this.fail(new Error('workspace.browser.error.nekoWebsocketFailed'));
  };

  private readonly handleClose = (): void => {
    this.stopHeartbeat();
    if (this.connectionState !== 'failed') {
      this.fail(new Error('workspace.browser.error.nekoWebsocketFailed'));
    }
  };

  private async handleSignalProvide(message: NekoSignalProvideMessage): Promise<void> {
    const queuedCandidates = this.pendingCandidates;
    this.closePeerConnection();

    const iceServers = this.frontendIceServers.length > 0
      ? this.frontendIceServers
      : message.ice;
    const peerConnection = new RTCPeerConnection(
      message.lite && this.frontendIceServers.length === 0
        ? DEFAULT_RTC_CONFIGURATION
        : { ...DEFAULT_RTC_CONFIGURATION, iceServers },
    );
    this.peerConnection = peerConnection;
    this.iceServersConfigured = (iceServers?.length ?? 0) > 0;
    this.relayCandidateCount = 0;
    this.iceServerErrors = [];
    this.remoteDescriptionReady = false;
    this.mediaStream = new MediaStream();
    this.pendingCandidates = queuedCandidates;

    peerConnection.ontrack = (trackEvent) => {
      const stream = this.mediaStream ?? new MediaStream();
      this.mediaStream = stream;
      stream.addTrack(trackEvent.track);
      this.callbacks.onTrack?.({
        ...trackEvent,
        streams: [stream],
      } as RTCTrackEvent);
    };

    peerConnection.onicecandidate = (iceEvent) => {
      if (!iceEvent.candidate) {
        return;
      }

      // Filter mDNS candidates because Pion in Docker cannot resolve .local hostnames.
      if (iceEvent.candidate.candidate.includes('.local')) {
        return;
      }

      if (iceEvent.candidate.candidate.includes('typ relay')) {
        this.relayCandidateCount += 1;
      }

      this.sendJson({
        event: NEKO_EVENT.signalCandidate,
        data: JSON.stringify(iceEvent.candidate),
      });
    };

    // STUN/TURN servers that cannot be reached surface here rather than as a
    // connection failure, so record them to tell a misconfigured ICE server
    // apart from a plain timeout.
    peerConnection.onicecandidateerror = (errorEvent) => {
      const { url, errorCode, errorText } = errorEvent as RTCPeerConnectionIceErrorEvent;
      this.iceServerErrors.push(`${url} (${errorCode}: ${errorText})`);
      console.warn('[neko] ICE server unreachable', { url, errorCode, errorText });
    };

    peerConnection.onconnectionstatechange = () => {
      const state = peerConnection.connectionState;
      if (state === 'connecting' || state === 'new') {
        return;
      }
      if (state === 'connected') {
        this.stopConnectionTimer();
        this.setConnectionState('connected');
      } else if (state === 'failed' || state === 'closed' || state === 'disconnected') {
        console.error('[neko] unexpected WebRTC connection state', { state });
        this.fail(new Error('workspace.browser.error.nekoWebrtcFailed'));
      }
    };

    // The Neko v3 answerer creates the data channel; the server receives it via ondatachannel.
    this.dataChannel = peerConnection.createDataChannel('data');
    this.dataChannel.onopen = () => {
      console.debug('[neko] data channel open, readyState=', this.dataChannel?.readyState);
    };
    this.dataChannel.onerror = (e) => {
      console.error('[neko] data channel error', e);
      this.fail(new Error('workspace.browser.error.nekoDataChannelFailed'));
    };
    this.dataChannel.onclose = () => {
      console.debug('[neko] data channel closed');
    };

    try {
      await peerConnection.setRemoteDescription({
        type: 'offer',
        sdp: message.sdp,
      });
      if (this.peerConnection !== peerConnection) {
        return;
      }

      this.remoteDescriptionReady = true;
      while (this.pendingCandidates.length > 0) {
        const candidate = this.pendingCandidates.shift();
        if (candidate) {
          await peerConnection.addIceCandidate(candidate);
        }
        if (this.peerConnection !== peerConnection) {
          return;
        }
      }

      const answer = await peerConnection.createAnswer();
      if (this.peerConnection !== peerConnection) {
        return;
      }

      answer.sdp = answer.sdp?.replace(/(stereo=1;)?useinbandfec=1/, 'useinbandfec=1;stereo=1') ?? answer.sdp;
      await peerConnection.setLocalDescription(answer);
      if (this.peerConnection !== peerConnection) {
        return;
      }

      this.sendJson({
        event: NEKO_EVENT.signalAnswer,
        sdp: answer.sdp ?? '',
        displayname: this.displayname,
      });
    } catch (error) {
      if (this.peerConnection !== peerConnection) {
        return;
      }
      throw error;
    }
  }

  private async handleSignalCandidate(message: NekoSignalCandidateMessage): Promise<void> {
    let candidate: RTCIceCandidateInit;
    try {
      candidate = JSON.parse(message.data) as RTCIceCandidateInit;
    } catch (error) {
      console.error('[neko] failed to parse ICE candidate', error);
      this.fail(new Error('workspace.browser.error.nekoWebrtcFailed'));
      return;
    }

    const peerConnection = this.peerConnection;
    if (!peerConnection || !this.remoteDescriptionReady) {
      this.pendingCandidates.push(candidate);
      return;
    }

    try {
      await peerConnection.addIceCandidate(candidate);
    } catch (error) {
      if (this.peerConnection !== peerConnection) {
        return;
      }
      console.error('[neko] failed to add ICE candidate', error);
      this.fail(new Error('workspace.browser.error.nekoWebrtcFailed'));
    }
  }

  private async handleSignalOffer(sdp: string): Promise<void> {
    if (!this.peerConnection) {
      return;
    }

    await this.peerConnection.setRemoteDescription({ type: 'offer', sdp });
  }

  private async handleSignalAnswer(sdp: string): Promise<void> {
    if (!this.peerConnection) {
      return;
    }

    await this.peerConnection.setRemoteDescription({ type: 'answer', sdp });
  }

  private sendJson(message: NekoOutboundMessage): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    this.websocket.send(JSON.stringify(message));
  }

  private sendDataMessage(
    event: 'mousemove' | 'wheel' | 'mousedown' | 'mouseup',
    data: { x?: number; y?: number; key?: number }
  ): void {
    if (!this.dataChannel || this.dataChannel.readyState !== 'open') {
      if (event !== 'mousemove') {
        console.debug('[neko] sendDataMessage blocked', event, 'dc=', this.dataChannel?.readyState ?? 'null');
      }
      return;
    }

    let buffer: ArrayBuffer;
    const payload = (buffer: ArrayBuffer) => new DataView(buffer);

    switch (event) {
      case 'mousemove': {
        buffer = new ArrayBuffer(7);
        const view = payload(buffer);
        view.setUint8(0, 0x01);
        view.setUint16(1, 4, true);
        view.setUint16(3, clampToUint16(data.x ?? 0), true);
        view.setUint16(5, clampToUint16(data.y ?? 0), true);
        break;
      }
      case 'wheel': {
        buffer = new ArrayBuffer(7);
        const view = payload(buffer);
        view.setUint8(0, 0x02);
        view.setUint16(1, 4, true);
        view.setInt16(3, clampToInt16(data.x ?? 0), true);
        view.setInt16(5, clampToInt16(data.y ?? 0), true);
        break;
      }
      case 'mousedown':
      case 'mouseup': {
        buffer = new ArrayBuffer(11);
        const view = payload(buffer);
        view.setUint8(0, event === 'mousedown' ? 0x03 : 0x04);
        view.setUint16(1, 8, true);
        view.setBigUint64(3, BigInt(data.key ?? 0), true);
        break;
      }
    }

    this.dataChannel.send(buffer);
  }

  private setConnectionState(nextState: NekoConnectionState): void {
    this.connectionState = nextState;
    this.callbacks.onConnectionStateChange?.(nextState);
  }

  private fail(error: Error): void {
    if (this.connectionState === 'failed') {
      return;
    }
    this.stopConnectionTimer();
    this.closeTransport();
    this.callbacks.onError?.(error);
    this.setConnectionState('failed');
  }

  private startConnectionTimer(): void {
    this.stopConnectionTimer();
    this.connectionTimer = setTimeout(() => {
      // Configured ICE servers that never yielded a relay candidate point at an
      // unreachable TURN server, not at a slow peer.
      const iceServersUnusable = this.iceServersConfigured
        && this.relayCandidateCount === 0
        && this.iceServerErrors.length > 0;

      if (iceServersUnusable) {
        console.error('[neko] no relay candidate; ICE servers unreachable', {
          errors: this.iceServerErrors,
        });
        this.fail(new Error('workspace.browser.error.nekoIceServerUnreachable'));
        return;
      }

      console.error('[neko] connection timed out', {
        iceServersConfigured: this.iceServersConfigured,
        relayCandidates: this.relayCandidateCount,
        iceServerErrors: this.iceServerErrors,
      });
      this.fail(new Error('workspace.browser.error.nekoConnectionTimeout'));
    }, CONNECTION_TIMEOUT_MS);
  }

  private stopConnectionTimer(): void {
    if (this.connectionTimer) {
      clearTimeout(this.connectionTimer);
      this.connectionTimer = null;
    }
  }

  private startHeartbeat(intervalSeconds: number): void {
    this.stopHeartbeat();
    if (!intervalSeconds || intervalSeconds <= 0) {
      return;
    }

    this.heartbeatTimer = setInterval(() => {
      this.sendJson({ event: NEKO_EVENT.clientHeartbeat });
    }, intervalSeconds * 1000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private closeTransport(): void {
    this.stopHeartbeat();
    if (this.websocket) {
      this.websocket.removeEventListener('message', this.handleMessage);
      this.websocket.removeEventListener('error', this.handleSocketError);
      this.websocket.removeEventListener('close', this.handleClose);
      if (this.websocket.readyState === WebSocket.OPEN || this.websocket.readyState === WebSocket.CONNECTING) {
        this.websocket.close();
      }
      this.websocket = null;
    }
    this.closePeerConnection();
    this.pendingCandidates = [];
  }

  private closePeerConnection(): void {
    if (this.dataChannel) {
      this.dataChannel.onopen = null;
      this.dataChannel.onerror = null;
      this.dataChannel.onclose = null;
      this.dataChannel.close();
      this.dataChannel = null;
    }

    if (this.peerConnection) {
      this.peerConnection.ontrack = null;
      this.peerConnection.onicecandidate = null;
      this.peerConnection.onconnectionstatechange = null;
      this.peerConnection.close();
      this.peerConnection = null;
    }
    this.remoteDescriptionReady = false;

    if (this.mediaStream) {
      for (const track of this.mediaStream.getTracks()) {
        track.stop();
      }
      this.mediaStream = null;
    }
  }
}

function clampToUint16(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(65535, Math.round(value)));
}

function clampToInt16(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(-32768, Math.min(32767, Math.round(value)));
}

function characterToX11Keysym(char: string): number {
  const cp = char.codePointAt(0) ?? 0;
  if (cp === 0) {
    return 0;
  }
  if (cp >= 0x20 && cp <= 0x7e) {
    return cp;
  }
  return 0x01000000 | cp;
}
