/**
 * 模板中心 SSH Keys API
 */

import { apiClient } from '@/shared/api/apiClient';

// ============ 型別定義 ============

export interface SSHKeys {
  publicKey: string | null;
  privateKey: string | null;
  fingerprint: string | null;
  lastRotatedAt: string | null;
}

export interface SSHKeysResponse {
  success: boolean;
  data?: SSHKeys;
  error?: string;
}

export interface GenerateSSHKeysResponse {
  success: boolean;
  data?: {
    publicKey: string;
    privateKey: string;
    fingerprint: string;
    generatedAt: string;
  };
  message?: string;
  error?: string;
}

export interface DeleteSSHKeysResponse {
  success: boolean;
  message?: string;
  error?: string;
}

// ============ API 方法 ============

/**
 * 取得 SSH Keys
 */
export async function getSSHKeys(): Promise<SSHKeysResponse> {
  return apiClient.get<SSHKeysResponse>('/templates/marketplace/ssh-keys');
}

/**
 * 產生新的 SSH Key Pair
 */
export async function generateSSHKeys(): Promise<GenerateSSHKeysResponse> {
  return apiClient.post<GenerateSSHKeysResponse>('/templates/marketplace/ssh-keys/generate', {});
}

/**
 * 更新 SSH Keys
 */
export async function updateSSHKeys(
  privateKey: string,
  publicKey: string
): Promise<GenerateSSHKeysResponse> {
  return apiClient.put<GenerateSSHKeysResponse>('/templates/marketplace/ssh-keys', {
    privateKey,
    publicKey,
  });
}

/**
 * 刪除 SSH Keys
 */
export async function deleteSSHKeys(): Promise<DeleteSSHKeysResponse> {
  return apiClient.delete<DeleteSSHKeysResponse>('/templates/marketplace/ssh-keys');
}
