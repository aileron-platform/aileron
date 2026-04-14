/**
 * 自動化任務執行相關的工具函數
 */

import { JobExecution, JobExecutionStatus } from '../types';

/**
 * 活躍的執行狀態（需要輪詢更新的狀態）
 */
export const ACTIVE_EXECUTION_STATUSES: JobExecutionStatus[] = ['running', 'queued', 'waiting'];

/**
 * 檢查執行記錄列表中是否有活躍的任務
 * 
 * @param executions 執行記錄列表
 * @returns 是否有活躍的任務（running, queued, waiting）
 */
export const hasActiveExecutions = (executions: JobExecution[]): boolean => {
  return executions.some(exec => ACTIVE_EXECUTION_STATUSES.includes(exec.status));
};

/**
 * 檢查單個執行記錄是否為活躍狀態
 * 
 * @param execution 執行記錄
 * @returns 是否為活躍狀態
 */
export const isActiveExecution = (execution: JobExecution): boolean => {
  return ACTIVE_EXECUTION_STATUSES.includes(execution.status);
};

/**
 * 檢查執行記錄是否可以取消
 * 
 * @param execution 執行記錄
 * @returns 是否可以取消（只有 waiting 狀態可以取消）
 */
export const isCancellableExecution = (execution: JobExecution): boolean => {
  return execution.status === 'waiting';
};

