import { getParentPath } from './fileOperationUtils';

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
