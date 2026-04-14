/**
 * 統一的 API 客戶端
 * 自動處理認證標頭、錯誤處理和 Token 刷新
 */

import { createLogger } from '../services/logger';

const logger = createLogger('API Client');

interface ApiClientOptions {
  baseUrl?: string;
  headers?: Record<string, string>;
}

type AuthTokenProvider = () => string | null;
type TokenRefreshHandler = () => Promise<void>;
type LanguageProvider = () => string | null;

let tokenProvider: AuthTokenProvider | null = null;
let tokenRefreshHandler: TokenRefreshHandler | null = null;
let sessionExpiredHandler: (() => void) | null = null;
let languageProvider: LanguageProvider | null = null;

const normalizeBaseUrl = (value?: string): string => {
  if (!value) {
    return '/api/v1';
  }

  return value.endsWith('/') ? value.slice(0, -1) : value;
};

export const registerAuthTokenProvider = (provider: AuthTokenProvider | null) => {
  tokenProvider = provider;
};

export const registerTokenRefreshHandler = (handler: TokenRefreshHandler | null) => {
  tokenRefreshHandler = handler;
};

export const registerSessionExpiredHandler = (handler: (() => void) | null) => {
  sessionExpiredHandler = handler;
};

export const registerLanguageProvider = (provider: LanguageProvider | null) => {
  languageProvider = provider;
};

const handleSessionExpired = () => {
  if (sessionExpiredHandler) {
    sessionExpiredHandler();
  } else {
    // Fallback: 清除 OIDC session 並硬跳轉
    try {
      sessionStorage.removeItem('oidc_tokens');
      sessionStorage.removeItem('oidc_user_profile');
      sessionStorage.removeItem('oidc_state');
    } catch { /* ignore */ }
    window.location.href = '/login';
  }
};

const formatValidationPath = (loc: unknown): string => {
  if (!Array.isArray(loc)) return 'request';
  const path = loc
    .filter((part) => part !== 'body')
    .map((part) => String(part))
    .join('.');
  return path || 'request';
};

const extractErrorMessage = (errorData: any, status: number): { message: string; code?: string } => {
  if (Array.isArray(errorData?.detail)) {
    const firstIssue = errorData.detail[0];
    if (firstIssue?.msg) {
      return {
        message: `${formatValidationPath(firstIssue.loc)}: ${firstIssue.msg}`,
        code: errorData.error_code ?? errorData.errorCode,
      };
    }
    return {
      message: `HTTP ${status}`,
      code: errorData.error_code ?? errorData.errorCode,
    };
  }

  if (typeof errorData?.detail === 'object' && errorData.detail !== null) {
    return {
      message: errorData.detail.message || errorData.detail.error || `HTTP ${status}`,
      code: errorData.detail.errorCode ?? errorData.detail.error_code ?? errorData.detail.code,
    };
  }

  return {
    message: errorData?.detail || errorData?.message || `HTTP ${status}`,
    code: errorData?.error_code ?? errorData?.errorCode,
  };
};

/**
 * API 錯誤類別
 *
 * 保留後端回傳的 error code 與 HTTP status，方便前端依錯誤代碼顯示對應翻譯訊息。
 * 仍繼承自 Error，因此既有以 `error.message` 取用的程式碼不受影響。
 */
class ApiError extends Error {
  readonly status: number;
  readonly errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorCode = errorCode;
  }
}

