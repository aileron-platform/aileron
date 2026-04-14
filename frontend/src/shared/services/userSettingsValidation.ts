/**
 * 用戶設定驗證服務
 * 檢查用戶是否完成必要的系統設定
 */

import type { UserSettings } from '@/shared/types/user';

export interface SettingsValidationResult {
  isValid: boolean;
  missingSettings: string[];
  details: {
    ssh: boolean;
    claudeCode: boolean;
    git: boolean;
  };
}

/**
 * 驗證 SSH 設定是否完整
 */
function validateSSHSettings(ssh: UserSettings['ssh']): boolean {
  // SSH 設定需要有 public key 和 private key
  return Boolean(ssh.publicKey && ssh.privateKey);
}

/**
 * 驗證 Git 設定是否完整
 */
function validateGitSettings(git: UserSettings['git']): boolean {
  // Git 設定需要有用戶名和郵箱
  return Boolean(git.userName && git.userEmail);
}

/**
 * 驗證用戶設定是否完整
 * 
 * @param settings 用戶設定
 * @returns 驗證結果
 */
export function validateUserSettings(settings: UserSettings): SettingsValidationResult {
  const sshValid = validateSSHSettings(settings.ssh);
  const gitValid = validateGitSettings(settings.git);

  const missingSettings: string[] = [];
  
  if (!sshValid) {
    missingSettings.push('SSH Keys');
  }

  if (!gitValid) {
    missingSettings.push('Git');
  }

  return {
    isValid: sshValid && gitValid,
    missingSettings,
    details: {
      ssh: sshValid,
      claudeCode: true,
      git: gitValid,
    },
  };
}

/**
 * 獲取缺失設定的描述文字
 */
export function getMissingSettingsDescription(
  missingSettings: string[],
  t: (key: string, params?: Record<string, string | number>) => string
): string {
  if (missingSettings.length === 0) {
    return '';
  }

  if (missingSettings.length === 1) {
    return t('validation.settings.missingSingle', { setting: missingSettings[0] });
  }

  const lastSetting = missingSettings[missingSettings.length - 1];
  const otherSettings = missingSettings.slice(0, -1).join('、');

  return t('validation.settings.missingMultiple', {
    settings: otherSettings,
    lastSetting
  });
}
