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

export class NekoClient {
  private readonly callbacks: NekoClientCallbacks;
  private websocket: WebSocket | null = null;
  private peerConnection: RTCPeerConnection | null = null;
  private dataChannel: RTCDataChannel | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private mediaStream: MediaStream | null = null;
  private pendingCandidates: RTCIceCandidateInit[] = [];
  private connectionState: NekoConnectionState = 'disconnected';
  private displayname = 'user';
  private password = 'neko';
  private screenWidth = 1440;
  private screenHeight = 900;

  constructor(callbacks: NekoClientCallbacks = {}) {
    this.callbacks = callbacks;
  }

  connect(url: string, password: string = 'neko', displayname: string = 'user'): void {
    this.disconnect();

    this.password = password;
    this.displayname = displayname;
    this.setConnectionState('connecting');

    try {
      const wsUrl = new URL(url);
      wsUrl.searchParams.set('password', password);
      wsUrl.searchParams.set('username', displayname);
      this.websocket = new WebSocket(wsUrl.toString());
      this.websocket.addEventListener('open', this.handleOpen);
      this.websocket.addEventListener('message', this.handleMessage);
      this.websocket.addEventListener('error', this.handleSocketError);
      this.websocket.addEventListener('close', this.handleClose);
    } catch (error) {
      this.fail(error instanceof Error ? error : new Error(String(error)));
    }
  }

  disconnect(): void {
    this.stopHeartbeat();

    if (this.websocket) {
      this.websocket.removeEventListener('open', this.handleOpen);
      this.websocket.removeEventListener('message', this.handleMessage);
      this.websocket.removeEventListener('error', this.handleSocketError);
      this.websocket.removeEventListener('close', this.handleClose);
      if (this.websocket.readyState === WebSocket.OPEN || this.websocket.readyState === WebSocket.CONNECTING) {
        this.websocket.close();
      }
      this.websocket = null;
    }

    this.closePeerConnection();
    this.mediaStream = null;
    this.setConnectionState('disconnected');
  }

  destroy(): void {
    this.disconnect();
  }

  getMediaStream(): MediaStream | null {
    return this.mediaStream;
  }

  getScreenResolution(): { width: number; height: number } {
    return { width: this.screenWidth, height: this.screenHeight };
  }

  on(_event: string, _handler: (...args: unknown[]) => void): void {
    // 保留介面相容，現階段不需要額外事件匯流排。
  }

  off(_event: string, _handler: (...args: unknown[]) => void): void {
    // 保留介面相容，現階段不需要額外事件匯流排。
  }

  sendMouseMove(x: number, y: number): void {
    this.sendDataMessage('mousemove', { x, y });
  }

  sendMouseButton(button: number, pressed: boolean): void {
    // browser event.button 是 0-based (0=left,1=middle,2=right)
    // neko/X11 button number 是 1-based (Button1=1,Button2=2,Button3=3)
    this.sendDataMessage(pressed ? 'mousedown' : 'mouseup', { key: button + 1 });
  }

  sendWheel(deltaX: number, deltaY: number): void {
    this.sendDataMessage('wheel', { x: deltaX, y: deltaY });
  }

  sendKey(keysym: number, pressed: boolean): void {
    this.sendDataMessage(pressed ? 'mousedown' : 'mouseup', { key: keysym });
  }

