import { ApiClient } from '@/shared/api/apiClient';
import type { FileViewerWorkbenchAdapter } from '@/shared/components/file-workbench/viewer-entry';

export interface WorkspaceFileWorkbenchAdapterOptions {
  runtimeBaseUrl?: string;
  readFile: (path: string) => Promise<string>;
  saveFile: (path: string, content: string) => Promise<void>;
  saveDrawio: (path: string, content: string) => void | Promise<void>;
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
  saveDrawio,
  copyPath,
  revealInTree,
}: WorkspaceFileWorkbenchAdapterOptions): FileViewerWorkbenchAdapter => ({
  readFile,
  readBlob: async (path) => {
    const client = new ApiClient({ baseUrl: requireRuntimeBaseUrl(runtimeBaseUrl) });
    return client.getBlob(`/api/v1/files/content?path=${encodeURIComponent(path)}&raw=true`);
  },
  saveFile,
  getDrawioViewerUrl: async (path, mode) => {
    const client = new ApiClient({ baseUrl: requireRuntimeBaseUrl(runtimeBaseUrl) });
    const data = await client.get<{ url: string }>(
      `/api/v1/drawio/viewer?file_path=${encodeURIComponent(path)}&mode=${mode}`,
    );
    return data.url;
  },
  saveDrawio: async (path, content) => {
    const client = new ApiClient({ baseUrl: requireRuntimeBaseUrl(runtimeBaseUrl) });
    await client.post(`/api/v1/drawio/save?file_path=${encodeURIComponent(path)}`, { content });
    await saveDrawio(path, content);
  },
  copyPath,
  revealInTree,
});
