/**
 * 工具審批相關的類型定義
 */

/**
 * 審批狀態
 */
export enum ApprovalStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  DENIED = 'denied',
  TIMEOUT = 'timeout',
}

/**
 * 工具審批請求數據
 */
export interface ToolApprovalRequestData {
  request_id: string;
  session_id: string;
  workspace_id: string;
  tool_name: string;
  tool_input: Record<string, any>;
  timeout_seconds: number;
  requested_at?: string;
}

/**
 * 工具審批回應請求
 */
export interface ToolApprovalResponse {
  type: 'tool_approval_response';
  request_id: string;
  approved: boolean;
  reason?: string;
}

/**
 * WebSocket 工具審批請求事件
 */
export interface ToolApprovalRequestEvent {
  type: 'tool_approval_request';
  data: ToolApprovalRequestData;
}

/**
 * 審批對話框狀態
 */
export interface ApprovalDialogState {
  isOpen: boolean;
  request: ToolApprovalRequestData | null;
  remainingSeconds: number;
}

