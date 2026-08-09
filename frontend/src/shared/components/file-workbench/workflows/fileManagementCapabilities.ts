export interface FileManagementCapabilities {
  canCreateFile: boolean;
  canCreateFolder: boolean;
  canUpload: boolean;
}

export const DEFAULT_FILE_MANAGEMENT_CAPABILITIES: FileManagementCapabilities = {
  canCreateFile: true,
  canCreateFolder: true,
  canUpload: true,
};

export const resolveFileManagementCapabilities = (
  capabilities?: Partial<FileManagementCapabilities>,
): FileManagementCapabilities => ({
  ...DEFAULT_FILE_MANAGEMENT_CAPABILITIES,
  ...capabilities,
});

export const isReadOnlyFileManagementCapabilities = (
  capabilities: FileManagementCapabilities,
): boolean => (
  !capabilities.canCreateFile &&
  !capabilities.canCreateFolder &&
  !capabilities.canUpload
);
