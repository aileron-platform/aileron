/**
 * ChatPanel 元件相關類型定義
 */

/**
 * Session 選單中顯示的對話選項
 */
export interface ChatSessionOption {
  /** Session 唯一識別碼 */
  session_id: string;
  /** Session 標題 */
  title: string;
  /** 訊息數量（可選） */
  messageCount?: number;
}
