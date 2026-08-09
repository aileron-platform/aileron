export const AUTH_ERROR_CODES = {
  serviceNotInitialized: 'AUTH_SERVICE_NOT_INITIALIZED',
  initializationFailed: 'AUTH_INITIALIZATION_FAILED',
  configurationInvalid: 'AUTH_CONFIGURATION_INVALID',
  loginFailed: 'AUTH_LOGIN_FAILED',
  registrationUnavailable: 'OIDC_REGISTRATION_UNAVAILABLE',
  registrationFailed: 'AUTH_REGISTRATION_FAILED',
  stateMissing: 'AUTH_STATE_MISSING',
  stateInvalid: 'AUTH_STATE_INVALID',
  stateExpired: 'AUTH_STATE_EXPIRED',
  tokenExchangeFailed: 'AUTH_TOKEN_EXCHANGE_FAILED',
  tokenInvalid: 'AUTH_TOKEN_INVALID',
  accessTokenMissing: 'AUTH_ACCESS_TOKEN_MISSING',
  userInfoUnavailable: 'AUTH_USERINFO_UNAVAILABLE',
  userInfoRequestFailed: 'AUTH_USERINFO_REQUEST_FAILED',
  userInfoSubjectMissing: 'AUTH_USERINFO_SUBJECT_MISSING',
  refreshFailed: 'AUTH_REFRESH_FAILED',
  refreshTokenInvalid: 'AUTH_REFRESH_TOKEN_INVALID',
  callbackFailed: 'AUTH_CALLBACK_FAILED',
} as const;

export type AuthErrorCode = typeof AUTH_ERROR_CODES[keyof typeof AUTH_ERROR_CODES];

export const toAuthErrorCode = (
  error: unknown,
  fallback: AuthErrorCode,
): AuthErrorCode => {
  const code = error instanceof Error ? error.message : '';
  return Object.values(AUTH_ERROR_CODES).includes(code as AuthErrorCode)
    ? code as AuthErrorCode
    : fallback;
};
