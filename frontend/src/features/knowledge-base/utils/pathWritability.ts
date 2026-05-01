const normalizeKnowledgeBasePath = (path: string): string => path.trim().replace(/^\/+/, '').replace(/\/+$/, '');

export const isPathWritable = (path: string): boolean => {
  const normalized = normalizeKnowledgeBasePath(path);
  return normalized === 'raw' || normalized.startsWith('raw/');
};
