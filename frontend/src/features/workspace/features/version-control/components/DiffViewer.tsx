/**
 * DiffViewer - 差異檢視器組件
 * 
 * 顯示檔案變更的差異內容
 */

import React, { useState, useEffect, useCallback } from 'react';
import type { VersionControlFileChange } from '../types';
import { buildVersionControlUrl } from '../utils';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { ApiClient } from '@/shared/api/apiClient';
import { VersionControlDiffContent } from '@/shared/components/version-control';
import { useI18n } from '@/shared/hooks/useI18n';

interface DiffViewerProps {
  selectedFile?: VersionControlFileChange | null;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ selectedFile }) => {
  const [diffContent, setDiffContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;

  const buildVersionControlRequestUrl = useCallback(
    (path: string) => {
      if (!runtimeBaseUrl || !workspaceId) {
        throw new Error(workspaceRuntime.error ?? 'Workspace Runtime 尚未就緒');
      }
      return buildVersionControlUrl(runtimeBaseUrl, workspaceId, path);
    },
    [runtimeBaseUrl, workspaceId, workspaceRuntime.error],
  );

  const fetchDiff = useCallback(async (filePath: string, changeType?: 'staged' | 'unstaged' | 'untracked'): Promise<string> => {
    // 根據 changeType 決定使用的 head 參數
    // - staged: 已暫存的變更，比較 HEAD 與索引 (INDEX)
    // - unstaged/untracked: 未暫存的變更，比較索引與工作目錄 (WORKTREE)
    const head = changeType === 'staged' ? 'INDEX' : 'WORKTREE';
    const url = buildVersionControlRequestUrl(`diff?path=${encodeURIComponent(filePath)}&head=${head}`);

    // 使用 ApiClient 來確保請求攜帶 Authorization header
    const apiClient = new ApiClient({ baseUrl: runtimeBaseUrl });
    const fullPath = `/api/v1/workspaces/${workspaceId}/version-control/diff?path=${encodeURIComponent(filePath)}&head=${head}`;

    const data = await apiClient.get<{ patch?: string; diff?: string }>(fullPath);
    return data.patch || data.diff || '';
  }, [buildVersionControlRequestUrl, runtimeBaseUrl, workspaceId]);

  // 載入差異內容
  useEffect(() => {
    const loadDiff = async () => {
      if (!selectedFile) {
        setDiffContent('');
        setIsLoading(false);
        setError(null);
        return;
      }

      // 如果檔案已經有 diff 內容，直接使用
      const existingDiff = selectedFile.diff ?? selectedFile.patch ?? '';
      if (existingDiff) {
        setIsLoading(true);
        setTimeout(() => {
          setDiffContent(existingDiff);
          setError(null);
          setIsLoading(false);
        }, 100);
        return;
      }

      // 如果沒有 diff 內容且 runtime 未準備好，顯示錯誤
      if (!runtimeBaseUrl || !workspaceId) {
        if (!workspaceRuntime.isLoading && workspaceRuntime.error) {
          setError(workspaceRuntime.error);
        }
        setDiffContent('');
        setIsLoading(false);
        return;
      }

      // 動態載入 diff 內容
      setIsLoading(true);
      setError(null);
      try {
        const diffContent = await fetchDiff(selectedFile.path, selectedFile.changeType);
        setDiffContent(diffContent);
      } catch (err) {
        const message = err instanceof Error ? err.message : t('workspace.versionControl.diff.loadFailed');
        setError(message);
        setDiffContent('');
      } finally {
        setIsLoading(false);
      }
    };

    loadDiff();
  }, [selectedFile, runtimeBaseUrl, workspaceId, workspaceRuntime.isLoading, workspaceRuntime.error, fetchDiff, t]);

  return (
    <VersionControlDiffContent
      diffContent={diffContent}
      selectedPath={selectedFile?.path ?? null}
      isLoading={isLoading}
      error={error}
    />
  );
};
