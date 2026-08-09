/**
 * useNekoStream — React hook for managing neko WebRTC stream lifecycle.
 *
 * Wraps NekoClient to provide reactive connection state,
 * video/audio MediaStream binding for one access generation.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { NekoClient } from '../lib/nekoClient';
import { attachInputHandlers } from '../lib/inputHandler';
import type { NekoConnectionState } from '../lib/nekoProtocol';

const EMPTY_ICE_SERVERS: RTCIceServer[] = [];

export interface UseNekoStreamOptions {
  /** WebSocket URL: ws://host:port/ws */
  url: string | null;
  /** neko password */
  password?: string | null;
  /** Fresh frontend TURN credentials for this access generation. */
  iceServers?: RTCIceServer[];
  /** display name */
  displayname?: string;
  /** Monotonic access generation used to replace the complete session. */
  generation: number;
}

export interface UseNekoStreamReturn {
  /** Current connection state */
  connectionState: NekoConnectionState;
  /** Whether the stream is connected */
  isConnected: boolean;
  /** Last error message */
  error: string | null;
  /** Ref to attach to the <video> element */
  videoRef: React.RefObject<HTMLVideoElement | null>;
  /** Ref to attach to the <audio> element */
  audioRef: React.RefObject<HTMLAudioElement | null>;
  /** Manually disconnect */
  disconnect: () => void;
}

export function useNekoStream({
  url,
  password,
  iceServers = EMPTY_ICE_SERVERS,
  displayname = 'user',
  generation,
}: UseNekoStreamOptions): UseNekoStreamReturn {
  const [connectionState, setConnectionState] = useState<NekoConnectionState>('disconnected');
  const [error, setError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const clientRef = useRef<NekoClient | null>(null);
  const connectTimer = useRef<ReturnType<typeof setTimeout>>();
  const detachInputRef = useRef<(() => void) | null>(null);

  const cleanup = useCallback(() => {
    if (connectTimer.current) {
      clearTimeout(connectTimer.current);
      connectTimer.current = undefined;
    }
    if (detachInputRef.current) {
      detachInputRef.current();
      detachInputRef.current = null;
    }
    if (clientRef.current) {
      const client = clientRef.current;
      clientRef.current = null;
      client.disconnect();
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (audioRef.current) {
      audioRef.current.srcObject = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!url || !password) return;

    cleanup();
    setError(null);
    setConnectionState('connecting');

    let client: NekoClient;
    client = new NekoClient({
      onConnectionStateChange: (state) => {
        if (clientRef.current !== client) {
          return;
        }
        setConnectionState(state);

        if (state === 'connected') {
          setError(null);
          // Attach input handlers once connected
          if (videoRef.current && clientRef.current) {
            if (detachInputRef.current) detachInputRef.current();
            detachInputRef.current = attachInputHandlers(videoRef.current, clientRef.current);
          }
        }

      },
      onTrack: (event) => {
        if (clientRef.current !== client) {
          return;
        }
        const [stream] = event.streams;
        if (!stream) return;

        const hasVideo = stream.getVideoTracks().length > 0;
        const hasAudio = stream.getAudioTracks().length > 0;

        if (hasVideo && videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        if (hasAudio && audioRef.current) {
          audioRef.current.srcObject = stream;
        }
      },
      onError: (err) => {
        if (clientRef.current !== client) {
          return;
        }
        setError(err.message);
      },
    });

    clientRef.current = client;
    client.connect(url, password, displayname, iceServers);
  }, [url, password, displayname, generation, iceServers, cleanup]);

  const disconnect = useCallback(() => {
    cleanup();
    setConnectionState('disconnected');
    setError(null);
  }, [cleanup]);

  // Connect when connection options change.
  useEffect(() => {
    if (url) {
      // Defer the socket creation so React Strict Mode can dispose its probe effect
      // without opening a WebSocket that is immediately closed.
      connectTimer.current = setTimeout(() => {
        connectTimer.current = undefined;
        connect();
      }, 0);
    } else {
      cleanup();
      setConnectionState('disconnected');
      setError(null);
    }

    return () => {
      cleanup();
    };
  }, [url, generation, connect, cleanup]);

  return {
    connectionState,
    isConnected: connectionState === 'connected',
    error,
    videoRef,
    audioRef,
    disconnect,
  };
}
