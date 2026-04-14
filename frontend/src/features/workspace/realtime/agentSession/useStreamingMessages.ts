
import { useState, useEffect, useCallback } from 'react';
import { getEventDispatcher } from '../../components/ChatPanel/agentSessionEvents';
import { StreamingMessage, createStreamingMessage } from './streamingBuffer';
import type { AgentMessage } from '../../components/ChatPanel/agentSessionTypes';

export function useStreamingMessages(sessionId: string | null) {
    const [streamingMessages, setStreamingMessages] = useState<Map<string, StreamingMessage>>(new Map());

    // 切換 session 時清空 buffer，避免舊 session 的 streaming 狀態污染新 session。
    useEffect(() => {
        setStreamingMessages(new Map());
    }, [sessionId]);

    const handleStreamingStart = useCallback((sid: string, taskId: string, messageId?: string) => {
        if (sessionId && sid !== sessionId) return;
        if (!messageId) return;

        setStreamingMessages(prev => {
            const next = new Map(prev);
            if (!next.has(messageId)) {
                next.set(messageId, createStreamingMessage(sid, taskId, messageId));
            } else {
                // Reset if exists? or just ignore?
                // Maybe it was thinking before?
                // thinking starts BEFORE streaming usually?
                // According to flow:
                // 9. thinking:start
                // 14. streaming:start
                // So if exists, update it.
                const existing = next.get(messageId)!;
                next.set(messageId, {
                    ...existing,
                    isStreaming: true,
                    startedAt: Date.now(),
                });
            }
            return next;
        });
    }, [sessionId]);

    const handleStreamingChunk = useCallback((sid: string, taskId: string, content: string, isPartial: boolean, messageId?: string) => {
        if (sessionId && sid !== sessionId) return;
        if (!messageId) return;

        setStreamingMessages(prev => {
            const next = new Map(prev);
            const msg = next.get(messageId);
            if (msg) {
                next.set(messageId, {
                    ...msg,
                    content: msg.content + content,
                    lastUpdateAt: Date.now(),
                });
            } else {
                // Received chunk without start? Create it.
                const newMsg = createStreamingMessage(sid, taskId, messageId);
                newMsg.content = content;
                next.set(messageId, newMsg);
            }
            return next;
        });
    }, [sessionId]);

    const handleStreamingEnd = useCallback((sid: string, taskId: string, data?: Record<string, unknown>, messageId?: string) => {
        if (sessionId && sid !== sessionId) return;

        setStreamingMessages(prev => {
            const next = new Map(prev);

            if (messageId) {
                const msg = next.get(messageId);
                if (msg) {
                    next.set(messageId, {
                        ...msg,
                        isStreaming: false,
                        lastUpdateAt: Date.now(),
                    });
                }
                return next;
            }

            // 某些後端事件可能不帶 message_id，退回以 task_id 關閉該任務的 streaming 狀態。
            next.forEach((msg, id) => {
                if (
                    msg.session_id === sid &&
                    msg.task_id === taskId &&
                    msg.isStreaming
                ) {
                    next.set(id, {
                        ...msg,
                        isStreaming: false,
                        lastUpdateAt: Date.now(),
                    });
                }
            });

            return next;
        });
    }, [sessionId]);

    const handleThinkingStart = useCallback((sid: string, taskId: string, messageId?: string) => {
        if (sessionId && sid !== sessionId) return;
        if (!messageId) return;

        setStreamingMessages(prev => {
            const next = new Map(prev);
            if (!next.has(messageId)) {
                const newMsg = createStreamingMessage(sid, taskId, messageId);
                // thinking 訊息不應該被視為 streaming，否則會讓 UI 長時間卡在「產生回覆中」
                newMsg.isStreaming = false;
                newMsg.isThinking = true;
                next.set(messageId, newMsg);
            } else {
                const existing = next.get(messageId)!;
                next.set(messageId, { ...existing, isThinking: true });
            }
            return next;
        });
    }, [sessionId]);

    const handleThinkingChunk = useCallback((sid: string, taskId: string, content: string, isPartial: boolean, messageId?: string) => {
        if (sessionId && sid !== sessionId) return;
        if (!messageId) return;

        setStreamingMessages(prev => {
            const next = new Map(prev);
            const msg = next.get(messageId);
            if (msg) {
                next.set(messageId, {
                    ...msg,
                    thinkingContent: (msg.thinkingContent || '') + content,
                    lastUpdateAt: Date.now(),
                });
            } else {
                // Received thinking chunk without start? Create it.
                const newMsg = createStreamingMessage(sid, taskId, messageId);
                newMsg.isStreaming = false;
                newMsg.isThinking = true;
                newMsg.thinkingContent = content;
                next.set(messageId, newMsg);
            }
            return next;
        });
    }, [sessionId]);

    const handleThinkingEnd = useCallback((sid: string, taskId: string, messageId?: string) => {
        if (sessionId && sid !== sessionId) return;

        setStreamingMessages(prev => {
            const next = new Map(prev);

            if (messageId) {
                const msg = next.get(messageId);
                if (msg) {
                    next.set(messageId, { ...msg, isThinking: false });
                }
                return next;
            }

            // 某些後端事件可能不帶 message_id，退回以 task_id 關閉該任務的 thinking 狀態。
            next.forEach((msg, id) => {
                if (
                    msg.session_id === sid &&
                    msg.task_id === taskId &&
                    msg.isThinking
                ) {
                    next.set(id, { ...msg, isThinking: false });
                }
            });

            return next;
        });
    }, [sessionId]);

    // Handle message created event to remove from buffer
    const handleMessageCreated = useCallback((message: AgentMessage) => {
        if (sessionId && message.session_id !== sessionId) return;

        setStreamingMessages(prev => {
            if (prev.has(message.message_id)) {
                const next = new Map(prev);
                next.delete(message.message_id);
                return next;
            }
            return prev;
        });
    }, [sessionId]);

    useEffect(() => {
        if (!sessionId) return;

        const dispatcher = getEventDispatcher();
        const unsubscribe = dispatcher.subscribe({
            onStreamingStart: handleStreamingStart,
            onStreamingChunk: handleStreamingChunk,
            onStreamingEnd: handleStreamingEnd,
            onThinkingStart: handleThinkingStart,
            onThinkingChunk: handleThinkingChunk,
            onThinkingEnd: handleThinkingEnd,
            onMessageCreated: handleMessageCreated,
        });

        return () => {
            unsubscribe();
        };
    }, [
        sessionId,
        handleStreamingStart,
        handleStreamingChunk,
        handleStreamingEnd,
        handleThinkingStart,
        handleThinkingChunk,
        handleThinkingEnd,
        handleMessageCreated
    ]);

    return streamingMessages;
}
