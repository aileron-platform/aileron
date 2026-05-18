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

export interface WorkspaceFileHref {
  filePath: string;
}

const stripLocationSuffix = (path: string): string => path.replace(LINE_COLUMN_SUFFIX_RE, '');

const stripWorkspaceRoot = (pathname: string): string | null => {
  if (pathname === WORKSPACE_ROOT_PREFIX || pathname === `${WORKSPACE_ROOT_PREFIX}/`) {
    return null;
  }
  if (!pathname.startsWith(`${WORKSPACE_ROOT_PREFIX}/`)) {
    return null;
  }
  return pathname.slice(WORKSPACE_ROOT_PREFIX.length);
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

  const sanitized = stripLocationSuffix(pathname);
  const filePath = stripWorkspaceRoot(sanitized);
  if (!filePath) {
    return null;
  }
  return { filePath };
};
