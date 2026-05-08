export type WizardStepKey = 'basicInfo' | 'runtimeConfig' | 'workspaceCreation' | 'settingsSync';

export type CliType = 'claude-code' | 'codex' | 'gemini';

export interface BasicInfoForm {
  name: string;
  description: string;
  gitUrl: string;
  branch: string;
  cliType: CliType;
}

export interface EnvVarItem {
  id: string;
  key: string;
  value: string;
}

export interface RuntimeConfigForm {
  runtime: string; // 動態從容器映像配置載入
  provisioner: 'docker' | 'kubernetes';
  targetNamespace: string | null;
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
  gitUrl?: string;
  branch?: string;
  runtime: RuntimeConfigForm['runtime'];
  targetNamespace?: string;
  setupScript: string;
  envVars: Array<{ key: string; value: string }>;
  cliType: CliType;
}

export interface WizardCLIInfo {
  workspaceId: string;
  instructions: string[];
  commands: string[];
}
