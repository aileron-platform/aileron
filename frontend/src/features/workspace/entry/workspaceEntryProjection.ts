import {
  WORKSPACE_ENTRY_ACTION_IDS,
  type WorkspaceAuthorizationEntrySource,
  type WorkspaceEntryAction,
  type WorkspaceEntryActionEmphasis,
  type WorkspaceEntryProjection,
  type WorkspaceEntryProjectionInput,
  type WorkspaceEntryStage,
  type WorkspaceExecutionEntrySource,
  type WorkspaceIdentityEntrySource,
} from '@/shared/components/entry/workspaceEntryTypes';
import { WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE } from '../api/workspaceLifecycleApi';

const ENTRY_TITLE_KEY = 'common.entry.title';
const ENTRY_STAGE_DESCRIPTION_KEYS = {
  identity: 'common.entry.descriptions.identity',
  workspace: 'common.entry.descriptions.workspace',
  execution: 'common.entry.descriptions.execution',
} as const;

const ACTION_EMPHASIS: Record<
  Exclude<WorkspaceEntryAction['id'], 'login' | 'create'>,
  WorkspaceEntryActionEmphasis
> = {
  refresh: 'primary',
  start: 'primary',
  retry: 'primary',
  rebuild: 'danger-secondary',
  return: 'secondary',
};

const stage = (
  id: WorkspaceEntryStage['id'],
  status: WorkspaceEntryStage['status'],
): WorkspaceEntryStage => ({ id, status });

const action = (
  id: WorkspaceEntryAction['id'],
  emphasis: WorkspaceEntryActionEmphasis,
): WorkspaceEntryAction => ({ id, emphasis });

const actionsFromAllowedValues = (
  allowedActions: readonly string[] | undefined,
): WorkspaceEntryAction[] => {
  const allowed = new Set(allowedActions ?? []);
  return WORKSPACE_ENTRY_ACTION_IDS
    .filter((id): id is Exclude<WorkspaceEntryAction['id'], 'login' | 'create'> => (
      id === 'start'
      || id === 'retry'
      || id === 'rebuild'
      || id === 'refresh'
      || id === 'return'
    ))
    .filter(id => allowed.has(id))
    .map(id => action(id, ACTION_EMPHASIS[id]));
};

const reasonCodeOf = (
  source: WorkspaceIdentityEntrySource
    | WorkspaceAuthorizationEntrySource
    | WorkspaceExecutionEntrySource,
): string | null => source.reasonCode ?? null;

const identityStages = (
  identity: WorkspaceIdentityEntrySource,
): {
  identity: WorkspaceEntryStage;
  workspace: WorkspaceEntryStage;
  execution: WorkspaceEntryStage;
  activeStage: WorkspaceEntryStage['id'];
  actions: readonly WorkspaceEntryAction[];
  reasonCode: string | null;
} => {
  if (identity.status === 'checking') {
    return {
      identity: stage('identity', 'active'),
      workspace: stage('workspace', 'pending'),
      execution: stage('execution', 'pending'),
      activeStage: 'identity',
      actions: [],
      reasonCode: null,
    };
  }

  if (identity.status === 'failed' || identity.status === 'unauthenticated') {
    return {
      identity: stage('identity', identity.status === 'failed' ? 'failed' : 'active'),
      workspace: stage('workspace', 'pending'),
      execution: stage('execution', 'pending'),
      activeStage: 'identity',
      actions: [action('login', 'primary')],
      reasonCode: reasonCodeOf(identity),
    };
  }

  return {
    identity: stage('identity', 'complete'),
    workspace: stage('workspace', 'active'),
    execution: stage('execution', 'pending'),
    activeStage: 'workspace',
    actions: [],
    reasonCode: null,
  };
};

