import { apiClient } from '@/shared/api/apiClient';
import type { FileViewerWorkbenchAdapter } from '@/shared/components/file-workbench';

export interface TemplateFileWorkbenchAdapterOptions {
  templateId: string;
  scope: string;
  readFile: (path: string) => Promise<string>;
  saveFile?: (path: string, content: string) => Promise<void>;
  copyPath?: (path: string) => void | Promise<void>;
  revealInTree?: (path: string) => void;
}

const getTemplateFileContentUrl = (templateId: string, scope: string, path: string) =>
  `/api/v1/templates/${templateId}/files/content?scope=${encodeURIComponent(scope)}&path=${encodeURIComponent(path)}`;

export const createTemplateFileWorkbenchAdapter = ({
  templateId,
  scope,
  readFile,
  saveFile,
  copyPath,
  revealInTree,
}: TemplateFileWorkbenchAdapterOptions): FileViewerWorkbenchAdapter => ({
  readFile,
  readBlob: (path) => apiClient.getBlob(getTemplateFileContentUrl(templateId, scope, path)),
  saveFile,
  copyPath,
  revealInTree,
});
