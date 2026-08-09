import { apiClient } from '@/shared/api/apiClient';
import {
  AutomationMetrics,
  AutomationJob,
  JobCreateInput,
  JobExecution,
  JobExecutionPageParams,
  JobExecutionListResponse,
  JobListResponse,
  JobUpdateInput,
} from '../model/automationTypes';

const API_BASE = '/automation';

const appendWorkspaceScope = (path: string, workspaceId?: string): string => {
  if (!workspaceId) return path;
  const separator = path.includes('?') ? '&' : '?';
  const params = new URLSearchParams({ workspaceId });
  return `${path}${separator}${params.toString()}`;
};

const omitUndefined = <T extends object>(value: T): T => Object.fromEntries(
  Object.entries(value).filter(([, item]) => item !== undefined),
) as T;

const toCreateBody = (payload: JobCreateInput): JobCreateInput => {
  const {
    name, description, workspaceId, prompt, trigger, schedule, exact,
    agenticTool, model, agentConfig, webhookApiKey, deliveryWebhookUrl,
    failureDestination,
  } = payload;
  return omitUndefined({
    name, description, workspaceId, prompt, trigger, schedule, exact,
    agenticTool, model, agentConfig, webhookApiKey, deliveryWebhookUrl,
    failureDestination,
  });
};

const toUpdateBody = (payload: JobUpdateInput): Omit<JobUpdateInput, 'id'> => {
  const {
    name, description, prompt, status, trigger, schedule, exact,
    agenticTool, model, agentConfig, webhookApiKey, deliveryWebhookUrl,
    failureDestination,
  } = payload;
  return omitUndefined({
    name, description, prompt, status, trigger, schedule, exact,
    agenticTool, model, agentConfig, webhookApiKey, deliveryWebhookUrl,
    failureDestination,
  });
};

export const automationApi = {
  async listJobs(workspaceId?: string): Promise<AutomationJob[]> {
    const data = await apiClient.get<JobListResponse>(
      appendWorkspaceScope(`${API_BASE}/jobs`, workspaceId),
    );
    return data.items;
  },

  async getJob(jobId: string): Promise<AutomationJob> {
    return apiClient.get<AutomationJob>(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`);
  },

  async createJob(payload: JobCreateInput): Promise<AutomationJob> {
    return apiClient.post<AutomationJob>(`${API_BASE}/jobs`, toCreateBody(payload));
  },

  async updateJob(payload: JobUpdateInput): Promise<AutomationJob> {
    return apiClient.patch<AutomationJob>(
      `${API_BASE}/jobs/${encodeURIComponent(payload.id)}`,
      toUpdateBody(payload),
    );
  },

  async executeJob(jobId: string): Promise<JobExecution> {
    return apiClient.post<JobExecution>(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/run`);
  },

  async deleteJob(jobId: string): Promise<void> {
    await apiClient.delete<void>(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`);
  },

  async getMetrics(workspaceId?: string): Promise<AutomationMetrics> {
    return apiClient.get<AutomationMetrics>(
      appendWorkspaceScope(`${API_BASE}/metrics`, workspaceId),
    );
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

  async getJobExecutions(
    jobId: string,
    params: JobExecutionPageParams,
  ): Promise<JobExecutionListResponse> {
    const query = new URLSearchParams({
      page: params.page.toString(),
      pageSize: params.pageSize.toString(),
    });
    if (params.rangeStart) query.set('rangeStart', params.rangeStart);
    if (params.rangeEnd) query.set('rangeEnd', params.rangeEnd);
    return apiClient.get<JobExecutionListResponse>(
      `${API_BASE}/jobs/${encodeURIComponent(jobId)}/executions?${query.toString()}`
    );
  },

  async getExecution(executionId: string): Promise<JobExecution> {
    return apiClient.get<JobExecution>(
      `${API_BASE}/executions/${encodeURIComponent(executionId)}`
    );
  },

  async cancelExecution(executionId: string): Promise<JobExecution> {
    return apiClient.post<JobExecution>(
      `${API_BASE}/executions/${encodeURIComponent(executionId)}/cancel`
    );
  },
};
