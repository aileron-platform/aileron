
import { useEffect, useRef, useState, useCallback } from 'react';
import { createLogger } from '@/shared/services/logger';
import { toWebSocketUrl } from '../../services/workspacePublicUrl';

const logger = createLogger('useWebSocketClient');

// Define allowed message types.
const ALLOWED_MESSAGE_TYPES = new Set([
    'pong', 'subscribed', 'unsubscribed', 'message', 'task',
    'task_created', 'task_patched', 'task_stopped', 'task_completed',
    // Error messages
    'error',
    // CRUD events
    'sessions created', 'session:init', 'sessions patched', 'sessions updated', 'sessions removed',
    'tasks created', 'tasks patched', 'tasks updated', 'tasks removed',
    'messages created', 'messages patched', 'messages updated', 'messages removed', 'messages queued',
    'message:dequeued', 'queue:processing_failed',
    // Streaming events
    'streaming:start', 'streaming:chunk', 'streaming:end', 'streaming:error',
    // Thinking events
    'thinking:start', 'thinking:chunk', 'thinking:end',
    // Task lifecycle events
    'task:started', 'task:completed', 'task:failed', 'task:stop_ack', 'task:stopping', 'task:stopped',
    // Tool events
    'tool:start', 'tool:complete', 'tool:error',
    // Tool Decision events
    'tool-decision:request', 'tool-decision:approved', 'tool-decision:denied', 'tool-decision:timeout',
]);

export interface UseWebSocketClientOptions {
    runtimeBaseUrl: string | null;
    workspaceId: string | null;
    sessionId?: string | null;
    lastSeq?: number | null;
    autoConnect?: boolean;
    token?: string | null;
}

export interface UseWebSocketClientResult {
    socket: WebSocket | null;
    connected: boolean;
    connecting: boolean;
    error: string | null;
    reconnect: () => void;
}

