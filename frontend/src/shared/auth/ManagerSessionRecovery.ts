const MANAGER_SESSION_REQUIRED = 'MANAGER_SESSION_REQUIRED';
const MANAGER_LOGIN_PATH = '/api/v1/oauth2/login';
const AUTHENTICATION_PATHS = new Set([
  '/login',
  '/api/v1/oauth2/login',
  '/api/v1/oauth2/callback',
  '/api/v1/oauth2/logout',
]);

type Navigate = (url: string) => void;

const toSafeReturnPath = (returnPath: string): string => (
  returnPath.startsWith('/') && !returnPath.startsWith('//')
    ? returnPath
    : '/'
);

const returnPathname = (returnPath: string): string => returnPath.split(/[?#]/, 1)[0] ?? '/';

export class ManagerSessionRecovery {
  private redirectOwned = false;

  constructor(private readonly navigate: Navigate) {}

  handle(status: number, errorCode: string | undefined, returnPath: string): boolean {
    if (status !== 401 || errorCode !== MANAGER_SESSION_REQUIRED) {
      return false;
    }

    const safeReturnPath = toSafeReturnPath(returnPath);
    if (AUTHENTICATION_PATHS.has(returnPathname(safeReturnPath)) || this.redirectOwned) {
      return false;
    }

    this.redirectOwned = true;
    this.navigate(`${MANAGER_LOGIN_PATH}?return_path=${encodeURIComponent(safeReturnPath)}`);
    return true;
  }

  reset(): void {
    this.redirectOwned = false;
  }
}

export const managerSessionRecovery = new ManagerSessionRecovery((url) => {
  window.location.assign(url);
});
