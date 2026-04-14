/**
 * useNekoStream — React hook for managing neko WebRTC stream lifecycle.
 *
 * Wraps NekoClient to provide reactive connection state,
 * video/audio MediaStream binding, and auto-reconnect.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { NekoClient } from '../lib/nekoClient';
import { attachInputHandlers } from '../lib/inputHandler';
import type { NekoConnectionState } from '../lib/nekoProtocol';

export interface UseNekoStreamOptions {
  /** WebSocket URL: ws://host:port/ws */
  url: string | null;
  /** neko password */
  password?: string;
  /** display name */
  displayname?: string;
  /** auto-reconnect on failure (default: true) */
  autoReconnect?: boolean;
  /** reconnect delay in ms (default: 3000) */
  reconnectDelay?: number;
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
  /** Manually reconnect */
  reconnect: () => void;
}

export function useNekoStream({
  url,
  password = 'neko',
  displayname = 'user',
  autoReconnect = true,
  reconnectDelay = 3000,
}: UseNekoStreamOptions): UseNekoStreamReturn {
  const [connectionState, setConnectionState] = useState<NekoConnectionState>('disconnected');
  const [error, setError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const clientRef = useRef<NekoClient | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const detachInputRef = useRef<(() => void) | null>(null);
  const intentionalDisconnect = useRef(false);

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = undefined;
    }
    if (detachInputRef.current) {
      detachInputRef.current();
      detachInputRef.current = null;
    }
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!url) return;

    cleanup();
    intentionalDisconnect.current = false;
    setError(null);

    const client = new NekoClient({
      onConnectionStateChange: (state) => {
        setConnectionState(state);

        if (state === 'connected') {
          setError(null);
          // Attach input handlers once connected
          if (videoRef.current && clientRef.current) {
            if (detachInputRef.current) detachInputRef.current();
            detachInputRef.current = attachInputHandlers(videoRef.current, clientRef.current);
          }
        }

        if (state === 'failed' && autoReconnect && !intentionalDisconnect.current) {
          reconnectTimer.current = setTimeout(() => {
            connect();
          }, reconnectDelay);
        }
      },
      onTrack: (event) => {
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
        setError(err.message);
      },
    });

    clientRef.current = client;
    client.connect(url, password, displayname);
  }, [url, password, displayname, autoReconnect, reconnectDelay, cleanup]);

  const disconnect = useCallback(() => {
    intentionalDisconnect.current = true;
    cleanup();
    setConnectionState('disconnected');
    setError(null);
  }, [cleanup]);

  const reconnect = useCallback(() => {
    disconnect();
    // Small delay to ensure cleanup is complete
    setTimeout(() => connect(), 100);
  }, [disconnect, connect]);

  // Connect when URL changes
  useEffect(() => {
    if (url) {
      connect();
    } else {
      cleanup();
      setConnectionState('disconnected');
    }

    return () => {
      intentionalDisconnect.current = true;
      cleanup();
    };
  }, [url]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    connectionState,
    isConnected: connectionState === 'connected',
    error,
    videoRef,
    audioRef,
    disconnect,
    reconnect,
  };
}
