
import { useState, useEffect, useCallback } from 'react';
import { getEventDispatcher } from '../../components/ChatPanel/agentSessionEvents';
import type { AgentSession } from '../../components/ChatPanel/agentSessionTypes';

export function useRealtimeSessions(workspaceId: string | null) {
    const [sessionsMap, setSessionsMap] = useState<Map<string, AgentSession>>(new Map());

    const handleSessionCreated = useCallback((session: AgentSession) => {
        if (workspaceId && session.workspace_id !== workspaceId) return;
        // Skip automation-created sessions in Chat Panel
        if (session.source === 'automation') return;

        setSessionsMap(prev => {
            const next = new Map(prev);
            next.set(session.session_id, session);
            return next;
        });
    }, [workspaceId]);

    const handleSessionPatched = useCallback((session: Partial<AgentSession> & { session_id: string }) => {
        setSessionsMap(prev => {
            const next = new Map(prev);
            const existing = next.get(session.session_id);
            if (existing) {
                // 更新已存在的 session
                if (workspaceId && existing.workspace_id !== workspaceId) return prev;
                next.set(session.session_id, { ...existing, ...session });
            } else {
                // 如果 session 不存在但 workspace_id 匹配，也添加它
                // 這處理了 session 創建後但 created 事件未被接收的情況
                if (!workspaceId || session.workspace_id === workspaceId) {
                    // 只有當 patched 事件包含足夠的資訊時才添加
                    if (session.workspace_id) {
                        next.set(session.session_id, session as AgentSession);
                    }
                }
            }
            return next;
        });
    }, [workspaceId]);

    const handleSessionRemoved = useCallback((sessionId: string) => {
        setSessionsMap(prev => {
            const next = new Map(prev);
            next.delete(sessionId);
            return next;
        });
    }, []);

    useEffect(() => {
        if (!workspaceId) return;

        const dispatcher = getEventDispatcher();
        const unsubscribe = dispatcher.subscribe({
            onSessionCreated: handleSessionCreated,
            onSessionPatched: handleSessionPatched,
            onSessionRemoved: handleSessionRemoved,
        });

        return () => {
            unsubscribe();
        };
    }, [workspaceId, handleSessionCreated, handleSessionPatched, handleSessionRemoved]);

    const setSessions = useCallback((newSessions: AgentSession[]) => {
        const map = new Map<string, AgentSession>();
        newSessions.forEach(s => map.set(s.session_id, s));
        setSessionsMap(map);
    }, []);

    const upsertSession = useCallback((session: AgentSession) => {
        if (!session?.session_id) {
            return;
        }

        setSessionsMap(prev => {
            const next = new Map(prev);
            const existing = next.get(session.session_id);
            next.set(session.session_id, existing ? { ...existing, ...session } : session);
            return next;
        });
    }, []);

    return {
        sessionsMap,
        setSessions,
        upsertSession,
    };
}
