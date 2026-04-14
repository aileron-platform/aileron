export type NekoConnectionState = 'connected' | 'connecting' | 'disconnected' | 'failed';

export const NEKO_EVENT = {
  systemInit: 'system/init',
  systemError: 'system/error',
  systemDisconnect: 'system/disconnect',
  clientHeartbeat: 'client/heartbeat',
  screenResolution: 'screen/resolution',
  signalProvide: 'signal/provide',
  signalOffer: 'signal/offer',
  signalAnswer: 'signal/answer',
  signalCandidate: 'signal/candidate',
} as const;

export const NEKO_OPCODE = {
  move: 0x01,
  scroll: 0x02,
  keyDown: 0x03,
  keyUp: 0x04,
} as const;

export interface NekoScreenResolutionMessage {
  event: typeof NEKO_EVENT.screenResolution;
  width: number;
  height: number;
  rate?: number;
}

export interface NekoSystemInitMessage {
  event: typeof NEKO_EVENT.systemInit;
  heartbeat_interval?: number;
}

export interface NekoSystemErrorMessage {
  event: typeof NEKO_EVENT.systemError | typeof NEKO_EVENT.systemDisconnect;
  title?: string;
  message?: string;
}

export interface NekoSignalProvideMessage {
  event: typeof NEKO_EVENT.signalProvide;
  id: string;
  lite?: boolean;
  ice?: RTCIceServer[];
  sdp: string;
}

export interface NekoSignalOfferMessage {
  event: typeof NEKO_EVENT.signalOffer;
  sdp: string;
}

export interface NekoSignalAnswerMessage {
  event: typeof NEKO_EVENT.signalAnswer;
  sdp: string;
  displayname: string;
}

export interface NekoSignalCandidateMessage {
  event: typeof NEKO_EVENT.signalCandidate;
  data: string;
}

export interface NekoHeartbeatMessage {
  event: typeof NEKO_EVENT.clientHeartbeat;
}

export type NekoInboundMessage =
  | NekoSystemInitMessage
  | NekoSystemErrorMessage
  | NekoScreenResolutionMessage
  | NekoSignalProvideMessage
  | NekoSignalOfferMessage
  | NekoSignalAnswerMessage
  | NekoSignalCandidateMessage;

export type NekoOutboundMessage =
  | NekoHeartbeatMessage
  | NekoSignalOfferMessage
  | NekoSignalAnswerMessage
  | NekoSignalCandidateMessage;

export interface NekoClientCallbacks {
  onConnectionStateChange?: (state: NekoConnectionState) => void;
  onTrack?: (event: RTCTrackEvent) => void;
  onError?: (error: Error) => void;
}
