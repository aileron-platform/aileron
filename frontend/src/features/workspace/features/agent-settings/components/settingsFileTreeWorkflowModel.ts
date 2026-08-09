import type {
  FileTreeContextMenuConfig,
  FileTreeNode,
} from '@/shared/components/file-workbench';
export interface SettingsFileSelection<TScope extends string = string> {
  path: string;
  scope: TScope;
  pluginId?: string;
  pluginName?: string;
  marketplaceName?: string;
}

type FileTreeContextMenuFeatures = NonNullable<FileTreeContextMenuConfig['features']>;

export const toSettingsFileSelection = <TScope extends string = string>(
  node: FileTreeNode,
  fallbackScope: TScope,
): SettingsFileSelection<TScope> => {
  const sourcePath = typeof node.metadata?.sourcePath === 'string' ? node.metadata.sourcePath : node.path;
  const sourceScope = typeof node.metadata?.sourceScope === 'string' ? node.metadata.sourceScope : node.scope;
  return {
    path: sourcePath,
    scope: ((sourceScope as TScope | null) || fallbackScope),
    pluginId: node.pluginId,
    pluginName: node.pluginName,
    marketplaceName: node.marketplaceName,
  };
};

export const buildSettingsFileTreeContextMenuFeatures = (isReadOnly: boolean): FileTreeContextMenuFeatures => ({
  view: isReadOnly,
  upload: !isReadOnly,
  createFile: !isReadOnly,
  createFolder: !isReadOnly,
  extractArchive: !isReadOnly,
  copy: false,
  copyPath: !isReadOnly,
  paste: false,
  rename: !isReadOnly,
  delete: !isReadOnly,
});
