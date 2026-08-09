import {
  generateCodeVerifier,
  generateCodeChallenge,
} from '@/shared/utils/oauth';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('OAuthService');
const CLIENT_ID = '9d1c250a-e61b-44d9-88ed-5944d1962f5e';
const AUTHORIZATION_URL = 'https://claude.ai/oauth/authorize';
const REDIRECT_URI = 'https://console.anthropic.com/oauth/code/callback';
const SCOPE = 'org:create_api_key user:profile user:inference';
const VERIFIER_STORAGE_KEY = 'claude_oauth_verifier';

const generatePkce = async (): Promise<{ codeVerifier: string; codeChallenge: string }> => {
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);

  return {
    codeVerifier,
    codeChallenge,
  };
};

const buildAuthorizationUrl = async (): Promise<{ url: string; verifier: string }> => {
  const { codeVerifier, codeChallenge } = await generatePkce();
  const params = new URLSearchParams({
    code: 'true',
    client_id: CLIENT_ID,
    response_type: 'code',
    redirect_uri: REDIRECT_URI,
    scope: SCOPE,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
    state: codeVerifier,
  });
  const url = `${AUTHORIZATION_URL}?${params.toString()}`;

  localStorage.setItem(VERIFIER_STORAGE_KEY, codeVerifier);

  return { url, verifier: codeVerifier };
};

export const clearOAuthVerifier = (): void => {
  localStorage.removeItem(VERIFIER_STORAGE_KEY);
};

export const openOAuthWindow = async (): Promise<{ verifier: string }> => {
  const { url, verifier } = await buildAuthorizationUrl();

  logger.debug('Opening OAuth authentication window');

  const popup = window.open(
    url,
    'claude-oauth',
    'width=600,height=700,scrollbars=yes,resizable=yes,menubar=no,toolbar=no,location=yes',
  );

  if (!popup) {
    throw new Error('Unable to open authentication window. Ensure the browser allows pop-up windows.');
  }

  const checkClosed = setInterval(() => {
    if (popup.closed) {
      clearInterval(checkClosed);
      logger.debug('OAuth authentication window closed');
    }
  }, 1000);

  return { verifier };
};