const workspaceStages = (
  workspace: WorkspaceAuthorizationEntrySource,
): {
  workspace: WorkspaceEntryStage;
  activeStage: WorkspaceEntryStage['id'];
  actions: readonly WorkspaceEntryAction[];
  reasonCode: string | null;
} => {
  switch (workspace.status) {
    case 'checking':
      return {
        workspace: stage('workspace', 'active'),
        activeStage: 'workspace',
        actions: [],
        reasonCode: null,
      };
    case 'empty':
      return {
        workspace: stage('workspace', 'action_required'),
        activeStage: 'workspace',
        actions: workspace.canCreate ? [action('create', 'primary')] : [],
        reasonCode: reasonCodeOf(workspace),
      };
    case 'deleting':
      return {
        workspace: stage('workspace', 'action_required'),
        activeStage: 'workspace',
        actions: actionsFromAllowedValues(workspace.allowedActions),
        reasonCode: reasonCodeOf(workspace),
      };
    case 'denied':
    case 'not_found':
    case 'failed':
      return {
        workspace: stage('workspace', 'failed'),
        activeStage: 'workspace',
        actions: actionsFromAllowedValues(workspace.allowedActions),
        reasonCode: reasonCodeOf(workspace),
      };
    case 'ready':
      return {
        workspace: stage('workspace', 'complete'),
        activeStage: 'execution',
        actions: [],
        reasonCode: null,
      };
    default: {
      const exhaustive: never = workspace;
      return exhaustive;
    }
  }
};

const executionStage = (
  execution: WorkspaceExecutionEntrySource,
): {
  execution: WorkspaceEntryStage;
  activeStage: WorkspaceEntryStage['id'];
  actions: readonly WorkspaceEntryAction[];
  reasonCode: string | null;
} => {
  switch (execution.status) {
    case 'checking':
    case 'transitioning':
      return {
        execution: stage('execution', 'active'),
        activeStage: 'execution',
        actions: actionsFromAllowedValues(execution.allowedActions),
        reasonCode: reasonCodeOf(execution),
      };
    case 'ready':
      return {
        execution: stage('execution', 'complete'),
        activeStage: 'execution',
        actions: [],
        reasonCode: null,
      };
    case 'stopped':
      return {
        execution: stage('execution', 'action_required'),
        activeStage: 'execution',
        actions: actionsFromAllowedValues(execution.allowedActions),
        reasonCode: reasonCodeOf(execution),
      };
    case 'uncertain':
      return {
        execution: stage('execution', 'uncertain'),
        activeStage: 'execution',
        actions: [
          action('refresh', 'primary'),
          ...(execution.allowedActions?.includes('return')
            ? [action('return', 'secondary')]
            : []),
        ],
        reasonCode: reasonCodeOf(execution),
      };
    case 'blocked':
    case 'failed':
      return {
        execution: stage('execution', 'failed'),
        activeStage: 'execution',
        actions: actionsFromAllowedValues(execution.allowedActions),
        reasonCode: reasonCodeOf(execution),
      };
    default: {
      const exhaustive: never = execution;
      return exhaustive;
    }
  }
};


export const projectWorkspaceEntry = (
  input: WorkspaceEntryProjectionInput,
): WorkspaceEntryProjection => {
  const identity = identityStages(input.identity);
  if (input.identity.status !== 'authenticated') {
    return {
      stages: [identity.identity, identity.workspace, identity.execution],
      activeStage: identity.activeStage,
      titleKey: ENTRY_TITLE_KEY,
      descriptionKey: input.identity.status === 'failed'
        ? 'common.entry.descriptions.identityFailed'
        : ENTRY_STAGE_DESCRIPTION_KEYS.identity,
      reasonCode: identity.reasonCode,
      actions: identity.actions,
    };
  }

  const workspace = workspaceStages(input.workspace);
  if (input.workspace.status !== 'ready') {
    return {
      stages: [
        identity.identity,
        workspace.workspace,
        stage('execution', 'pending'),
      ],
      activeStage: workspace.activeStage,
      titleKey: ENTRY_TITLE_KEY,
      descriptionKey: workspace.workspace.status === 'failed'
        ? 'common.entry.descriptions.workspaceFailed'
        : ENTRY_STAGE_DESCRIPTION_KEYS.workspace,
      reasonCode: workspace.reasonCode,
      actions: workspace.actions,
    };
  }

  const execution = executionStage(input.execution);
  return {
    stages: [
      identity.identity,
      workspace.workspace,
      execution.execution,
    ],
    activeStage: execution.activeStage,
    titleKey: ENTRY_TITLE_KEY,
    descriptionKey: execution.reasonCode === WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE
      ? 'common.entry.descriptions.executionPlaneDrift'
      : execution.execution.status === 'failed'
        ? 'common.entry.descriptions.executionFailed'
        : ENTRY_STAGE_DESCRIPTION_KEYS.execution,
    reasonCode: execution.reasonCode,
    actions: execution.actions,
  };
};
