import {
  generateCodeVerifier,
  generateCodeChallenge,
} from '@/shared/utils/oauth';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('GeminiOAuthService');

const AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth';
const SCOPE = 'https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/cloud-platform openid';
const VERIFIER_STORAGE_KEY = 'gemini_oauth_verifier';

export class GeminiOAuthService {
  static getOAuthConfig(): { clientId: string; redirectUri: string } {
    const clientId = import.meta.env.VITE_GEMINI_GOOGLE_CLIENT_ID?.trim();
    const redirectUri = import.meta.env.VITE_GEMINI_GOOGLE_REDIRECT_URI?.trim()
      || 'https://codeassist.google.com/authcode';

    if (!clientId) {
      logger.error('Gemini OAuth client ID is not configured');
      throw new Error('gemini_oauth.client_not_configured');
    }

    return { clientId, redirectUri };
  }

  static saveVerifier(verifier: string): void {
    localStorage.setItem(VERIFIER_STORAGE_KEY, verifier);
  }

  static getVerifier(): string | null {
    return localStorage.getItem(VERIFIER_STORAGE_KEY);
  }

  static clearVerifier(): void {
    localStorage.removeItem(VERIFIER_STORAGE_KEY);
  }

  static async buildAuthorizationURL(): Promise<{ url: string; verifier: string }> {
    const { clientId, redirectUri } = this.getOAuthConfig();
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    const state = Array.from(crypto.getRandomValues(new Uint8Array(32)))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');

    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: 'code',
      scope: SCOPE,
      access_type: 'offline',
      prompt: 'consent',
      code_challenge: codeChallenge,
      code_challenge_method: 'S256',
      state,
    });

    this.saveVerifier(codeVerifier);
    return { url: `${AUTHORIZATION_URL}?${params.toString()}`, verifier: codeVerifier };
  }

  static async openAuthWindow(): Promise<{ verifier: string }> {
    const { url, verifier } = await this.buildAuthorizationURL();
    logger.debug('Opening Gemini OAuth window');

    const popup = window.open(
      url,
      'gemini-oauth',
      'width=600,height=700,scrollbars=yes,resizable=yes,menubar=no,toolbar=no,location=yes',
    );
    if (!popup) {
      throw new Error('gemini_oauth.popup_blocked');
    }

    const checkClosed = setInterval(() => {
      if (popup.closed) {
        clearInterval(checkClosed);
        logger.debug('Gemini OAuth window closed');
      }
    }, 1000);

    return { verifier };
  }
}
