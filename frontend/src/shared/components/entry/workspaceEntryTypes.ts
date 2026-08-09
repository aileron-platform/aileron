export const WORKSPACE_ENTRY_STAGE_IDS = [
  'identity',
  'workspace',
  'execution',
] as const;

export type WorkspaceEntryStageId = typeof WORKSPACE_ENTRY_STAGE_IDS[number];

export const WORKSPACE_ENTRY_STATUS_IDS = [
  'pending',
  'active',
  'complete',
  'action_required',
  'uncertain',
  'failed',
] as const;

export type WorkspaceEntryStageStatus = typeof WORKSPACE_ENTRY_STATUS_IDS[number];

export const WORKSPACE_ENTRY_ACTION_IDS = [
  'login',
  'create',
  'refresh',
  'start',
  'retry',
  'rebuild',
  'return',
] as const;

export type WorkspaceEntryActionId = typeof WORKSPACE_ENTRY_ACTION_IDS[number];

export type WorkspaceEntryActionEmphasis =
  | 'primary'
  | 'secondary'
  | 'danger-secondary';

export interface WorkspaceEntryStage {
  id: WorkspaceEntryStageId;
  status: WorkspaceEntryStageStatus;
}

export interface WorkspaceEntryAction {
  id: WorkspaceEntryActionId;
  emphasis: WorkspaceEntryActionEmphasis;
}

export interface WorkspaceEntryProjectionBase {
  activeStage: WorkspaceEntryStageId;
  titleKey: string;
  descriptionKey: string;
  reasonCode: string | null;
  actions: readonly WorkspaceEntryAction[];
}

export interface WorkspaceEntryProjection extends WorkspaceEntryProjectionBase {
  stages: readonly [
    WorkspaceEntryStage,
    WorkspaceEntryStage,
    WorkspaceEntryStage,
  ];
}

export interface PlatformIdentityEntryProjection extends WorkspaceEntryProjectionBase {
  stages: readonly [WorkspaceEntryStage];
}

export type WorkspaceIdentityEntrySource =
  | { status: 'checking'; reasonCode?: string | null }
  | { status: 'unauthenticated'; reasonCode?: string | null }
  | { status: 'authenticated'; reasonCode?: string | null }
  | { status: 'failed'; reasonCode?: string | null };

export type WorkspaceAuthorizationEntrySource =
  | { status: 'checking'; reasonCode?: string | null }
  | { status: 'ready'; canCreate: boolean; reasonCode?: string | null }
  | {
      status: 'empty';
      canCreate: boolean;
      allowedActions?: readonly string[];
      reasonCode?: string | null;
    }
  | {
      status: 'deleting' | 'denied' | 'not_found' | 'failed';
      allowedActions?: readonly string[];
      reasonCode?: string | null;
    };

export type WorkspaceExecutionEntrySource =
  | { status: 'checking'; reasonCode?: string | null; allowedActions?: readonly string[] }
  | { status: 'ready'; reasonCode?: string | null; allowedActions?: readonly string[] }
  | { status: 'transitioning'; reasonCode?: string | null; allowedActions?: readonly string[] }
  | { status: 'stopped'; reasonCode?: string | null; allowedActions?: readonly string[] }
  | { status: 'uncertain'; reasonCode?: string | null; allowedActions?: readonly string[] }
  | { status: 'blocked' | 'failed'; reasonCode?: string | null; allowedActions?: readonly string[] };

export interface WorkspaceEntryProjectionInput {
  identity: WorkspaceIdentityEntrySource;
  workspace: WorkspaceAuthorizationEntrySource;
  execution: WorkspaceExecutionEntrySource;
}
