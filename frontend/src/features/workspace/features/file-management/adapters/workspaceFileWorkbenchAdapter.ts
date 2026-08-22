import { ApiClient } from '@/shared/api/apiClient';
import type { FileViewerWorkbenchAdapter } from '@/shared/components/file-workbench/viewer-entry';

export interface WorkspaceFileWorkbenchAdapterOptions {
  runtimeBaseUrl?: string;
  readFile: (path: string) => Promise<string>;
  saveFile: (path: string, content: string) => Promise<void>;
  copyPath: (path: string) => void | Promise<void>;
  revealInTree: (path: string) => void;
}

const requireRuntimeBaseUrl = (runtimeBaseUrl?: string) => {
  if (!runtimeBaseUrl) {
    throw new Error('Workspace runtime URL is unavailable');
  }

  return runtimeBaseUrl;
};

export const createWorkspaceFileWorkbenchAdapter = ({
  runtimeBaseUrl,
  readFile,
  saveFile,
  copyPath,
  revealInTree,
}: WorkspaceFileWorkbenchAdapterOptions): FileViewerWorkbenchAdapter => ({
  readFile,
  readBlob: async (path) => {
    const client = new ApiClient({
      baseUrl: requireRuntimeBaseUrl(runtimeBaseUrl),
      unauthorizedBehavior: 'propagate',
      executionAudience: 'workspace-runtime',
    });
    return client.getBlob(`/api/v1/files/content?path=${encodeURIComponent(path)}&raw=true`);
  },
  saveFile,
  copyPath,
  revealInTree,
});
