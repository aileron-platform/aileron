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

export interface ClaudeModelConfig {
  modelKey: string;
  modelName: string;
}

export interface ClaudeProviderConfig {
  provider: string;
  displayName: string;
}

export interface ClaudeCodeEnvironmentVariable {
  key: string;
  value: string;
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
  // 認證方式：subscription 或 apikey
  authMethod: string;

  // Subscription 認證相關
  subscriptionAuthCode?: string;
  subscriptionAccessToken?: string;
  subscriptionRefreshToken?: string;
  subscriptionExpiresAt?: number;  // 毫秒時間戳
  oauthAccount?: OAuthAccountInfo;

  // API Key 認證相關
  authKey: string | null;
  apiProvider?: string; // Anthropic, AWS Bedrock, Google Vertex AI, 其他

  // 統一的模型選擇欄位（不論 subscription 或 apikey 都使用這個）
  model?: string;

  // 環境變數設定
  environmentVariables: ClaudeCodeEnvironmentVariable[];
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
  git: UserSettingsGit;
}

export interface UserSettingsResponse {
  data: UserSettings;
}
