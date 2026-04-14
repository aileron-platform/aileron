/**
 * API 回應測試資料 Fixtures
 */

import { MockUser } from './user';
import { MockWorkspace } from './workspace';
import { MockChatMessage, MockConversation } from './chat';

/**
 * 標準 API 回應格式
 */
export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  message?: string;
  status?: number;
}

/**
 * 分頁回應格式
 */
export interface PaginatedResponse<T = any> {
  data: T[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

/**
 * 創建成功回應
 */
export const createSuccessResponse = <T>(data: T, message?: string): ApiResponse<T> => ({
  data,
  message: message || 'Success',
  status: 200,
});

/**
 * 創建錯誤回應
 */
export const createErrorResponse = (error: string, status: number = 400): ApiResponse => ({
  error,
  status,
});

/**
 * 創建分頁回應
 */
export const createPaginatedResponse = <T>(
  data: T[],
  page: number = 1,
  pageSize: number = 10,
  total?: number
): PaginatedResponse<T> => ({
  data,
  pagination: {
    page,
    pageSize,
    total: total || data.length,
    totalPages: Math.ceil((total || data.length) / pageSize),
  },
});

/**
 * 使用者相關 API 回應
 */
export const mockUserApiResponses = {
  login: (user: MockUser, token: string = 'mock-token') =>
    createSuccessResponse({ user, token }, 'Login successful'),
  logout: () => createSuccessResponse(null, 'Logout successful'),
  getCurrentUser: (user: MockUser) => createSuccessResponse(user),
  updateProfile: (user: MockUser) => createSuccessResponse(user, 'Profile updated'),
  error: {
    unauthorized: createErrorResponse('Unauthorized', 401),
    notFound: createErrorResponse('User not found', 404),
    invalidCredentials: createErrorResponse('Invalid credentials', 401),
  },
};

/**
 * 工作區相關 API 回應
 */
export const mockWorkspaceApiResponses = {
  list: (workspaces: MockWorkspace[]) => createSuccessResponse(workspaces),
  get: (workspace: MockWorkspace) => createSuccessResponse(workspace),
  create: (workspace: MockWorkspace) => createSuccessResponse(workspace, 'Workspace created'),
  update: (workspace: MockWorkspace) => createSuccessResponse(workspace, 'Workspace updated'),
  delete: () => createSuccessResponse(null, 'Workspace deleted'),
  start: (workspace: MockWorkspace) =>
    createSuccessResponse({ ...workspace, status: 'running' }, 'Workspace started'),
  stop: (workspace: MockWorkspace) =>
    createSuccessResponse({ ...workspace, status: 'stopped' }, 'Workspace stopped'),
  error: {
    notFound: createErrorResponse('Workspace not found', 404),
    forbidden: createErrorResponse('Access forbidden', 403),
    alreadyRunning: createErrorResponse('Workspace is already running', 400),
  },
};

/**
 * 聊天相關 API 回應
 */
export const mockChatApiResponses = {
  sendMessage: (message: MockChatMessage) => createSuccessResponse(message, 'Message sent'),
  getHistory: (messages: MockChatMessage[]) => createSuccessResponse(messages),
  getConversation: (conversation: MockConversation) => createSuccessResponse(conversation),
  deleteMessage: () => createSuccessResponse(null, 'Message deleted'),
  approveTool: (toolCallId: string) =>
    createSuccessResponse({ id: toolCallId, status: 'approved' }, 'Tool approved'),
  rejectTool: (toolCallId: string) =>
    createSuccessResponse({ id: toolCallId, status: 'rejected' }, 'Tool rejected'),
  error: {
    conversationNotFound: createErrorResponse('Conversation not found', 404),
    messageNotFound: createErrorResponse('Message not found', 404),
    tooLong: createErrorResponse('Message too long', 400),
  },
};

/**
 * 通用 API 錯誤
 */
export const mockCommonApiErrors = {
  badRequest: createErrorResponse('Bad request', 400),
  unauthorized: createErrorResponse('Unauthorized', 401),
  forbidden: createErrorResponse('Forbidden', 403),
  notFound: createErrorResponse('Not found', 404),
  conflict: createErrorResponse('Conflict', 409),
  internalServerError: createErrorResponse('Internal server error', 500),
  networkError: createErrorResponse('Network error', 0),
};
