
import { useState, useEffect, useCallback } from 'react';
import { getEventDispatcher } from '../../components/ChatPanel/agentSessionEvents';
import type { AgentMessage } from '../../components/ChatPanel/agentSessionTypes';

export function useRealtimeMessages(sessionId: string | null) {
    // Map of messageId -> AgentMessage
    const [messagesMap, setMessagesMap] = useState<Map<string, AgentMessage>>(new Map());

    // Handle created message
    const handleMessageCreated = useCallback((message: AgentMessage) => {
        if (sessionId && message.session_id !== sessionId) return;

        setMessagesMap(prev => {
            const next = new Map(prev);
            next.set(message.message_id, message);
            return next;
        });
    }, [sessionId]);

    // Handle patched message
    const handleMessagePatched = useCallback((message: Partial<AgentMessage> & { message_id: string }) => {
        setMessagesMap(prev => {
            const next = new Map(prev);
            const existing = next.get(message.message_id);
            if (existing) {
                // Correctly handling potentially mismatching session_id if needed, but usually patched doesn't change session_id
                if (sessionId && existing.session_id !== sessionId) return prev;

                next.set(message.message_id, { ...existing, ...message });
            }
            return next;
        });
    }, [sessionId]);

    // Handle removed message
    const handleMessageRemoved = useCallback((messageId: string) => {
        setMessagesMap(prev => {
            const next = new Map(prev);
            next.delete(messageId);
            return next;
        });
    }, []);

    // Update handlers when sessionId or callbacks change
    useEffect(() => {
        if (!sessionId) return;

        const dispatcher = getEventDispatcher();
        const unsubscribe = dispatcher.subscribe({
            onMessageCreated: handleMessageCreated,
            onMessagePatched: handleMessagePatched,
            onMessageRemoved: handleMessageRemoved,
        });

        return () => {
            unsubscribe();
        };
    }, [sessionId, handleMessageCreated, handleMessagePatched, handleMessageRemoved]);

    // 完全替換訊息（用於切換 session）
    const setMessages = useCallback((newMessages: AgentMessage[]) => {
        const map = new Map<string, AgentMessage>();
        newMessages.forEach(msg => map.set(msg.message_id, msg));
        setMessagesMap(map);
    }, []);

    // 合併訊息（用於頁面重整，保留 WebSocket 已接收的新訊息）
    const mergeMessages = useCallback((newMessages: AgentMessage[]) => {
        setMessagesMap(prev => {
            const next = new Map(prev);
            newMessages.forEach(msg => {
                const existing = next.get(msg.message_id);
                if (!existing) {
                    // 新訊息，直接加入
                    next.set(msg.message_id, msg);
                } else {
                    // 已存在，保留較新的版本
                    const existingTime = new Date(existing.updated_at || existing.created_at).getTime();
                    const newTime = new Date(msg.updated_at || msg.created_at).getTime();
                    if (newTime > existingTime) {
                        next.set(msg.message_id, msg);
                    }
                }
            });
            return next;
        });
    }, []);

    return {
        messagesMap,
        setMessages,
        mergeMessages,
    };
}
