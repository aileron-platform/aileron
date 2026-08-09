import type { AgenticTool } from '@/shared/types/agenticTool';

export type { AgenticTool };

export type WizardStepKey = 'basicInfo' | 'runtimeConfig' | 'workspaceCreation';

export interface BasicInfoForm {
  name: string;
  description: string;
  agenticTools: AgenticTool[];
}

export interface EnvVarItem {
  id: string;
  key: string;
  value: string;
}

export interface RuntimeConfigForm {
  runtime: string;
  setupScript: string;
  envVars: EnvVarItem[];
}

export interface WorkspaceWizardState {
  step: WizardStepKey;
  basicInfo: BasicInfoForm;
  runtimeConfig: RuntimeConfigForm;
  createdWorkspaceId: string | null;
  isSubmitting: boolean;
  isPolling: boolean;
  error: string | null;
}

export interface CreateWorkspacePayload {
  name: string;
  description: string;
  runtime: RuntimeConfigForm['runtime'];
  setupScript: string;
  envVars: Array<{ key: string; value: string }>;
  agenticTools: AgenticTool[];
}