  private readonly handleOpen = (): void => {
    // Neko v3 以 query 參數完成登入，open 之後等待 signal/provide。
  };

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
          this.fail(new Error(message.message || message.title || 'Neko 連線失敗'));
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
      this.fail(err instanceof Error ? err : new Error(String(err)));
    }
  };

  private readonly handleSocketError = (): void => {
    this.fail(new Error('Neko WebSocket 連線失敗'));
  };

  private readonly handleClose = (): void => {
    if (this.connectionState !== 'failed') {
      this.setConnectionState('disconnected');
    }
    this.stopHeartbeat();
  };

  private async handleSignalProvide(message: NekoSignalProvideMessage): Promise<void> {
    this.closePeerConnection();

    const peerConnection = new RTCPeerConnection(
      message.lite ? DEFAULT_RTC_CONFIGURATION : { ...DEFAULT_RTC_CONFIGURATION, iceServers: message.ice }
    );
    this.peerConnection = peerConnection;
    this.mediaStream = new MediaStream();
    // 先把在 signal/provide 之前到達的 candidate 存下來，再重置
    const priorPendingCandidates = this.pendingCandidates;
    this.pendingCandidates = [];

    peerConnection.addEventListener('track', (trackEvent) => {
      const stream = this.mediaStream ?? new MediaStream();
      this.mediaStream = stream;
      stream.addTrack(trackEvent.track);
      this.callbacks.onTrack?.({
        ...trackEvent,
        streams: [stream],
      } as RTCTrackEvent);
    });

    peerConnection.addEventListener('icecandidate', (iceEvent) => {
      if (!iceEvent.candidate) {
        return;
      }

      // 過濾掉 mDNS (.local) candidate：pion (neko) 在 Docker 容器裡無法
      // 透過 multicast 解析 .local hostname，會導致 ICE 中斷。
      if (iceEvent.candidate.candidate.includes('.local')) {
        return;
      }

      this.sendJson({
        event: NEKO_EVENT.signalCandidate,
        data: JSON.stringify(iceEvent.candidate),
      });
    });

    peerConnection.addEventListener('connectionstatechange', () => {
      const state = peerConnection.connectionState;
      if (state === 'connecting' || state === 'new') {
        return;
      }
      if (state === 'connected') {
        this.setConnectionState('connected');
      } else if (state === 'failed' || state === 'closed' || state === 'disconnected') {
        this.fail(new Error(`Neko WebRTC 狀態異常: ${state}`));
      }
    });

    // neko v3 官方 client 由 answerer（前端）createDataChannel，server 透過 ondatachannel 接收
    this.dataChannel = peerConnection.createDataChannel('data');
    this.dataChannel.onopen = () => {
      console.debug('[neko] data channel open, readyState=', this.dataChannel?.readyState);
    };
    this.dataChannel.onerror = (e) => {
      console.error('[neko] data channel error', e);
      this.fail(new Error('Neko data channel 錯誤'));
    };
    this.dataChannel.onclose = () => {
      console.debug('[neko] data channel closed');
    };

    await peerConnection.setRemoteDescription({
      type: 'offer',
      sdp: message.sdp,
    });

    // 加入 signal/provide 之前就已到達的 candidate（trickle ICE 早到情況）
    for (const candidate of priorPendingCandidates) {
      await peerConnection.addIceCandidate(candidate);
    }
    // 加入在 setRemoteDescription 期間又到的 candidate
    for (const candidate of this.pendingCandidates) {
      await peerConnection.addIceCandidate(candidate);
    }
    this.pendingCandidates = [];

    const answer = await peerConnection.createAnswer();
    answer.sdp = answer.sdp?.replace(/(stereo=1;)?useinbandfec=1/, 'useinbandfec=1;stereo=1') ?? answer.sdp;
    await peerConnection.setLocalDescription(answer);

    this.sendJson({
      event: NEKO_EVENT.signalAnswer,
      sdp: answer.sdp ?? '',
      displayname: this.displayname,
    });
  }

  private async handleSignalCandidate(message: NekoSignalCandidateMessage): Promise<void> {
    if (!this.peerConnection) {
      try {
        this.pendingCandidates.push(JSON.parse(message.data) as RTCIceCandidateInit);
      } catch (error) {
        this.fail(error instanceof Error ? error : new Error(String(error)));
      }
      return;
    }

    try {
      const candidate = JSON.parse(message.data) as RTCIceCandidateInit;
      await this.peerConnection.addIceCandidate(candidate);
    } catch (error) {
      this.fail(error instanceof Error ? error : new Error(String(error)));
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
    this.callbacks.onError?.(error);
    this.setConnectionState('failed');
  }

  private startHeartbeat(intervalMs: number): void {
    this.stopHeartbeat();
    if (!intervalMs || intervalMs <= 0) {
      return;
    }

    this.heartbeatTimer = setInterval(() => {
      this.sendJson({ event: NEKO_EVENT.clientHeartbeat });
    }, intervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private closePeerConnection(): void {
    if (this.dataChannel) {
      this.dataChannel.onerror = null;
      this.dataChannel.onclose = null;
      this.dataChannel.close();
      this.dataChannel = null;
    }

    if (!this.peerConnection) {
      return;
    }

    this.peerConnection.ontrack = null;
    this.peerConnection.onicecandidate = null;
    this.peerConnection.close();
    this.peerConnection = null;
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
