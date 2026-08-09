export const getTerminalTabTitle = (workingDirectory: string): string => {
  if (workingDirectory === '/') return '/';

  const segments = workingDirectory.split('/').filter(Boolean);
  return segments.at(-1) ?? '/';
};
