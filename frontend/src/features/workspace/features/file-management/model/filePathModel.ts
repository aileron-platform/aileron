export const ensureLeadingSlash = (path: string): string => {
  if (!path.startsWith('/')) {
    return `/${path}`;
  }
  return path;
};
