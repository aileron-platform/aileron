export const WORKSPACE_FILE_REFERENCE_MIME = 'application/x-aileron-workspace-file-reference';

export const toWorkspaceFileReferencePath = (path: string): string => {
  const trimmedPath = path.trim();
  if (!trimmedPath) {
    return '';
  }
  if (trimmedPath.startsWith('./') || trimmedPath.startsWith('../')) {
    return trimmedPath;
  }
  if (trimmedPath.startsWith('/')) {
    return `.${trimmedPath}`;
  }
  return `./${trimmedPath}`;
};
