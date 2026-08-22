/**
 */

import { createLogger } from '../services/logger';
import { isRecord } from '../utils/typeGuards';
import { managerSessionRecovery } from '../auth/ManagerSessionRecovery';

const logger = createLogger('API Client');

export type ApiClientUnauthorizedBehavior = 'expire' | 'propagate';

interface ApiClientOptions {
  baseUrl?: string;
  headers?: Record<string, string>;
  unauthorizedBehavior?: ApiClientUnauthorizedBehavior;
  executionAudience?: 'workspace-runtime';
}

type ApiRequestHeaders = Record<string, string>;

interface ApiRequestOptions {
  headers?: ApiRequestHeaders;
  signal?: AbortSignal;
}

interface ApiRequestHeaderOptions {
  headers?: ApiRequestHeaders;
  omitContentType?: boolean;
}

type CsrfTokenProvider = () => string | null;
type ExecutionGrantProvider = (request: {
  targetUrl: string;
  method: string;
  path: string;
}) => Promise<string>;
type ExecutionGrantRejectionHandler = (rejection: {
  targetUrl: string;
  errorCode: string;
}) => boolean;
type LanguageProvider = () => string | null;
export interface ApiErrorEvent {
  status: number;
  errorCode?: string;
  responseUrl: string;
}
type ApiErrorListener = (event: ApiErrorEvent) => void;

let csrfTokenProvider: CsrfTokenProvider | null = null;
let executionGrantProvider: ExecutionGrantProvider | null = null;
let executionGrantRejectionHandler: ExecutionGrantRejectionHandler | null = null;
let languageProvider: LanguageProvider | null = null;
const apiErrorListeners = new Set<ApiErrorListener>();

const normalizeBaseUrl = (value?: string): string => {
  if (!value) {
    return '/api/v1';
  }

  return value.endsWith('/') ? value.slice(0, -1) : value;
};

const normalizeRequestOptions = (
  headersOrOptions?: ApiRequestHeaders | ApiRequestOptions,
): ApiRequestOptions => {
  if (!headersOrOptions) {
    return {};
  }
  if ('headers' in headersOrOptions || 'signal' in headersOrOptions) {
    return headersOrOptions as ApiRequestOptions;
  }
  return { headers: headersOrOptions as ApiRequestHeaders };
};

export const registerCsrfTokenProvider = (provider: CsrfTokenProvider | null) => {
  csrfTokenProvider = provider;
};

export const registerExecutionGrantProvider = (provider: ExecutionGrantProvider | null) => {
  executionGrantProvider = provider;
};

export const registerExecutionGrantRejectionHandler = (
  handler: ExecutionGrantRejectionHandler | null,
) => {
  executionGrantRejectionHandler = handler;
};

export const registerLanguageProvider = (provider: LanguageProvider | null) => {
  languageProvider = provider;
};

export const subscribeApiError = (listener: ApiErrorListener): (() => void) => {
  apiErrorListeners.add(listener);
  return () => {
    apiErrorListeners.delete(listener);
  };
};

