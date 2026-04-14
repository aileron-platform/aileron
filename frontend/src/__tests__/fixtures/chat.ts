/**
 * 聊天訊息測試資料 Fixtures
 */

export interface MockChatMessage {
  id: string;
  conversationId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
  toolCalls?: MockToolCall[];
  status?: 'pending' | 'completed' | 'error';
}

export interface MockToolCall {
  id: string;
  name: string;
  parameters: Record<string, any>;
  result?: any;
  status: 'pending' | 'approved' | 'rejected' | 'completed';
}

export interface MockConversation {
  id: string;
  workspaceId: string;
  title: string;
  messages: MockChatMessage[];
  createdAt: string;
  updatedAt: string;
}

/**
 * 創建 Mock 聊天訊息
 */
export const createMockChatMessage = (
  overrides: Partial<MockChatMessage> = {}
): MockChatMessage => ({
  id: 'msg-1',
  conversationId: 'conv-1',
  role: 'user',
  content: 'Hello, this is a test message',
  timestamp: new Date().toISOString(),
  status: 'completed',
  ...overrides,
});

/**
 * 創建使用者訊息
 */
export const createUserMessage = (
  content: string,
  overrides: Partial<MockChatMessage> = {}
): MockChatMessage =>
  createMockChatMessage({
    role: 'user',
    content,
    ...overrides,
  });

/**
 * 創建助手訊息
 */
export const createAssistantMessage = (
  content: string,
  overrides: Partial<MockChatMessage> = {}
): MockChatMessage =>
  createMockChatMessage({
    id: 'msg-2',
    role: 'assistant',
    content,
    ...overrides,
  });

/**
 * 創建系統訊息
 */
export const createSystemMessage = (
  content: string,
  overrides: Partial<MockChatMessage> = {}
): MockChatMessage =>
  createMockChatMessage({
    id: 'msg-3',
    role: 'system',
    content,
    ...overrides,
  });

/**
 * 創建工具呼叫
 */
export const createMockToolCall = (
  overrides: Partial<MockToolCall> = {}
): MockToolCall => ({
  id: 'tool-1',
  name: 'execute_command',
  parameters: { command: 'ls -la' },
  status: 'pending',
  ...overrides,
});

/**
 * 創建帶工具呼叫的訊息
 */
export const createMessageWithToolCalls = (
  toolCalls: MockToolCall[],
  overrides: Partial<MockChatMessage> = {}
): MockChatMessage =>
  createMockChatMessage({
    role: 'assistant',
    content: 'I need to execute some commands',
    toolCalls,
    ...overrides,
  });

/**
 * 創建對話歷史
 */
export const createMockChatHistory = (count: number = 5): MockChatMessage[] =>
  Array.from({ length: count }, (_, i) =>
    createMockChatMessage({
      id: `msg-${i + 1}`,
      role: i % 2 === 0 ? 'user' : 'assistant',
      content: `Message ${i + 1}`,
      timestamp: new Date(Date.now() - (count - i) * 1000).toISOString(),
    })
  );

/**
 * 創建 Mock 對話
 */
export const createMockConversation = (
  overrides: Partial<MockConversation> = {}
): MockConversation => ({
  id: 'conv-1',
  workspaceId: 'ws-1',
  title: 'Test Conversation',
  messages: createMockChatHistory(5),
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  ...overrides,
});
