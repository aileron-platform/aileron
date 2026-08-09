import type {
  DocumentResourceItem,
  DocumentResourceScope,
  AvailableScope,
  ResourceListResult,
} from './model/documentResourceTypes';

export interface ResourceError {
  errorCode?: string;
  message: string;
  validationResults?: unknown[];
}

interface DetailShape {
  errorCode?: string;
  error?: string;
  code?: string;
  message?: string;
  validationResults?: unknown[];
  details?: unknown;
}

export function parseResourceError(err: unknown): ResourceError {
  const detail = (err as { response?: { data?: { detail?: DetailShape } } })?.response?.data?.detail;
  if (detail && typeof detail === 'object') {
    const errorCode = detail.errorCode ?? detail.error ?? detail.code;
    const message = detail.message ?? errorCode ?? 'Unknown error';
    const validationResults =
      detail.validationResults ?? (detail.details !== undefined ? [detail.details] : undefined);
    return {
      ...(errorCode ? { errorCode } : {}),
      message,
      ...(validationResults ? { validationResults } : {}),
    };
  }
  const apiError = err as { errorCode?: string; code?: string; message?: string; validationResults?: unknown[] };
  const apiErrorCode = apiError?.errorCode ?? apiError?.code;
  if (apiErrorCode || Array.isArray(apiError?.validationResults)) {
    return {
      ...(apiErrorCode ? { errorCode: apiErrorCode } : {}),
      message: apiError?.message ?? apiErrorCode ?? 'Unknown error',
      ...(Array.isArray(apiError?.validationResults) ? { validationResults: apiError.validationResults } : {}),
    };
  }
  if (err instanceof Error) {
    return { message: err.message };
  }
  return { message: 'Unknown error' };
}

export interface ResourceResult<T> {
  revision?: string;
  validationResults?: unknown[];
  resource?: T;
}

export function parseResourceResult<T>(raw: unknown): ResourceResult<T> {
  const r = (raw ?? {}) as {
    revision?: string;
    validationResults?: unknown[];
    resource?: T;
    document?: T;
  };
  const resource = r.resource ?? r.document;
  return {
    ...(r.revision !== undefined ? { revision: r.revision } : {}),
    ...(r.validationResults !== undefined ? { validationResults: r.validationResults } : {}),
    ...(resource !== undefined ? { resource } : {}),
  };
}

interface GroupedScope {
  scope: DocumentResourceScope;
  readOnly?: boolean;
  documents: DocumentResourceItem[];
}

export function toResourceList(raw: unknown): ResourceListResult {
  if (Array.isArray(raw)) {
    return { items: raw as DocumentResourceItem[], availableScopes: [] };
  }
  const flat = raw as { items?: DocumentResourceItem[]; availableScopes?: AvailableScope[] };
  if (Array.isArray(flat?.items)) {
    return {
      items: flat.items,
      availableScopes: flat.availableScopes ?? [],
    };
  }
  const grouped = (raw as { scopes?: GroupedScope[] })?.scopes ?? [];
  return {
    items: grouped.flatMap((g) => g.documents ?? []),
    availableScopes: grouped.map((g) => ({ scope: g.scope, readOnly: Boolean(g.readOnly) })),
  };
}
