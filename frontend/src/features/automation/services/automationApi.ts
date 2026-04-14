import { apiClient } from '../../../shared/api/apiClient';
import {
  AutomationMetrics,
  AutomationJob,
  ExecutionCancelResponse,
  JobCalendarEvent,
  JobCalendarResponse,
  JobCreateInput,
  JobExecution,
  JobListResponse,
  JobStatus,
  JobStatusUpdateInput,
  JobUpdateInput,
  WorkspaceQueueResponse,
} from '../types';

const API_BASE = '/automation';

export const automationApi = {
  async listJobs(): Promise<AutomationJob[]> {
    const data = await apiClient.get<JobListResponse>(`${API_BASE}/jobs`);
    return data.items;
  },

  async getJob(jobId: string): Promise<AutomationJob> {
    return apiClient.get<AutomationJob>(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`);
  },

  async createJob(payload: JobCreateInput): Promise<AutomationJob> {
    return apiClient.post<AutomationJob>(`${API_BASE}/jobs`, payload);
  },

  async updateJob(payload: JobUpdateInput): Promise<AutomationJob> {
    const { id, ...rest } = payload;
    return apiClient.patch<AutomationJob>(`${API_BASE}/jobs/${encodeURIComponent(id)}`, rest);
  },

  async executeJob(jobId: string): Promise<JobExecution> {
    return apiClient.post<JobExecution>(
      `${API_BASE}/jobs/${encodeURIComponent(jobId)}/execute`
    );
  },

  async deleteJob(jobId: string): Promise<void> {
    await apiClient.delete<void>(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`);
  },

  async updateJobStatus(jobId: string, status: JobStatus): Promise<AutomationJob> {
    const body: JobStatusUpdateInput = { status };
    return apiClient.post<AutomationJob>(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/status`, body);
  },

  async getMetrics(): Promise<AutomationMetrics> {
    return apiClient.get<AutomationMetrics>(`${API_BASE}/metrics`);
  },

  async getRecentExecutions(limit = 10): Promise<JobExecution[]> {
    const params = new URLSearchParams();
    if (limit) {
      params.set('limit', limit.toString());
    }
    const query = params.toString();
    const path = query.length > 0 ? `${API_BASE}/executions?${query}` : `${API_BASE}/executions`;
    const data = await apiClient.get<{ items: JobExecution[]; total: number }>(path);
    return data.items;
  },

  async getCalendarEvents(): Promise<JobCalendarEvent[]> {
    const data = await apiClient.get<JobCalendarResponse>(`${API_BASE}/calendar`);
    return data.items;
  },

  async getWorkspaceQueue(workspaceId: string): Promise<WorkspaceQueueResponse> {
    return apiClient.get<WorkspaceQueueResponse>(
      `${API_BASE}/workspaces/${encodeURIComponent(workspaceId)}/queue`
    );
  },

  async cancelExecution(executionId: string): Promise<ExecutionCancelResponse> {
    return apiClient.post<ExecutionCancelResponse>(
      `${API_BASE}/executions/${encodeURIComponent(executionId)}/cancel`
    );
  },
};

export type AutomationApi = typeof automationApi;
