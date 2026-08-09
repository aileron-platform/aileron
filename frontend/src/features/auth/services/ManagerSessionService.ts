import { registerCsrfTokenProvider } from '@/shared/api/apiClient';
import { managerSessionRecovery } from '@/shared/auth/ManagerSessionRecovery';
import { AUTHORIZATION_ERROR_CODES } from '@/shared/authorization/authorizationErrorCodes';

export interface ManagerSessionUser {
  id: string;
  username: string;
  email: string | null;
  display_name: string | null;
  platform_role: 'admin' | 'member';
  allowed_operations: string[];
}

export interface ManagerSessionBootstrap {
  user: ManagerSessionUser;
  csrf_token: string;
  absolute_expires_at: string;
}

const API_BASE_PATH = '/api/v1';

type ErrorPayload = {
  errorCode?: string;
  detail?: { errorCode?: string };
};

const readErrorCode = async (response: Response): Promise<string | undefined> => {
  const payload = await response.json().catch(() => null) as ErrorPayload | null;
  return payload?.errorCode ?? payload?.detail?.errorCode;
};

class ManagerSessionService {
  private csrfToken: string | null = null;

  constructor() {
    registerCsrfTokenProvider(() => this.csrfToken);
  }

  async bootstrap(): Promise<ManagerSessionBootstrap | null> {
    const response = await fetch(`${API_BASE_PATH}/oauth2/session`, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
    if (response.status === 401) {
      const errorCode = await readErrorCode(response);
      this.clear();
      if (errorCode === 'MANAGER_SESSION_REQUIRED') {
        managerSessionRecovery.handle(
          response.status,
          errorCode,
          `${window.location.pathname}${window.location.search}${window.location.hash}`,
        );
      }
      return null;
    }
    if (response.status === 403) {
      const errorCode = await readErrorCode(response);
      if (errorCode === AUTHORIZATION_ERROR_CODES.platformAuthorizationDenied) {
        throw new Error(errorCode);
      }
    }
    if (!response.ok) {
      throw new Error('MANAGER_SESSION_BOOTSTRAP_FAILED');
    }
    const session = await response.json() as ManagerSessionBootstrap;
    if (!session.csrf_token || !session.user?.id) {
      throw new Error('MANAGER_SESSION_BOOTSTRAP_INVALID');
    }
    this.csrfToken = session.csrf_token;
    managerSessionRecovery.reset();
    return session;
  }

  login(returnPath: string): void {
    const safeReturnPath = returnPath.startsWith('/') && !returnPath.startsWith('//')
      ? returnPath
      : '/';
    window.location.assign(
      `${API_BASE_PATH}/oauth2/login?return_path=${encodeURIComponent(safeReturnPath)}`,
    );
  }

  async logout(): Promise<void> {
    const response = await fetch(`${API_BASE_PATH}/oauth2/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: this.csrfToken ? { 'X-CSRF-Token': this.csrfToken } : {},
    });
    this.clear();
    if (!response.ok && response.status !== 401) {
      throw new Error('MANAGER_SESSION_LOGOUT_FAILED');
    }
    if (response.ok) {
      const payload = await response.json() as { provider_logout_url?: string | null };
      if (payload.provider_logout_url) window.location.assign(payload.provider_logout_url);
    }
  }

  getCsrfToken(): string | null {
    return this.csrfToken;
  }

  clear(): void {
    this.csrfToken = null;
  }
}

export const managerSessionService = new ManagerSessionService();
