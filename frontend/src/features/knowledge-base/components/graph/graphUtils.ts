export const DEFAULT_WIKI_PATH = 'wiki/overview.md';

export const graphNodeIdFromPath = (path: string): string => (path.endsWith('.md') ? path.slice(0, -3) : path);