const notifyApiError = (event: ApiErrorEvent): void => {
  for (const listener of apiErrorListeners) {
    try {
      listener(event);
    } catch (error) {
      logger.warn('API error listener failed', { error });
    }
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

const normalizeErrorMessage = (value: unknown, fallback: string): string => {
  if (typeof value === 'string' && value.trim()) return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (isRecord(value)) {
    for (const key of ['message', 'error', 'detail', 'code', 'errorCode', 'error_code']) {
      const nested = value[key];
      if (typeof nested === 'string' && nested.trim()) return nested;
    }
  }
  return fallback;
};

const getStringField = (value: unknown, key: string): string | undefined =>
  isRecord(value) && typeof value[key] === 'string' ? value[key] : undefined;

const getCurrentReturnPath = (): string => (
  `${window.location.pathname}${window.location.search}${window.location.hash}`
);

export type ApiErrorBlockingScope = 'working_tree_target' | 'common_repository';

export interface ApiErrorOperationStatus {
  isActive: boolean;
  operation: string | null;
  actorDisplayName: string | null;
  startedAt: string | null;
  blockingScope: ApiErrorBlockingScope | null;
  stale: boolean;
  retryable: boolean;
  progressCurrent: number | null;
  progressTotal: number | null;
  phase: string | null;
  cancellable: boolean;
  cancelRequested: boolean;
}

interface ApiErrorMetadata {
  messageKey?: string;
  blockingScope?: ApiErrorBlockingScope;
  operationStatus?: ApiErrorOperationStatus;
  stale?: boolean;
  canForceUnlock?: boolean;
}

const isApiErrorBlockingScope = (value: unknown): value is ApiErrorBlockingScope => (
  value === 'working_tree_target' || value === 'common_repository'
);

const parseNullableString = (value: unknown): string | null | undefined => {
  if (value === null) return null;
  return typeof value === 'string' ? value : undefined;
};

const parseNullableNumber = (value: unknown): number | null | undefined => {
  if (value === null) return null;
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
};

const parseOperationStatus = (value: unknown): ApiErrorOperationStatus | undefined => {
  if (!isRecord(value)) return undefined;

  const operation = parseNullableString(value.operation);
  const actorDisplayName = parseNullableString(value.actorDisplayName);
  const startedAt = parseNullableString(value.startedAt);
  const blockingScope = value.blockingScope === null
    ? null
    : isApiErrorBlockingScope(value.blockingScope)
      ? value.blockingScope
      : undefined;
  const progressCurrent = parseNullableNumber(value.progressCurrent);
  const progressTotal = parseNullableNumber(value.progressTotal);
  const phase = parseNullableString(value.phase);

  if (
    typeof value.isActive !== 'boolean'
    || operation === undefined
    || actorDisplayName === undefined
    || startedAt === undefined
    || blockingScope === undefined
    || typeof value.stale !== 'boolean'
    || typeof value.retryable !== 'boolean'
    || progressCurrent === undefined
    || progressTotal === undefined
    || phase === undefined
    || typeof value.cancellable !== 'boolean'
    || typeof value.cancelRequested !== 'boolean'
  ) {
    return undefined;
  }

  return {
    isActive: value.isActive,
    operation,
    actorDisplayName,
    startedAt,
    blockingScope,
    stale: value.stale,
    retryable: value.retryable,
    progressCurrent,
    progressTotal,
    phase,
    cancellable: value.cancellable,
    cancelRequested: value.cancelRequested,
  };
};

const parseErrorMetadata = (value: Record<string, unknown>): ApiErrorMetadata | undefined => {
  const messageKey = getStringField(value, 'messageKey');
  if (!messageKey) return undefined;

  const blockingScopeValue = getStringField(value, 'blockingScope');
  return {
    messageKey,
    blockingScope: isApiErrorBlockingScope(blockingScopeValue)
      ? blockingScopeValue
      : undefined,
    operationStatus: parseOperationStatus(value.operationStatus),
    stale: typeof value.stale === 'boolean' ? value.stale : undefined,
    canForceUnlock: typeof value.canForceUnlock === 'boolean'
      ? value.canForceUnlock
      : undefined,
  };
};

const extractErrorMessage = (errorData: unknown, status: number): {
  message: string;
  code?: string;
  reason?: string;
  validationResults?: unknown[];
  metadata?: ApiErrorMetadata;
} => {
  const errorRecord = isRecord(errorData) ? errorData : {};
  const detail = errorRecord.detail;
  const errorCode = getStringField(errorRecord, 'error_code') ?? getStringField(errorRecord, 'errorCode');

  const metadata = parseErrorMetadata(errorRecord);
  if (errorCode && metadata?.messageKey) {
    return {
      message: `HTTP ${status}`,
      code: errorCode,
      metadata,
    };
  }

  if (Array.isArray(detail)) {
    const firstIssue = detail[0];
    if (isRecord(firstIssue) && firstIssue.msg) {
      return {
        message: `${formatValidationPath(firstIssue.loc)}: ${firstIssue.msg}`,
        code: errorCode,
      };
    }
    return {
      message: `HTTP ${status}`,
      code: errorCode,
    };
  }

  if (isRecord(detail)) {
    const code = getStringField(detail, 'errorCode')
      ?? getStringField(detail, 'error_code')
      ?? getStringField(detail, 'code')
      ?? getStringField(detail, 'error');
    const validationResults = Array.isArray(detail.validationResults)
      ? detail.validationResults
      : undefined;
    return {
      message: normalizeErrorMessage(detail.message ?? detail.error ?? code, code ?? `HTTP ${status}`),
      code,
      reason: getStringField(detail, 'reason'),
      validationResults,
      metadata: parseErrorMetadata(detail),
    };
  }

  return {
    message: normalizeErrorMessage(detail ?? errorRecord.message, `HTTP ${status}`),
    code: errorCode,
  };
};

/**
 *
 */
class ApiError extends Error {
  readonly status: number;
  readonly errorCode?: string;
  readonly reason?: string;
  readonly validationResults?: unknown[];
  readonly responseData?: unknown;
  readonly messageKey?: string;
  readonly blockingScope?: ApiErrorBlockingScope;
  readonly operationStatus?: ApiErrorOperationStatus;
  readonly stale?: boolean;
  readonly canForceUnlock?: boolean;

  constructor(
    message: string,
    status: number,
    errorCode?: string,
    reason?: string,
    validationResults?: unknown[],
    responseData?: unknown,
    metadata?: ApiErrorMetadata,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorCode = errorCode;
    this.reason = reason;
    this.validationResults = validationResults;
    this.responseData = responseData;
    this.messageKey = metadata?.messageKey;
    this.blockingScope = metadata?.blockingScope;
    this.operationStatus = metadata?.operationStatus;
    this.stale = metadata?.stale;
    this.canForceUnlock = metadata?.canForceUnlock;
  }
}

class ApiClient {
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;
  private unauthorizedBehavior: ApiClientUnauthorizedBehavior;
  private executionAudience?: 'workspace-runtime';

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    this.unauthorizedBehavior = options.unauthorizedBehavior ?? 'expire';
    this.executionAudience = options.executionAudience;
  }

  private async buildHeaders(
    additionalHeaders?: Record<string, string>,
    method = 'GET',
    path = '/',
  ): Promise<Record<string, string>> {
    const headers = { ...this.defaultHeaders, ...additionalHeaders };
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfTokenProvider) {
      const csrfToken = csrfTokenProvider();
      if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
    }
    if (this.executionAudience) {
      if (!executionGrantProvider) throw new Error('EXECUTION_GRANT_PROVIDER_MISSING');
      headers.Authorization = `Bearer ${await executionGrantProvider({
        targetUrl: this.baseUrl,
        method,
        path,
      })}`;
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

  async getRequestHeaders(
    options: ApiRequestHeaderOptions & { method?: string; path?: string } = {},
  ): Promise<Record<string, string>> {
    const headers = await this.buildHeaders(
      options.headers,
      options.method ?? 'GET',
      options.path ?? '/',
    );
    if (options.omitContentType) {
      delete headers['Content-Type'];
    }
    return headers;
  }

  buildUrl(path: string): string {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.baseUrl}${normalizedPath}`;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorMessage: string;
      let errorCode: string | undefined;
      let errorReason: string | undefined;
      let validationResults: unknown[] | undefined;
      let errorMetadata: ApiErrorMetadata | undefined;
      let responseData: unknown;

      try {
        const errorData = await response.json();
        responseData = errorData;
        const extracted = extractErrorMessage(errorData, response.status);
        errorMessage = extracted.message;
        errorCode = extracted.code;
        errorReason = extracted.reason;
        validationResults = extracted.validationResults;
        errorMetadata = extracted.metadata;
      } catch {
        errorMessage = response.statusText || `HTTP ${response.status}`;
      }

      if (
        response.status === 401
        && errorCode === 'MANAGER_SESSION_REQUIRED'
        && this.unauthorizedBehavior === 'expire'
      ) {
        managerSessionRecovery.handle(response.status, errorCode, getCurrentReturnPath());
      }

      if (response.status === 401) {
        logger.info('401 response received', { errorCode });
      }

      const apiError = new ApiError(
        errorMessage,
        response.status,
        errorCode,
        errorReason,
        validationResults,
        responseData,
        errorMetadata,
      );
      notifyApiError({
        status: apiError.status,
        errorCode: apiError.errorCode,
        responseUrl: response.url,
      });
      throw apiError;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  }

  private shouldRetryExecutionGrant(error: unknown): boolean {
    const errorCode = error instanceof ApiError ? error.errorCode : undefined;
    const isGenerationMismatch = errorCode === 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH'
      || errorCode === 'WORKSPACE_RUNTIME_ACCESS_REVISION_MISMATCH';
    return Boolean(
      this.executionAudience
      && errorCode
      && isGenerationMismatch
      && executionGrantRejectionHandler?.({ targetUrl: this.baseUrl, errorCode }),
    );
  }

  private async executeRequestWithGrantRecovery<T>(
    makeRequest: () => Promise<Response>,
    readResponse: (response: Response) => Promise<T>,
  ): Promise<T> {
    try {
      return await readResponse(await makeRequest());
    } catch (error) {
      if (!this.shouldRetryExecutionGrant(error)) {
        throw error;
      }
      return readResponse(await makeRequest());
    }
  }

  private executeJsonRequest<T>(makeRequest: () => Promise<Response>): Promise<T> {
    return this.executeRequestWithGrantRecovery(
      makeRequest,
      response => this.handleResponse<T>(response),
    );
  }

  async get<T>(path: string, headersOrOptions?: ApiRequestHeaders | ApiRequestOptions): Promise<T> {
    const options = normalizeRequestOptions(headersOrOptions);
    const makeRequest = async () => fetch(this.buildUrl(path), {
      method: 'GET',
      headers: await this.buildHeaders(options.headers, 'GET', path),
      credentials: 'include',
      signal: options.signal,
    });

    return this.executeJsonRequest<T>(makeRequest);
  }

  async post<T>(
    path: string,
    data?: unknown,
    headersOrOptions?: ApiRequestHeaders | ApiRequestOptions,
  ): Promise<T> {
    const options = normalizeRequestOptions(headersOrOptions);
    const isFormData = data instanceof FormData;

    const makeRequest = async () => {
      const requestHeaders = isFormData
        ? await this.buildHeaders({ ...options.headers }, 'POST', path)
        : await this.buildHeaders(options.headers, 'POST', path);

      if (isFormData) {
        delete requestHeaders['Content-Type'];
      }

      return fetch(this.buildUrl(path), {
        method: 'POST',
        headers: requestHeaders,
        body: isFormData ? data : (data ? JSON.stringify(data) : undefined),
        signal: options.signal,
        credentials: 'include',
      });
    };

    return this.executeJsonRequest<T>(makeRequest);
  }

  async put<T>(path: string, data?: unknown, headers?: Record<string, string>): Promise<T> {
    const isFormData = data instanceof FormData;

    const makeRequest = async () => {
      const requestHeaders = isFormData
        ? await this.buildHeaders({ ...headers }, 'PUT', path)
        : await this.buildHeaders(headers, 'PUT', path);

      if (isFormData) {
        delete requestHeaders['Content-Type'];
      }

      return fetch(this.buildUrl(path), {
        method: 'PUT',
        headers: requestHeaders,
        body: isFormData ? data : (data ? JSON.stringify(data) : undefined),
        credentials: 'include',
      });
    };

    return this.executeJsonRequest<T>(makeRequest);
  }

  async patch<T>(path: string, data?: unknown, headers?: Record<string, string>): Promise<T> {
    const isFormData = data instanceof FormData;

    const makeRequest = async () => {
      const requestHeaders = isFormData
        ? await this.buildHeaders({ ...headers }, 'PATCH', path)
        : await this.buildHeaders(headers, 'PATCH', path);

      if (isFormData) {
        delete requestHeaders['Content-Type'];
      }

      return fetch(this.buildUrl(path), {
        method: 'PATCH',
        headers: requestHeaders,
        body: isFormData ? data : (data ? JSON.stringify(data) : undefined),
        credentials: 'include',
      });
    };

    return this.executeJsonRequest<T>(makeRequest);
  }

  async delete<T>(path: string, headers?: Record<string, string>, data?: unknown): Promise<T> {
    const makeRequest = async () => fetch(this.buildUrl(path), {
      method: 'DELETE',
      headers: await this.buildHeaders(headers, 'DELETE', path),
      body: data ? JSON.stringify(data) : undefined,
      credentials: 'include',
    });

    return this.executeJsonRequest<T>(makeRequest);
  }

  /**
   * @returns Promise<Blob>
   */
  async getBlob(path: string, headers?: Record<string, string>): Promise<Blob> {
    const requestHeaders: Record<string, string> = { ...headers };
    delete requestHeaders['Content-Type'];

    const makeRequest = async () => fetch(this.buildUrl(path), {
      method: 'GET',
      headers: await this.buildHeaders(requestHeaders, 'GET', path),
      credentials: 'include',
    });

    return this.executeRequestWithGrantRecovery(makeRequest, async (response) => {
      if (!response.ok) {
        await this.handleResponse<never>(response);
      }
      return response.blob();
    });
  }
}

export const apiClient = new ApiClient();

export { ApiClient, ApiError };
export type { ApiClientOptions };
