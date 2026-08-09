import { apiClient } from '@/shared/api/apiClient';

export type WorkspaceCapacityStorageKind = 'workspace_data' | 'runtime_home';
export type WorkspaceCapacityRisk = 'normal' | 'warning' | 'critical' | 'unknown' | 'stale';

export interface WorkspaceCapacityHistoryPoint {
  date: string;
  usedBytes: number;
}

export interface WorkspaceCapacityItem {
  storageKind: WorkspaceCapacityStorageKind;
  usedBytes: number | null;
  allocatedBytes: number | null;
  hostAvailableBytes: number | null;
  utilizationPercent: number | null;
  risk: WorkspaceCapacityRisk;
  measuredAt: string | null;
  history: WorkspaceCapacityHistoryPoint[];
}

export interface WorkspaceCapacityResponse {
  provisioner: 'docker' | 'kubernetes';
  timeZone: string;
  items: WorkspaceCapacityItem[];
}

export const getWorkspaceCapacity = (workspaceId: string): Promise<WorkspaceCapacityResponse> => (
  apiClient.get(`/workspaces/${encodeURIComponent(workspaceId)}/capacity?range=7d`)
);
