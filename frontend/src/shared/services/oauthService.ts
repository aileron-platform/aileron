/**
 * OAuth 認證服務 - 簡化版本，只處理開新視窗
 */

import {
  generateState,
  generateCodeVerifier,
  generateCodeChallenge
} from '@/shared/utils/oauth';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('OAuthService');

export class OAuthService {
  private static readonly CLIENT_ID = '9d1c250a-e61b-44d9-88ed-5944d1962f5e';
  private static readonly AUTHORIZATION_URL = 'https://claude.ai/oauth/authorize';
  private static readonly REDIRECT_URI = 'https://console.anthropic.com/oauth/code/callback';
  private static readonly SCOPE = 'org:create_api_key user:profile user:inference';  // ✅ 修正順序
  private static readonly VERIFIER_STORAGE_KEY = 'claude_oauth_verifier';

  /**
   * 生成安全的隨機 state 參數
   */
  static generateStateParam(): string {
    return generateState();
  }

  /**
   * 生成 PKCE code challenge 和 verifier
   * 使用真正的 SHA256 算法
   */
  static async generatePKCE(): Promise<{ codeVerifier: string; codeChallenge: string }> {
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);

    return {
      codeVerifier,
      codeChallenge
    };
  }

  /**
   * 儲存 verifier 到 localStorage
   */
  static saveVerifier(verifier: string): void {
    localStorage.setItem(this.VERIFIER_STORAGE_KEY, verifier);
  }

  /**
   * 從 localStorage 取得 verifier
   */
  static getVerifier(): string | null {
    return localStorage.getItem(this.VERIFIER_STORAGE_KEY);
  }

  /**
   * 清除儲存的 verifier
   */
  static clearVerifier(): void {
    localStorage.removeItem(this.VERIFIER_STORAGE_KEY);
  }

  /**
   * 建構 OAuth 授權 URL 並儲存 verifier
   * 注意：根據參考程式，state 參數應該使用 verifier 的值
   */
  static async buildAuthorizationURL(): Promise<{ url: string; verifier: string }> {
    const { codeVerifier, codeChallenge } = await this.generatePKCE();

    // 重要：state 參數使用 verifier 的值（參考 AuthAnthropic.authorize）
    const params = new URLSearchParams({
      code: 'true',
      client_id: this.CLIENT_ID,
      response_type: 'code',
      redirect_uri: this.REDIRECT_URI,
      scope: this.SCOPE,
      code_challenge: codeChallenge,
      code_challenge_method: 'S256',
      state: codeVerifier,  // 使用 verifier 作為 state
    });

    const url = `${this.AUTHORIZATION_URL}?${params.toString()}`;

    // 儲存 verifier 供後續使用
    this.saveVerifier(codeVerifier);

    return { url, verifier: codeVerifier };
  }

  /**
   * 開啟 OAuth 認證視窗
   */
  static async openAuthWindow(): Promise<{ verifier: string }> {
    const { url, verifier } = await this.buildAuthorizationURL();

    logger.debug('開啟 OAuth 認證視窗', { url });

    const popup = window.open(
      url,
      'claude-oauth',
      'width=600,height=700,scrollbars=yes,resizable=yes,menubar=no,toolbar=no,location=yes'
    );

    if (!popup) {
      throw new Error('無法開啟認證視窗，請確保瀏覽器允許彈出視窗');
    }

    // 可選：監聽視窗關閉事件
    const checkClosed = setInterval(() => {
      if (popup.closed) {
        clearInterval(checkClosed);
        logger.debug('OAuth 認證視窗已關閉');
      }
    }, 1000);

    return { verifier };
  }

  /**
   * 生成範例 OAuth URL（用於測試和文檔）
   */
  static generateExampleURL(): string {
    // 使用固定的測試參數生成範例URL，符合正確格式
    const exampleParams = new URLSearchParams({
      response_type: 'code',
      client_id: this.CLIENT_ID,
      redirect_uri: this.REDIRECT_URI,
      state: 'y63Ae3n1xd_p0EWJUSBH3VM6aoxrsv-6wY5sdyoIV8w', // 43字元，只包含允許的字元
      code_challenge_method: 'S256',
      code_challenge: 'ZVUMC_9a8RGo18nJuruEBLkGMDM733om9ohWuJ8l6JE', // 43字元的正確challenge
      scope: this.SCOPE
    });

    return `${this.AUTHORIZATION_URL}?${exampleParams.toString()}`;
  }
}