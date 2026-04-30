
import { apiClient } from '@/shared/api/apiClient';



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



export async function getSSHKeys(): Promise<SSHKeysResponse> {
  return apiClient.get<SSHKeysResponse>('/templates/marketplace/ssh-keys');
}

export async function generateSSHKeys(): Promise<GenerateSSHKeysResponse> {
  return apiClient.post<GenerateSSHKeysResponse>('/templates/marketplace/ssh-keys/generate', {});
}

export async function updateSSHKeys(
  privateKey: string,
  publicKey: string
): Promise<GenerateSSHKeysResponse> {
  return apiClient.put<GenerateSSHKeysResponse>('/templates/marketplace/ssh-keys', {
    privateKey,
    publicKey,
  });
}

export async function deleteSSHKeys(): Promise<DeleteSSHKeysResponse> {
  return apiClient.delete<DeleteSSHKeysResponse>('/templates/marketplace/ssh-keys');
}
