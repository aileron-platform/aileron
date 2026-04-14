/**
 * DiffViewer - 差異檢視器組件
 * 
 * 顯示檔案變更的差異內容
 */

import React, { useState, useEffect, useCallback } from 'react';
import { FileText } from 'lucide-react';
import type { VersionControlFileChange } from '../types';
import { buildVersionControlUrl, parseVersionControlError } from '../utils';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { ApiClient } from '@/shared/api/apiClient';

interface DiffLine {
  type: 'add' | 'remove' | 'context' | 'header';
  oldLineNumber?: number;
  newLineNumber?: number;
  content: string;
}

interface DiffViewerProps {
  selectedFile?: VersionControlFileChange | null;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ selectedFile }) => {
  const [diffLines, setDiffLines] = useState<DiffLine[]>([]);
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

  // 解析差異內容
  const parseDiff = useCallback((diffContent: string): DiffLine[] => {
    const lines = diffContent.split('\n');
    const result: DiffLine[] = [];
    let oldLineNumber = 1;
    let newLineNumber = 1;

    for (const line of lines) {
      if (line.startsWith('@@')) {
        result.push({
          type: 'header',
          content: line
        });
        // 解析行號資訊
        const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/);
        if (match) {
          oldLineNumber = parseInt(match[1]);
          newLineNumber = parseInt(match[2]);
        }
      } else if (line.startsWith('+')) {
        result.push({
          type: 'add',
          newLineNumber: newLineNumber++,
          content: line.substring(1)
        });
      } else if (line.startsWith('-')) {
        result.push({
          type: 'remove',
          oldLineNumber: oldLineNumber++,
          content: line.substring(1)
        });
      } else if (line.startsWith(' ')) {
        result.push({
          type: 'context',
          oldLineNumber: oldLineNumber++,
          newLineNumber: newLineNumber++,
          content: line.substring(1)
        });
      }
    }

    return result;
  }, []);

  // 檢查是否為二進位或大檔案
  const isBinaryOrLargeFile = useCallback((diffContent: string): boolean => {
    return diffContent.includes('Binary file:') ||
           diffContent.includes('Large text file:') ||
           diffContent.includes('Binary files') ||
           diffContent.includes('(Binary files cannot be displayed)') ||
           diffContent.includes('(File too large to display');
  }, []);

  // 載入差異內容
  useEffect(() => {
    const loadDiff = async () => {
      if (!selectedFile) {
        setDiffLines([]);
        setIsLoading(false);
        setError(null);
        return;
      }

      // 如果檔案已經有 diff 內容，直接使用
      const existingDiff = selectedFile.diff ?? selectedFile.patch ?? '';
      if (existingDiff) {
        setIsLoading(true);
        setTimeout(() => {
          // 檢查是否為二進位或大檔案
          if (isBinaryOrLargeFile(existingDiff)) {
            setError(existingDiff);
            setDiffLines([]);
          } else {
            const lines = parseDiff(existingDiff);
            setDiffLines(lines);
            setError(null);
          }
          setIsLoading(false);
        }, 100);
        return;
      }

      // 如果沒有 diff 內容且 runtime 未準備好，顯示錯誤
      if (!runtimeBaseUrl || !workspaceId) {
        if (!workspaceRuntime.isLoading && workspaceRuntime.error) {
          setError(workspaceRuntime.error);
        }
        setDiffLines([]);
        setIsLoading(false);
        return;
      }

      // 動態載入 diff 內容
      setIsLoading(true);
      setError(null);
      try {
        const diffContent = await fetchDiff(selectedFile.path, selectedFile.changeType);

        // 檢查是否為二進位或大檔案
        if (isBinaryOrLargeFile(diffContent)) {
          setError(diffContent);
          setDiffLines([]);
        } else {
          const lines = parseDiff(diffContent);
          setDiffLines(lines);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : '載入差異內容失敗';
        setError(message);
        setDiffLines([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadDiff();
  }, [selectedFile, runtimeBaseUrl, workspaceId, workspaceRuntime.isLoading, workspaceRuntime.error, fetchDiff, parseDiff, isBinaryOrLargeFile]);

  // 渲染差異行
  const renderDiffLine = (line: DiffLine, index: number) => {
    const getLineClass = () => {
      switch (line.type) {
        case 'add':
          // 新增行：淺色模式用淺綠背景，深色模式用深綠背景
          return 'bg-green-50 dark:bg-green-500/10 border-l-2 border-l-green-600 dark:border-l-green-400';
        case 'remove':
          // 刪除行：淺色模式用淺紅背景，深色模式用深紅背景
          return 'bg-red-50 dark:bg-red-500/10 border-l-2 border-l-red-600 dark:border-l-red-400';
        case 'header':
          // 標題行：淺色模式用淺藍背景，深色模式用深藍背景
          return 'bg-blue-50 dark:bg-blue-500/10 border-l-2 border-l-blue-600 dark:border-l-blue-400 font-medium';
        default:
          return 'bg-background';
      }
    };

    const getLinePrefix = () => {
      switch (line.type) {
        case 'add':
          return '+';
        case 'remove':
          return '-';
        default:
          return ' ';
      }
    };

    const getLinePrefixClass = () => {
      switch (line.type) {
        case 'add':
          return 'text-green-600 dark:text-green-400';
        case 'remove':
          return 'text-red-600 dark:text-red-400';
        default:
          return 'text-muted-foreground';
      }
    };

    return (
      <div key={index} className={`flex text-sm font-mono ${getLineClass()}`}>
        {/* 行號 */}
        <div className="flex">
          <div className="w-12 px-2 py-1 text-right text-muted-foreground bg-muted/20 border-r border-border">
            {line.oldLineNumber || ''}
          </div>
          <div className="w-12 px-2 py-1 text-right text-muted-foreground bg-muted/20 border-r border-border">
            {line.newLineNumber || ''}
          </div>
        </div>

        {/* 內容 */}
        <div className="flex-1 px-2 py-1 overflow-x-auto">
          <span className={`mr-2 font-bold ${getLinePrefixClass()}`}>{getLinePrefix()}</span>
          <span className="whitespace-pre-wrap text-foreground">
            {line.content}
          </span>
        </div>
      </div>
    );
  };

  // 判斷錯誤類型
  const isBinaryOrLargeError = error && (
    error.includes('Binary file:') ||
    error.includes('Large text file:') ||
    error.includes('Binary files cannot be displayed') ||
    error.includes('File too large to display')
  );

  return (
    <div className="h-full flex flex-col bg-background">
      {/* 差異內容 */}
      <div className="flex-1 overflow-auto">
        {error ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md px-4">
              <FileText className={`w-12 h-12 mx-auto mb-4 opacity-50 ${isBinaryOrLargeError ? 'text-muted-foreground' : 'text-destructive'}`} />
              <div className={`text-sm mb-2 ${isBinaryOrLargeError ? 'text-foreground' : 'text-destructive'}`}>
                {isBinaryOrLargeError ? '無法顯示檔案內容' : '載入差異內容失敗'}
              </div>
              <div className="text-xs text-muted-foreground whitespace-pre-wrap text-left bg-muted/30 p-3 rounded border border-border">
                {error}
              </div>
              {isBinaryOrLargeError && selectedFile && (
                <div className="mt-4 text-xs text-muted-foreground">
                  檔案路徑: {selectedFile.path}
                </div>
              )}
            </div>
          </div>
        ) : isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-sm text-muted-foreground">
              {t('workspace.versionControl.diff.loading')}
            </div>
          </div>
        ) : diffLines.length > 0 ? (
          <div className="min-h-full">
            {diffLines.map((line, index) => renderDiffLine(line, index))}
          </div>
        ) : selectedFile ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <div className="text-sm">{t('workspace.versionControl.diff.noDifference')}</div>
              <div className="text-xs mt-2 font-mono">{selectedFile.path}</div>
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <div className="text-sm">{t('workspace.versionControl.diff.empty')}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
