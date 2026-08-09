export interface UserProfile {
  userId: string;
  username: string;
  firstName: string;
  lastName: string;
  email: string;
  avatarUrl: string | null;
}

export interface UserProfileResponse {
  data: UserProfile;
}

export interface UserSettingsNotifications {
  desktop: boolean;
  email: boolean;
  updates: boolean;
}

export interface UserSettingsPerformance {
  autoSave: boolean;
  animationsEnabled: boolean;
}

export interface UserSettingsPrivacy {
  analytics: boolean;
  crashReports: boolean;
  usageData: boolean;
}

export interface UserSettingsGeneral {
  theme: 'light' | 'dark' | 'system';
  language: 'zh-TW' | 'en';
  timezone: string;
  notifications: UserSettingsNotifications;
  performance: UserSettingsPerformance;
  privacy: UserSettingsPrivacy;
}

export interface UserSettingsSSH {
  publicKey: string | null;
  privateKey: string | null;
  fingerprint: string | null;
  lastRotatedAt: string | null;
}

export interface UserToolEnvironmentVariable {
  key: string;
  value: string;
}

export interface UserToolModelSelection {
  customModels: string[];
  availableModels: string[];
  allowedModels: string[];
  defaultModel: string;
}

export interface OAuthAccountInfo {
  accountUuid?: string;
  emailAddress?: string;
  organizationUuid?: string;
  displayName?: string;
  organizationBillingType?: string;
  organizationRole?: string;
  workspaceRole?: string | null;
  organizationName?: string;
}

export interface UserSettingsClaudeCode {
  authMethod: string;

  subscriptionAuthCode?: string;
  subscriptionAccessToken?: string;
  subscriptionRefreshToken?: string;
  subscriptionExpiresAt?: number;
  oauthAccount?: OAuthAccountInfo;

  authKey: string | null;
  apiProvider?: string;

  model?: string;

  environmentVariables: UserToolEnvironmentVariable[];
  modelSelection: UserToolModelSelection;
}

export type CodexLoginStatus = 'notConnected' | 'pending' | 'connected' | 'needsRelogin' | 'error';

export interface CodexAccountInfo {
  accountId?: string | null;
  email?: string | null;
  planType?: string | null;
}

export interface CodexAuthFlow {
  loginId?: string | null;
  authUrl?: string | null;
  verificationUrl?: string | null;
  userCode?: string | null;
  expiresAt?: number | null;
}

export interface UserSettingsCodex {
  authMethod: 'subscription' | 'apikey';
  loginStatus: CodexLoginStatus;
  account?: CodexAccountInfo | null;
  model: string;
  environmentVariables: UserToolEnvironmentVariable[];
  modelSelection: UserToolModelSelection;
  authFlow?: CodexAuthFlow | null;
  lastSyncedAt?: number | null;
  lastSyncError?: string | null;
}

export interface UserSettingsOpenCode {
  model: string;
  environmentVariables: UserToolEnvironmentVariable[];
  modelSelection: UserToolModelSelection;
}

export interface UserSettingsGit {
  userName: string | null;
  userEmail: string | null;
  signingKey: string | null;
}

export interface UserSettings {
  general: UserSettingsGeneral;
  ssh: UserSettingsSSH;
  claudeCode: UserSettingsClaudeCode;
  codex: UserSettingsCodex;
  opencode: UserSettingsOpenCode;
  git: UserSettingsGit;
}

export interface UserSettingsResponse {
  data: UserSettings;
}
