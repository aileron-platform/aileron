
export interface StreamingMessage {
    message_id: string;
    session_id: string;
    task_id?: string;
    role: 'assistant';
    content: string;
    thinkingContent?: string;
    isStreaming: boolean;
    isThinking?: boolean;
    startedAt: number;
    lastUpdateAt: number;
}


// Helper to create an initial streaming message
export function createStreamingMessage(
    sessionId: string,
    taskId: string | undefined,
    messageId: string
): StreamingMessage {
    return {
        message_id: messageId,
        session_id: sessionId,
        task_id: taskId,
        role: 'assistant',
        content: '',
        thinkingContent: '',
        isStreaming: true,
        isThinking: false,
        startedAt: Date.now(),
        lastUpdateAt: Date.now(),
    };
}
