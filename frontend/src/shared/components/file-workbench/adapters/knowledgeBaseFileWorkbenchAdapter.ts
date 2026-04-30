import { apiClient } from '@/shared/api/apiClient';
import { API_ENDPOINTS } from '../constants';
import type { FileViewerWorkbenchAdapter } from '../viewer';

export interface KnowledgeBaseFileWorkbenchAdapterOptions {
  knowledgeBaseId: string;
  readFile: (path: string) => Promise<string>;
  saveFile?: (path: string, content: string) => Promise<void>;
  copyPath?: (path: string) => void | Promise<void>;
  revealInTree?: (path: string) => void;
}

export const createKnowledgeBaseFileWorkbenchAdapter = ({
  knowledgeBaseId,
  readFile,
  saveFile,
  copyPath,
  revealInTree,
}: KnowledgeBaseFileWorkbenchAdapterOptions): FileViewerWorkbenchAdapter => ({
  readFile,
  readBlob: (path) => apiClient.getBlob(
    `${API_ENDPOINTS.knowledgeBase.getContent(knowledgeBaseId)}?path=${encodeURIComponent(path)}&raw=true`,
  ),
  saveFile,
  copyPath,
  revealInTree,
});
