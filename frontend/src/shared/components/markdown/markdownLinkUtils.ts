export type MarkdownLinkKind = 'internal' | 'external' | 'anchor';

const EXTERNAL_PROTOCOL_RE = /^[a-zA-Z][a-zA-Z\d+\-.]*:/;

const stripHashAndQuery = (href: string): string => {
  const hashIndex = href.indexOf('#');
  const queryIndex = href.indexOf('?');
  const cutIndex = [hashIndex, queryIndex]
    .filter((index) => index >= 0)
    .sort((a, b) => a - b)[0];

  return cutIndex === undefined ? href : href.slice(0, cutIndex);
};

const getParentPath = (filePath: string): string => {
  const normalized = filePath.startsWith('/') ? filePath : `/${filePath}`;
  const segments = normalized.split('/').filter(Boolean);
  segments.pop();
  return `/${segments.join('/')}`;
};

export const classifyMarkdownHref = (href?: string | null): MarkdownLinkKind => {
  if (!href || href.startsWith('#')) {
    return 'anchor';
  }

  if (EXTERNAL_PROTOCOL_RE.test(href)) {
    return 'external';
  }

  return 'internal';
};

export const resolveWorkspaceMarkdownPath = (
  currentFilePath: string,
  href: string,
): string | null => {
  const sanitizedHref = stripHashAndQuery(href).trim();
  if (!sanitizedHref) {
    return null;
  }

  const baseSegments = sanitizedHref.startsWith('/')
    ? []
    : getParentPath(currentFilePath)
        .split('/')
        .filter(Boolean);

  const targetSegments = sanitizedHref.split('/').filter(Boolean);
  const resolvedSegments = [...baseSegments];

  for (const segment of targetSegments) {
    if (segment === '.') {
      continue;
    }

    if (segment === '..') {
      if (resolvedSegments.length > 0) {
        resolvedSegments.pop();
      }
      continue;
    }

    resolvedSegments.push(segment);
  }

  return `/${resolvedSegments.join('/')}`;
};

const WORKSPACE_ROOT_PREFIX = '/workspace';
const LINE_COLUMN_SUFFIX_RE = /:\d+(?::\d+)?$/;
const MAX_WORKSPACE_FILE_PATH_LENGTH = 4096;
const ENCODED_PATH_BOUNDARY_RE = /%(?:2e|2f|5c)/i;

export interface WorkspaceFileHref {
  filePath: string;
}

const stripLocationSuffix = (path: string): string => path.replace(LINE_COLUMN_SUFFIX_RE, '');

const normalizeWorkspaceFilePath = (path: string): string | null => {
  const normalized = path.trim().normalize('NFC');
  if (!normalized) return null;
  if (normalized.includes('\u0000') || normalized.includes('\\')) return null;

  const withLeadingSlash = normalized.startsWith('/') ? normalized : `/${normalized}`;
  if (withLeadingSlash.length > MAX_WORKSPACE_FILE_PATH_LENGTH) return null;
  if (ENCODED_PATH_BOUNDARY_RE.test(withLeadingSlash)) return null;

  const segments = withLeadingSlash.split('/').filter(Boolean);
  if (segments.some((segment) => segment === '.' || segment === '..')) {
    return null;
  }

  return withLeadingSlash;
};

const stripWorkspaceRoot = (pathname: string): string | null => {
  if (pathname === WORKSPACE_ROOT_PREFIX || pathname === `${WORKSPACE_ROOT_PREFIX}/`) {
    return null;
  }
  if (!pathname.startsWith(`${WORKSPACE_ROOT_PREFIX}/`)) {
    return null;
  }
  return pathname.slice(WORKSPACE_ROOT_PREFIX.length);
};

const parseWorkspacePathname = (pathname: string): WorkspaceFileHref | null => {
  const sanitized = stripLocationSuffix(pathname);
  const filePath = stripWorkspaceRoot(sanitized);
  const normalized = filePath ? normalizeWorkspaceFilePath(filePath) : null;
  return normalized ? { filePath: normalized } : null;
};

const decodeRawWorkspaceHrefPathname = (pathname: string): string | null => {
  if (/%2f/i.test(pathname)) return null;
  try {
    return decodeURIComponent(pathname);
  } catch {
    return null;
  }
};

export const parseWorkspaceFileHref = (
  href: string | null | undefined,
  currentOrigin: string,
): WorkspaceFileHref | null => {
  if (!href) {
    return null;
  }

  let pathname: string;
  if (EXTERNAL_PROTOCOL_RE.test(href)) {
    let parsed: URL;
    try {
      parsed = new URL(href);
    } catch {
      return null;
    }
    if (parsed.origin !== currentOrigin) {
      return null;
    }
    pathname = parsed.pathname;
  } else if (href.startsWith('/')) {
    pathname = stripHashAndQuery(href);
  } else {
    return null;
  }

  const decodedPathname = decodeRawWorkspaceHrefPathname(pathname);
  return decodedPathname ? parseWorkspacePathname(decodedPathname) : null;
};

export const parseWorkspaceLocationPathname = (
  pathname: string | null | undefined,
): WorkspaceFileHref | null => {
  if (!pathname) return null;
  const decodedPathname = decodeRawWorkspaceHrefPathname(pathname);
  return decodedPathname ? parseWorkspacePathname(decodedPathname) : null;
};

export const parseWorkspaceOpenPath = (
  path: string | null | undefined,
): WorkspaceFileHref | null => {
  if (!path) return null;
  const normalized = normalizeWorkspaceFilePath(stripLocationSuffix(path));
  return normalized ? { filePath: normalized } : null;
};

export const encodeWorkspaceOpenPath = (filePath: string): string => encodeURIComponent(filePath);
