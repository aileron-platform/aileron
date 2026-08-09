import type { FileTreeNode } from '@/shared/components/file-workbench';
import type { FileViewerWorkbenchAdapter } from '@/shared/components/file-workbench/viewer-entry';

const getStringField = (value: unknown, fallback = ''): string => (
  typeof value === 'string' && value.trim() ? value : fallback
);

const marketplaceBlobFromContent = (
  content: string,
  mimeType: string,
  binary: boolean,
): Blob => {
  if (!binary) {
    return new Blob([content], { type: mimeType });
  }

  const byteCharacters = atob(content);
  const byteNumbers = Array.from(byteCharacters, character => character.charCodeAt(0));
  return new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
};

interface CreateReadonlyMarketplaceViewerAdapterOptions {
  getNode: (path: string) => FileTreeNode | undefined;
  getContent: (path: string) => string;
}

export const createReadonlyMarketplaceViewerAdapter = ({
  getNode,
  getContent,
}: CreateReadonlyMarketplaceViewerAdapterOptions): FileViewerWorkbenchAdapter => ({
  readFile: async (path) => getContent(path),
  readBlob: async (path) => {
    const node = getNode(path);
    const mimeType = getStringField(node?.metadata?.mimeType, 'application/octet-stream');
    return marketplaceBlobFromContent(getContent(path), mimeType, node?.metadata?.binary === true);
  },
  copyPath: async (path) => {
    await navigator.clipboard.writeText(path);
  },
});
