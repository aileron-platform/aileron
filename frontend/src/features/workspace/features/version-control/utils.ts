import type { VersionControlFileChange } from './types';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('VersionControlUtils');

export const buildVersionControlUrl = (
  runtimeBaseUrl: string,
  workspaceId: string,
  path: string,
): string => {
  const normalizedBase = runtimeBaseUrl.endsWith('/') ? runtimeBaseUrl : `${runtimeBaseUrl}/`;
  const normalizedPath = path.startsWith('/') ? path.slice(1) : path;
  const fullPath = `api/v1/workspaces/${encodeURIComponent(workspaceId)}/version-control/${normalizedPath}`;
  return new URL(fullPath, normalizedBase).toString();
};

export const parseVersionControlError = async (response: Response): Promise<string> => {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === 'string') {
      return payload.detail;
    }
    if (payload?.detail?.message) {
      return payload.detail.message;
    }
    if (typeof payload?.message === 'string') {
      return payload.message;
    }
  } catch (error) {
    logger.warn('解析版本控制錯誤回應失敗', { error });
  }
  return `${response.status} ${response.statusText}`;
};

export const mapCommitFileToChange = (file: VersionControlFileChange): VersionControlFileChange => ({
  ...file,
  diff: file.diff ?? file.patch ?? null,
});
