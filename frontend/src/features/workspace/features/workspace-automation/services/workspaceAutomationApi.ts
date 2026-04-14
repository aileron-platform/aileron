import {
  AutomationJob,
  JobExecution,
  AutomationMetrics,
} from '@/features/automation/types';
import { apiClient } from '@/shared/api/apiClient';

/**
 * 工作區自動化 API
 *
 * 注意：自動化任務存儲在 workspace-manager 中，不是 workspace-runtime
 * 因此這裡使用 apiClient 調用 workspace-manager 的 API
 */
export const workspaceAutomationApi = {
  /**
   * 獲取指定工作區的任務列表
   */
  async listJobs(_runtimeBaseUrl: string, workspaceId: string): Promise<AutomationJob[]> {
    const data = await apiClient.get<{ items: AutomationJob[] }>(
      `/automation/jobs?workspaceId=${workspaceId}`
    );
    return data.items;
  },

  /**
   * 獲取指定工作區的任務指標
   *
   * 注意：workspace-manager 目前沒有提供按工作區的指標 API
   * 這裡從任務列表計算指標
   */
  async getMetrics(_runtimeBaseUrl: string, workspaceId: string): Promise<AutomationMetrics> {
    const jobs = await this.listJobs(_runtimeBaseUrl, workspaceId);

    // 使用單次遍歷計算所有指標
    const metrics = jobs.reduce(
      (acc, job) => {
        // 統計任務狀態
        if (job.status === 'active') acc.activeCount++;
        else if (job.status === 'paused') acc.pausedCount++;
        else if (job.status === 'failed') acc.failedCount++;
        else if (job.status === 'draft') acc.draftCount++;

        // 累計執行統計
        acc.totalExecutions += job.totalExecutions;
        acc.successfulExecutions += Math.round(job.totalExecutions * job.successRate);
        acc.totalDuration += (job.averageDuration || 0) * job.totalExecutions;

        return acc;
      },
      {
        activeCount: 0,
        pausedCount: 0,
        failedCount: 0,
        draftCount: 0,
        totalExecutions: 0,
        successfulExecutions: 0,
        totalDuration: 0,
      }
    );

    return {
      activeCount: metrics.activeCount,
      pausedCount: metrics.pausedCount,
      failedCount: metrics.failedCount,
      draftCount: metrics.draftCount,
      successRate: metrics.totalExecutions > 0 ? metrics.successfulExecutions / metrics.totalExecutions : 0,
      runningExecutions: 0, // 需要從執行記錄獲取
      queuedExecutions: 0,  // 需要從執行記錄獲取
      averageDuration: metrics.totalExecutions > 0 ? metrics.totalDuration / metrics.totalExecutions : 0,
    };
  },

  /**
   * 獲取指定工作區的最近執行記錄
   */
  async getRecentExecutions(
    _runtimeBaseUrl: string,
    workspaceId: string,
    limit = 10,
  ): Promise<JobExecution[]> {
    const data = await apiClient.get<{ items: JobExecution[] }>(
      `/automation/executions?workspaceId=${workspaceId}&limit=${limit}`
    );
    return data.items;
  },

  /**
   * 獲取指定任務的執行記錄
   */
  async getJobExecutions(
    _runtimeBaseUrl: string,
    _workspaceId: string,
    jobId: string,
    limit = 20,
  ): Promise<JobExecution[]> {
    const data = await apiClient.get<{ items: JobExecution[] }>(
      `/automation/executions?jobId=${jobId}&limit=${limit}`
    );
    return data.items;
  },
};

export type WorkspaceAutomationApi = typeof workspaceAutomationApi;
