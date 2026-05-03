import { apiClient } from '@/shared/api/apiClient';

export interface GeminiAuthResponse {
  success: boolean;
  message: string;
  access_token: string;
  refresh_token: string | null;
  id_token: string | null;
  expires_at: number;
  scope: string;
  email: string | null;
  name: string | null;
  needs_sync: boolean;
}

export class GeminiOAuthApiService {
  static async authenticate(authCode: string, verifier: string): Promise<GeminiAuthResponse> {
    return apiClient.post<GeminiAuthResponse>('/gemini-oauth/authenticate', {
      auth_code: authCode,
      verifier,
    });
  }

  static async disconnect(): Promise<void> {
    await apiClient.post('/gemini-oauth/disconnect', {});
  }
}
