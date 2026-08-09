import type { SyncWorkspaceResult } from './settings/settingsSyncApi';
import type { UserSettingsCodex, UserSettingsOpenCode, UserToolModelSelection } from '@/shared/types/user';

export const cloneDeep = <T,>(value: T): T => {
  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value)) as T;
};

export const normalizeModelSelection = (
  value: Partial<UserToolModelSelection> | null | undefined,
  current?: UserToolModelSelection | null,
): UserToolModelSelection => {
  const availableModels = value?.availableModels?.length
    ? value.availableModels
    : current?.availableModels || [];
  const allowedModels = value?.allowedModels?.length
    ? value.allowedModels
    : current?.allowedModels || availableModels;
  const defaultModel = value?.defaultModel && allowedModels.includes(value.defaultModel)
    ? value.defaultModel
    : current?.defaultModel && allowedModels.includes(current.defaultModel)
      ? current.defaultModel
      : allowedModels[0] || '';

  return {
    customModels: value?.customModels || current?.customModels || [],
    availableModels,
    allowedModels,
    defaultModel,
  };
};

export const normalizeCodexSettings = (
  codex: Partial<UserSettingsCodex> | null | undefined,
  current?: UserSettingsCodex | null,
): UserSettingsCodex => ({
  authMethod: codex?.authMethod || current?.authMethod || 'subscription',
  loginStatus: codex?.loginStatus || 'notConnected',
  account: codex?.account ?? null,
  model: codex?.model || current?.model || codex?.modelSelection?.defaultModel || current?.modelSelection.defaultModel || '',
  environmentVariables: codex?.environmentVariables || current?.environmentVariables || [],
  modelSelection: normalizeModelSelection(
    codex?.modelSelection ?? current?.modelSelection,
    current?.modelSelection,
  ),
  authFlow: codex?.authFlow ?? null,
  lastSyncedAt: codex?.lastSyncedAt ?? current?.lastSyncedAt,
  lastSyncError: codex?.lastSyncError ?? current?.lastSyncError,
});

export const normalizeOpenCodeSettings = (
  opencode: Partial<UserSettingsOpenCode> | null | undefined,
  current?: UserSettingsOpenCode | null,
): UserSettingsOpenCode => ({
  model: opencode?.model || current?.model || opencode?.modelSelection?.defaultModel || current?.modelSelection.defaultModel || '',
  environmentVariables: opencode?.environmentVariables || current?.environmentVariables || [],
  modelSelection: normalizeModelSelection(
    opencode?.modelSelection ?? current?.modelSelection,
    current?.modelSelection,
  ),
});

export const hasSuccessfulSyncDetail = (workspace: SyncWorkspaceResult): boolean =>
  Object.values(workspace.details ?? {}).some((detail) => detail?.success);

export const getPartialSyncWorkspaceCount = (workspaces: SyncWorkspaceResult[]): number =>
  workspaces.filter((workspace) => !workspace.success && hasSuccessfulSyncDetail(workspace)).length;
