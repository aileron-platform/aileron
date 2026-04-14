// === OAuth2/OIDC Authentication (Keycloak) ===

export interface OidcConfig {
  authority: string;           // Keycloak realm URL
  clientId: string;            // OAuth2 client ID
  redirectUri: string;         // Callback URL after login
  postLogoutRedirectUri: string; // Logout completed redirect URL
  responseType: string;        // OAuth2 response type (default: "code")
  scope: string;               // OAuth2 scope (default: "openid profile email")
  automaticSilentRenew: boolean; // Enable automatic token refresh
  loadUserInfo: boolean;       // Load user profile from OIDC userinfo endpoint
}

export interface OidcTokens {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  token_type: string;
  expires_in: number;
  scope?: string;
}

export interface OidcUserProfile {
  sub: string;                 // Keycloak user UUID
  email: string;
  email_verified: boolean;
  preferred_username: string;
  given_name: string;
  family_name: string;
  name: string;
}

export interface OidcAuthState {
  isAuthenticated: boolean;
  tokens: OidcTokens | null;
  userProfile: OidcUserProfile | null;
  error: string | null;
}

export interface OidcCallbackResponse {
  code: string;                // Authorization code from OAuth2 flow
  state: string;               // State parameter for CSRF protection
  session_state?: string;
}