class ApiClient {
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;
  private isRefreshing = false;
  private refreshPromise: Promise<void> | null = null;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
  }

  private getAuthToken(): string | null {
    // 首先嘗試從 token provider 獲取（優先使用最新的 state）
    if (tokenProvider) {
      try {
        const providedToken = tokenProvider();
        if (providedToken) {
          logger.debug('Token retrieved from provider');
          return providedToken;
        }
      } catch (error) {
        logger.warn('Auth token provider failed', { error });
      }
    }

    if (typeof window === 'undefined') {
      return null;
    }

    // 作為備用，直接從 sessionStorage 讀取 OIDC tokens
    try {
      const stored = window.sessionStorage.getItem('oidc_tokens');
      if (!stored) {
        return null;
      }

      const parsed = JSON.parse(stored) as { access_token?: string };
      const token = parsed.access_token || null;
      if (token) {
        logger.debug('Token retrieved from sessionStorage');
      }
      return token;
    } catch (error) {
      logger.warn('Failed to get auth token from sessionStorage', { error });
      return null;
    }
  }

  private buildHeaders(additionalHeaders?: Record<string, string>): Record<string, string> {
    const headers = { ...this.defaultHeaders, ...additionalHeaders };

    const token = this.getAuthToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    if (!headers['X-Language'] && languageProvider) {
      try {
        const language = languageProvider();
        if (language) {
          headers['X-Language'] = language;
        }
      } catch (error) {
        logger.warn('Language provider failed', { error });
      }
    }

    return headers;
  }

  private buildUrl(path: string): string {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.baseUrl}${normalizedPath}`;
  }

  private async handleResponse<T>(response: Response, retryRequest?: () => Promise<Response>): Promise<T> {
    // 處理 401 未授權錯誤 - 嘗試刷新 token 並重試
    if (response.status === 401 && retryRequest && tokenRefreshHandler) {
      logger.info('Received 401, attempting token refresh...');

      try {
        // 如果已經在刷新中，等待刷新完成
        if (this.isRefreshing && this.refreshPromise) {
          await this.refreshPromise;
        } else {
          // 開始刷新 token
          this.isRefreshing = true;
          this.refreshPromise = tokenRefreshHandler();
          await this.refreshPromise;
          this.isRefreshing = false;
          this.refreshPromise = null;
        }

        // Token 刷新成功，重試原始請求
        logger.info('Token refreshed, retrying request...');

        const retryResponse = await retryRequest();

        // 遞迴處理重試的回應（但不再重試，避免無限循環）
        return this.handleResponse<T>(retryResponse);
      } catch (refreshError) {
        logger.error('Token refresh failed', { error: refreshError });
        this.isRefreshing = false;
        this.refreshPromise = null;

        // Token 刷新失敗，導向登入頁
        handleSessionExpired();
        throw new Error('認證已過期，請重新登入');
      }
    }

    // 處理其他錯誤
    if (!response.ok) {
      let errorMessage: string;
      let errorCode: string | undefined;

      try {
        const errorData = await response.json();
        const extracted = extractErrorMessage(errorData, response.status);
        errorMessage = extracted.message;
        errorCode = extracted.code;
      } catch {
        errorMessage = response.statusText || `HTTP ${response.status}`;
      }

      // 為 401 錯誤提供更友善的訊息
      if (response.status === 401) {
        if (errorCode === 'TOKEN_EXPIRED') {
          errorMessage = 'Token 已過期，正在嘗試刷新...';
        } else if (errorCode === 'MISSING_AUTH_HEADER') {
          errorMessage = '缺少認證資訊，請重新登入';
        } else {
          errorMessage = '認證失敗，請重新登入';
        }
        logger.info(`401 Error: ${errorMessage}`, { errorCode });
      }

      throw new ApiError(errorMessage, response.status, errorCode);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  }

  async get<T>(path: string, headers?: Record<string, string>): Promise<T> {
    const makeRequest = () => fetch(this.buildUrl(path), {
      method: 'GET',
      headers: this.buildHeaders(headers),
    });

    const response = await makeRequest();
    return this.handleResponse<T>(response, makeRequest);
  }

  async post<T>(path: string, data?: any, headers?: Record<string, string>): Promise<T> {
    // 如果 data 是 FormData，不要設置 Content-Type，讓瀏覽器自動設置
    const isFormData = data instanceof FormData;

    const makeRequest = () => {
      const requestHeaders = isFormData
        ? this.buildHeaders({ ...headers })
        : this.buildHeaders(headers);

      if (isFormData) {
        delete requestHeaders['Content-Type']; // 讓瀏覽器自動設置正確的 boundary
      }

      return fetch(this.buildUrl(path), {
        method: 'POST',
        headers: requestHeaders,
        body: isFormData ? data : (data ? JSON.stringify(data) : undefined),
      });
    };

    const response = await makeRequest();
    return this.handleResponse<T>(response, makeRequest);
  }

  async put<T>(path: string, data?: any, headers?: Record<string, string>): Promise<T> {
    // 如果 data 是 FormData，不要設置 Content-Type，讓瀏覽器自動設置
    const isFormData = data instanceof FormData;

    const makeRequest = () => {
      const requestHeaders = isFormData
        ? this.buildHeaders({ ...headers })
        : this.buildHeaders(headers);

      if (isFormData) {
        delete requestHeaders['Content-Type']; // 讓瀏覽器自動設置正確的 boundary
      }

      return fetch(this.buildUrl(path), {
        method: 'PUT',
        headers: requestHeaders,
        body: isFormData ? data : (data ? JSON.stringify(data) : undefined),
      });
    };

    const response = await makeRequest();
    return this.handleResponse<T>(response, makeRequest);
  }

  async patch<T>(path: string, data?: any, headers?: Record<string, string>): Promise<T> {
    // 如果 data 是 FormData，不要設置 Content-Type，讓瀏覽器自動設置
    const isFormData = data instanceof FormData;

    const makeRequest = () => {
      const requestHeaders = isFormData
        ? this.buildHeaders({ ...headers })
        : this.buildHeaders(headers);

      if (isFormData) {
        delete requestHeaders['Content-Type']; // 讓瀏覽器自動設置正確的 boundary
      }

      return fetch(this.buildUrl(path), {
        method: 'PATCH',
        headers: requestHeaders,
        body: isFormData ? data : (data ? JSON.stringify(data) : undefined),
      });
    };

    const response = await makeRequest();
    return this.handleResponse<T>(response, makeRequest);
  }

  async delete<T>(path: string, headers?: Record<string, string>): Promise<T> {
    const makeRequest = () => fetch(this.buildUrl(path), {
      method: 'DELETE',
      headers: this.buildHeaders(headers),
    });

    const response = await makeRequest();
    return this.handleResponse<T>(response, makeRequest);
  }

  /**
   * 獲取二進位資料（如圖片、檔案等）
   * @param path API 路徑
   * @param headers 額外的標頭
   * @returns Promise<Blob>
   */
  async getBlob(path: string, headers?: Record<string, string>): Promise<Blob> {
    // 移除 Content-Type，因為我們要接收二進位資料
    const requestHeaders: Record<string, string> = { ...headers };
    delete requestHeaders['Content-Type'];

    const makeRequest = () => fetch(this.buildUrl(path), {
      method: 'GET',
      headers: this.buildHeaders(requestHeaders),
    });

    const response = await makeRequest();

    // 處理 401 未授權錯誤 - 嘗試刷新 token 並重試
    if (response.status === 401 && tokenRefreshHandler) {
      try {
        if (this.isRefreshing && this.refreshPromise) {
          await this.refreshPromise;
        } else {
          this.isRefreshing = true;
          this.refreshPromise = tokenRefreshHandler();
          await this.refreshPromise;
          this.isRefreshing = false;
          this.refreshPromise = null;
        }

        const retryResponse = await makeRequest();
        if (!retryResponse.ok) {
          throw new Error('認證失敗，請重新登入');
        }
        return retryResponse.blob();
      } catch (refreshError) {
        logger.error('Token refresh failed', { error: refreshError });
        this.isRefreshing = false;
        this.refreshPromise = null;
        handleSessionExpired();
        throw new Error('認證已過期，請重新登入');
      }
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.blob();
  }
}

// 預設的 API 客戶端實例
export const apiClient = new ApiClient({
  baseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
});

// 允許創建自定義實例
export { ApiClient, ApiError };
export type { ApiClientOptions, AuthTokenProvider, TokenRefreshHandler };
