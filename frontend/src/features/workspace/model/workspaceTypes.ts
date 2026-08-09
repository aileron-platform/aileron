import type { OperationId } from '@/shared/authorization/operationIds';
import type { ResourceAccessRole } from '@/shared/authorization/resourceAccessRole';
import type { ResourceAccessSource } from '@/shared/authorization/resourceAuthorization';

export const WORKSPACE_ACCESS_SOURCE_BADGE_KEYS: Record<
  ResourceAccessSource,
  string
> = {
  owned: 'workspace.workspaceSettings.access.badges.owned',
  direct_share: 'workspace.workspaceSettings.access.badges.directShare',
  group_share: 'workspace.workspaceSettings.access.badges.groupShare',
  public: 'workspace.workspaceSettings.access.badges.public',
  platform_admin: 'workspace.workspaceSettings.access.badges.platformAdmin',
};

export interface WorkspaceListItem {
  id: string;
  name: string;
  description?: string | null;
  accessRole: ResourceAccessRole;
  allowedOperations: OperationId[];
  accessSource: ResourceAccessSource;
  accessSources: ResourceAccessSource[];
  provisioner?: 'docker' | 'kubernetes';
  targetNamespace?: string | null;
  overallPhase?: string;
  runtimeStatus: string;
  runtimeUrl: string;
  agenticTools?: string[];
  owner?: {
    id: string;
    displayName: string;
    avatarUrl?: string | null;
  };
}

export interface WorkspaceListResponse {
  items: WorkspaceListItem[];
}