export function useWebSocketClient({
    runtimeBaseUrl,
    workspaceId,
    sessionId,
    lastSeq,
    autoConnect = true,
    token,
}: UseWebSocketClientOptions): UseWebSocketClientResult {
    const [socket, setSocket] = useState<WebSocket | null>(null);
    const [connected, setConnected] = useState(false);
    const [connecting, setConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const reconnectAttempts = useRef(0);
    const maxReconnectAttempts = 10;
    const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
    const heartbeatTimer = useRef<ReturnType<typeof setInterval>>();
    const socketRef = useRef<WebSocket | null>(null);
    const manuallyClosedSocketsRef = useRef(new WeakSet<WebSocket>());
    const prevSessionIdRef = useRef<string | null | undefined>(undefined);
    const lastSeqRef = useRef<number | null>(lastSeq ?? null);

    useEffect(() => {
        if (typeof lastSeq === 'number' && Number.isFinite(lastSeq) && lastSeq >= 0) {
            lastSeqRef.current = Math.floor(lastSeq);
            return;
        }
        lastSeqRef.current = null;
    }, [lastSeq]);

    const cleanup = useCallback(() => {
        if (socketRef.current) {
            manuallyClosedSocketsRef.current.add(socketRef.current);
            socketRef.current.close();
            socketRef.current = null;
        }
        if (reconnectTimer.current) {
            clearTimeout(reconnectTimer.current);
            reconnectTimer.current = undefined;
        }
        if (heartbeatTimer.current) {
            clearInterval(heartbeatTimer.current);
            heartbeatTimer.current = undefined;
        }
        setSocket(null);
        setConnected(false);
        setConnecting(false);
    }, []);

    const getWsUrl = useCallback((sid: string) => {
        if (!runtimeBaseUrl) {
            return '';
        }

        const urlObj = new URL(toWebSocketUrl(runtimeBaseUrl, `/api/v1/ws/agent-sessions/${sid}`));

        if (token) {
            urlObj.searchParams.set('token', token);
            urlObj.searchParams.set('user_id', 'current-user');
        }

        const replaySeq = lastSeqRef.current;
        if (typeof replaySeq === 'number' && Number.isFinite(replaySeq) && replaySeq >= 0) {
            urlObj.searchParams.set('last_seq', String(Math.floor(replaySeq)));
        }

        return urlObj.toString();
    }, [runtimeBaseUrl, token]);

    const startHeartbeat = useCallback((ws: WebSocket) => {
        heartbeatTimer.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }, []);

    const handleMessage = useCallback((event: MessageEvent) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'pong') return;

            // Validate message structure.
            if (!data.type || typeof data.type !== 'string') {
                logger.error('Invalid WebSocket message structure', {
                    hasType: !!data.type,
                    type: typeof data.type,
                    dataKeys: data ? Object.keys(data) : []
                });
                return;
            }

            // Validate message type.
            if (!ALLOWED_MESSAGE_TYPES.has(data.type)) {
                logger.warn('Unknown WebSocket message type', {
                    type: data.type,
                    allowedTypes: Array.from(ALLOWED_MESSAGE_TYPES)
                });
                return;
            }

            // Handle error messages.
            if (data.type === 'error') {
                logger.error('WebSocket error from server', {
                    message: data.message,
                    code: data.code,
                });
                setError(data.message || 'Unknown WebSocket error');
                return;
            }

            // Message handling is owned by the caller.
            // This hook only performs basic validation.

        } catch (e) {
            logger.error('Failed to parse WebSocket message', {
                error: e,
                errorName: e instanceof Error ? e.name : 'unknown',
                rawData: typeof event.data === 'string' ? event.data.substring(0, 200) : '[non-string data]'
            });

            // Try to extract an error message from the raw payload.
            if (typeof event.data === 'string') {
                const text = event.data.trim();
                if (text.startsWith('error:') || text.startsWith('Error:') || text.startsWith('ERROR:')) {
                    logger.error('WebSocket error message from server', { message: text });
                    setError(text);
                }
            }
        }
    }, []);

    const handleClose = useCallback((event: CloseEvent, reconnectFn: () => void) => {
        logger.debug('Disconnected', { code: event.code, reason: event.reason });
        setConnected(false);
        setConnecting(false);
        if (heartbeatTimer.current) {
            clearInterval(heartbeatTimer.current);
        }

        if (event.code === 1000) return;

        if (reconnectAttempts.current >= maxReconnectAttempts) {
            logger.error('WebSocket reconnection failed after max attempts', {
                attempts: reconnectAttempts.current,
                maxAttempts: maxReconnectAttempts,
                sessionId
            });
            setError('連線失敗，請檢查網路後重新整理頁面');
            return;
        }

        const baseDelay = reconnectAttempts.current === 0 ? 500 : 2000;
        const delay = Math.min(baseDelay * Math.pow(1.5, Math.max(0, reconnectAttempts.current - 1)), 30000);
        logger.debug(`Reconnecting in ${delay}ms...`, {
            attempt: reconnectAttempts.current + 1,
            maxAttempts: maxReconnectAttempts
        });
        reconnectAttempts.current++;
        setConnecting(true);
        reconnectTimer.current = setTimeout(reconnectFn, delay);
    }, [maxReconnectAttempts]);

    const connect = useCallback(() => {
        if (!runtimeBaseUrl || !sessionId) return;

        if (socketRef.current?.readyState === WebSocket.OPEN) {
            logger.debug('Already connected, skipping');
            return;
        }

        cleanup();
        setConnecting(true);
        setError(null);

        try {
            const wsUrl = getWsUrl(sessionId);
            logger.debug('Connecting to', { wsUrl });
            const ws = new WebSocket(wsUrl);
            socketRef.current = ws;

            ws.addEventListener('open', () => {
                if (ws !== socketRef.current) {
                    return;
                }
                logger.debug('Connected');
                setConnected(true);
                setConnecting(false);
                setError(null);
                reconnectAttempts.current = 0;
                startHeartbeat(ws);
            });

            ws.addEventListener('message', handleMessage);
            ws.addEventListener('close', (event) => {
                const isManualClose = manuallyClosedSocketsRef.current.has(ws);
                const isStaleSocket = ws !== socketRef.current;

                if (isManualClose || isStaleSocket) {
                    manuallyClosedSocketsRef.current.delete(ws);
                    logger.debug('Ignoring close from stale/manual WebSocket', {
                        code: event.code,
                        reason: event.reason,
                        isManualClose,
                        isStaleSocket,
                    });
                    return;
                }

                handleClose(event, connect);
            });

            ws.addEventListener('error', (e) => {
                if (ws !== socketRef.current) {
                    return;
                }
                logger.error('WebSocket error', { error: e });
                setError('WebSocket connection error');
            });

            setSocket(ws);

        } catch (e) {
            logger.error('Connection failed', { error: e });
            setError(e instanceof Error ? e.message : 'Unknown error');
            setConnecting(false);
        }
    }, [runtimeBaseUrl, sessionId, cleanup, getWsUrl, startHeartbeat, handleMessage, handleClose]);

    useEffect(() => {
        const isSessionSwitch = prevSessionIdRef.current !== undefined && prevSessionIdRef.current !== sessionId;
        const isSessionCleared = prevSessionIdRef.current !== undefined && prevSessionIdRef.current !== null && sessionId === null;

        prevSessionIdRef.current = sessionId;

        if (isSessionCleared) {
            logger.debug('Session cleared, closing existing WebSocket connection');
            cleanup();
            return;
        }

        if (autoConnect && runtimeBaseUrl && sessionId) {
            if (isSessionSwitch) {
                reconnectAttempts.current = 0;
                logger.debug('Session switched, resetting reconnect attempts', { sessionId });
            }
            connect();
        } else if (!sessionId) {
            cleanup();
        }
        return () => {
            cleanup();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
        // connect and cleanup are intentionally omitted to prevent infinite reconnection loops
        // The effect should only run when autoConnect, runtimeBaseUrl, or sessionId changes
    }, [autoConnect, runtimeBaseUrl, sessionId]);

    return {
        socket,
        connected,
        connecting,
        error,
        reconnect: connect
    };
}
