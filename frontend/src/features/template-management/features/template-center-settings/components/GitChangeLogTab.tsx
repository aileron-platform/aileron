import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { RefreshCcw, GitCommit, GitPullRequest, ChevronDown, ChevronRight, Folder, File, Loader2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Separator } from '@/shared/components/ui/separator';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { useTaskProgress } from '@/shared/hooks/useTaskProgress';
import { TaskProgressDialog } from '@/shared/components/task-progress/TaskProgressDialog';
import {
  getGitStatus,
  getGitChanges,
  getGitBranches,
  commitAndPush,
  pullFromRemote,
  rebuildTemplates,
  getRebuildProgress,
  type GitStatus,
  type GitChangeLog,
  type TemplateChange,
  type GitBranchList,
} from '@/shared/services/templateGitApi';
import { CommitDialog } from './CommitDialog';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('GitChangeLogTab');

type ChangeTreeNode = {
  name: string;
  path: string;
  type: 'folder' | 'file';
  children?: ChangeTreeNode[];
};

type MutableTreeNode = ChangeTreeNode & { childrenMap?: Map<string, MutableTreeNode> };

const normalisePath = (value: string): string[] => value.split('/').filter(Boolean);

const insertPath = (
  root: Map<string, MutableTreeNode>,
  segments: string[],
  isFile: boolean,
): void => {
  if (segments.length === 0) {
    return;
  }

  let currentLevel = root;
  let currentPath = '';

  segments.forEach((segment, index) => {
    currentPath = currentPath ? `${currentPath}/${segment}` : segment;
    const isLast = index === segments.length - 1;
    const nodeType: ChangeTreeNode['type'] = isLast && isFile ? 'file' : 'folder';

    let node = currentLevel.get(segment);
    if (!node) {
      node = {
        name: segment,
        path: currentPath,
        type: nodeType,
      };
      if (nodeType === 'folder') {
        node.childrenMap = new Map<string, MutableTreeNode>();
      }
      currentLevel.set(segment, node);
    }

    if (!isLast) {
      if (!node.childrenMap) {
        node.childrenMap = new Map<string, MutableTreeNode>();
      }
      currentLevel = node.childrenMap;
    }
  });
};

const convertToTree = (nodes: Map<string, MutableTreeNode>): ChangeTreeNode[] => {
  return Array.from(nodes.values())
    .map((node) => {
      if (node.type === 'folder') {
        const children = node.childrenMap ? convertToTree(node.childrenMap) : [];
        return {
          name: node.name,
          path: node.path,
          type: 'folder' as const,
          children,
        };
      }

      return {
        name: node.name,
        path: node.path,
        type: 'file' as const,
      };
    })
    .sort((a, b) => {
      if (a.type !== b.type) {
        return a.type === 'folder' ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });
};

const buildChangeTree = (directories: string[], files: string[]): ChangeTreeNode[] => {
  const root = new Map<string, MutableTreeNode>();

  directories.forEach((directory) => {
    const segments = normalisePath(directory);
    if (segments.length > 0) {
      insertPath(root, segments, false);
    }
  });

  files.forEach((filePath) => {
    const segments = normalisePath(filePath);
    if (segments.length > 0) {
      insertPath(root, segments, true);
    }
  });

  return convertToTree(root);
};

export const GitChangeLogTab: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();

  const [isLoading, setIsLoading] = useState(false);
  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [changeLog, setChangeLog] = useState<GitChangeLog | null>(null);
  const [branches, setBranches] = useState<GitBranchList | null>(null);
  const [expandedTemplates, setExpandedTemplates] = useState<Set<string>>(new Set());
  const [expandedNodesByTemplate, setExpandedNodesByTemplate] = useState<Record<string, Set<string>>>({});
  const [commitDialogOpen, setCommitDialogOpen] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [isPulling, setIsPulling] = useState(false);
  const [rebuildProgressDialogOpen, setRebuildProgressDialogOpen] = useState(false);

  // 使用 useTaskProgress Hook 管理重建進度
  const {
    progress: rebuildProgress,
    isPolling: isRebuildPolling,
    startPolling: startRebuildPolling,
    resetProgress: resetRebuildProgress,
  } = useTaskProgress(
    null,
    getRebuildProgress,
    {
      onComplete: (result) => {
        if (result.status === 'completed') {
          loadGitData();
        }
      },
    }
  );

  const templateTrees = useMemo(() => {
    if (!changeLog) {
      return {} as Record<string, ChangeTreeNode[]>;
    }

    return changeLog.templates.reduce<Record<string, ChangeTreeNode[]>>((acc, template) => {
      acc[template.template_id] = buildChangeTree(template.changed_dirs, template.changed_files);
      return acc;
    }, {});
  }, [changeLog]);

  useEffect(() => {
    if (!changeLog) {
      setExpandedNodesByTemplate({});
      return;
    }

    const initialExpanded: Record<string, Set<string>> = {};
    Object.entries(templateTrees).forEach(([templateId, nodes]) => {
      const topLevelFolders = nodes
        .filter((node) => node.type === 'folder')
        .map((node) => node.path);
      if (topLevelFolders.length > 0) {
        initialExpanded[templateId] = new Set(topLevelFolders);
      }
    });
    setExpandedNodesByTemplate(initialExpanded);
  }, [changeLog, templateTrees]);

  // 載入 Git 資料
  const loadGitData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [statusRes, changesRes, branchesRes] = await Promise.all([
        getGitStatus(),
        getGitChanges(),
        getGitBranches(),
      ]);

      if (statusRes.success && statusRes.data) {
        setGitStatus(statusRes.data);
      }

      if (changesRes.success && changesRes.data) {
        setChangeLog(changesRes.data);
      }

      if (branchesRes.success && branchesRes.data) {
        setBranches(branchesRes.data);
      }
    } catch (error) {
      logger.error('載入 Git 資料失敗', { error });
      toast({
        title: t('template.center.settingsDialog.toasts.failed.title'),
        description: t('template.center.settingsDialog.toasts.failed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    void loadGitData();
  }, [loadGitData]);

  // 處理提交
  const handleCommit = async (message: string, branch?: string, push?: boolean) => {
    setIsCommitting(true);
    try {
      const result = await commitAndPush({
        message,
        branch,
        push: push ?? true,
      });

      if (result.success) {
        toast({
          title: t('template.center.settingsDialog.toasts.commitSuccess.title'),
          description: t('template.center.settingsDialog.toasts.commitSuccess.description'),
          variant: 'success',
        });
        // 重新載入資料
        await loadGitData();
      } else {
        toast({
          title: t('template.center.settingsDialog.toasts.commitFailed.title'),
          description: t('template.center.settingsDialog.toasts.commitFailed.description', {
            error: result.error || result.message,
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('提交失敗', { error });
      toast({
        title: t('template.center.settingsDialog.toasts.commitFailed.title'),
        description: error instanceof Error ? error.message : t('template.center.settingsDialog.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsCommitting(false);
    }
  };

  // 處理拉取
  const handlePull = async () => {
    setIsPulling(true);
    try {
      const result = await pullFromRemote({});

      if (result.success) {
        toast({
          title: t('template.center.settingsDialog.toasts.pullSuccess.title'),
          description: t('template.center.settingsDialog.toasts.pullSuccess.description'),
          variant: 'success',
        });
        // 重新載入資料
        await loadGitData();
      } else {
        toast({
          title: t('template.center.settingsDialog.toasts.pullFailed.title'),
          description: t('template.center.settingsDialog.toasts.pullFailed.description', {
            error: result.error || result.message,
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('拉取失敗', { error });
      toast({
        title: t('template.center.settingsDialog.toasts.pullFailed.title'),
        description: error instanceof Error ? error.message : t('template.center.settingsDialog.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsPulling(false);
    }
  };

  // 處理重建
  const handleRebuild = useCallback(async () => {
    try {
      const result = await rebuildTemplates();

      if (result.success && result.task_id) {
        toast({
          title: t('template.center.settingsDialog.toasts.rebuildStarted.title'),
          description: t('template.center.settingsDialog.toasts.rebuildStarted.description'),
          variant: 'default',
        });

        // 打開進度對話框
        setRebuildProgressDialogOpen(true);

        // 傳入 task_id 開始輪詢
        startRebuildPolling(result.task_id);
      } else {
        toast({
          title: t('template.center.settingsDialog.toasts.rebuildFailed.title'),
          description: t('template.center.settingsDialog.toasts.rebuildFailed.description', {
            error: result.error || t('template.center.settingsDialog.toasts.unknownError')
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t('template.center.settingsDialog.toasts.rebuildFailed.title'),
        description: t('template.center.settingsDialog.toasts.rebuildFailed.description', {
          error: error instanceof Error ? error.message : t('template.center.settingsDialog.toasts.unknownError')
        }),
        variant: 'destructive',
      });
    }
  }, [toast, startRebuildPolling, t]);

  // 切換模板展開/收合
  const toggleTemplate = (templateId: string) => {
    setExpandedTemplates((prev) => {
      const next = new Set(prev);
      if (next.has(templateId)) {
        next.delete(templateId);
      } else {
        next.add(templateId);
        setExpandedNodesByTemplate((prevExpanded) => {
          if (prevExpanded[templateId]) {
            return prevExpanded;
          }
          const topLevelFolders = (templateTrees[templateId] || [])
            .filter((node) => node.type === 'folder')
            .map((node) => node.path);
          if (topLevelFolders.length === 0) {
            return prevExpanded;
          }
          return {
            ...prevExpanded,
            [templateId]: new Set(topLevelFolders),
          };
        });
      }
      return next;
    });
  };

  // 展開/收合全部
  const expandAll = () => {
    if (!changeLog) {
      return;
    }

    setExpandedTemplates(new Set(changeLog.templates.map((t) => t.template_id)));

    const allExpanded: Record<string, Set<string>> = {};
    Object.entries(templateTrees).forEach(([templateId, nodes]) => {
      const collect = (items: ChangeTreeNode[]): string[] => {
        const results: string[] = [];
        items.forEach((item) => {
          if (item.type === 'folder') {
            results.push(item.path);
            if (item.children && item.children.length > 0) {
              results.push(...collect(item.children));
            }
          }
        });
        return results;
      };

      const folderPaths = collect(nodes);
      if (folderPaths.length > 0) {
        allExpanded[templateId] = new Set(folderPaths);
      }
    });

    setExpandedNodesByTemplate(allExpanded);
  };

  const collapseAll = () => {
    setExpandedTemplates(new Set());
    setExpandedNodesByTemplate({});
  };

  const toggleDirectory = (templateId: string, path: string) => {
    setExpandedNodesByTemplate((prev) => {
      const current = prev[templateId] ?? new Set<string>();
      const nextSet = new Set(current);
      if (nextSet.has(path)) {
        nextSet.delete(path);
      } else {
        nextSet.add(path);
      }
      return {
        ...prev,
        [templateId]: nextSet,
      };
    });
  };

  const renderTreeNodes = (templateId: string, nodes: ChangeTreeNode[]) => {
    if (!nodes.length) {
      return (
        <div className="text-xs text-muted-foreground">
          {t('template.center.settingsDialog.git.changeLog.emptyTree')}
        </div>
      );
    }

    const renderNodes = (items: ChangeTreeNode[]): React.ReactNode => {
      return items.map((item) => {
        if (item.type === 'folder') {
          const isExpanded = expandedNodesByTemplate[templateId]?.has(item.path) ?? false;
          return (
            <div key={item.path} className="space-y-1">
              <div
                className="flex cursor-pointer select-none items-center gap-2 text-sm"
                onClick={() => toggleDirectory(templateId, item.path)}
              >
                {isExpanded ? (
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                )}
                <Folder className="h-3.5 w-3.5 text-muted-foreground" />
                <span>{item.name}</span>
              </div>
              {isExpanded && item.children && item.children.length > 0 && (
                <div className="pl-5">
                  {renderNodes(item.children)}
                </div>
              )}
            </div>
          );
        }

        return (
          <div key={item.path} className="flex items-center gap-2 text-sm text-muted-foreground pl-5">
            <File className="h-3.5 w-3.5 text-muted-foreground" />
            <span>{item.name}</span>
          </div>
        );
      });
    };

    return <div className="space-y-1">{renderNodes(nodes)}</div>;
  };

  // 渲染狀態徽章
  const renderStatusBadge = (status: TemplateChange['status']) => {
    const variants: Record<TemplateChange['status'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
      modified: 'default',
      added: 'secondary',
      deleted: 'destructive',
      untracked: 'outline',
    };

    return (
      <Badge variant={variants[status]} className="text-xs">
        {t(`template.center.settingsDialog.git.changeLog.status.${status}`)}
      </Badge>
    );
  };

  // 載入中顯示載入提示
  if (isLoading && !gitStatus) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <RefreshCcw className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
        <p className="text-sm text-muted-foreground">
          {t('template.center.settingsDialog.git.status.loading')}
        </p>
      </div>
    );
  }

  // 載入完成後，如果沒有 Git 倉庫才顯示提示
  if (!gitStatus || !gitStatus.is_git_repo) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-sm text-muted-foreground">
          {t('template.center.settingsDialog.git.status.notGitRepo')}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Git 狀態卡片 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t('template.center.settingsDialog.git.status.title')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                {t('template.center.settingsDialog.git.status.currentBranch')}
              </p>
              <p className="text-sm font-semibold">{gitStatus.current_branch}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                {t('template.center.settingsDialog.git.status.changesCount', {
                  count: changeLog?.total_changes || 0,
                })}
              </p>
              <p className="text-sm">
                {changeLog && changeLog.total_changes > 0 ? (
                  <span className="text-orange-600 dark:text-orange-400">
                    {t('template.center.settingsDialog.git.status.changesCountInline', {
                      count: changeLog.total_changes,
                    })}
                  </span>
                ) : (
                  <span className="text-green-600 dark:text-green-400">
                    {t('template.center.settingsDialog.git.status.noChanges')}
                  </span>
                )}
              </p>
            </div>
          </div>

          <Separator />
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                {t('template.center.settingsDialog.git.status.remoteUrl')}
              </p>
              {gitStatus.remote_url ? (
                <p className="text-xs text-muted-foreground truncate" title={gitStatus.remote_url}>
                  {gitStatus.remote_url}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground italic">
                  {t('template.center.settingsDialog.git.status.noRemoteUrl')}
                </p>
              )}
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                {t('template.center.settingsDialog.git.status.syncStatus')}
              </p>
              <p className="text-sm">
                {!gitStatus.remote_url ? (
                  <span className="text-muted-foreground italic">
                    {t('template.center.settingsDialog.git.status.needRemoteUrl')}
                  </span>
                ) : gitStatus.ahead_count > 0 || gitStatus.behind_count > 0 ? (
                  <>
                    {gitStatus.ahead_count > 0 && (
                      <Badge variant="secondary" className="bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                        ↑ {gitStatus.ahead_count}
                      </Badge>
                    )}
                    {gitStatus.ahead_count > 0 && gitStatus.behind_count > 0 && ' '}
                    {gitStatus.behind_count > 0 && (
                      <Badge variant="secondary" className="bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                        ↓ {gitStatus.behind_count}
                      </Badge>
                    )}
                  </>
                ) : (
                  <span className="text-green-600 dark:text-green-400">
                    ✓ {t('template.center.settingsDialog.git.status.upToDate')}
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* 操作按鈕 */}
          <Separator />
          <div className="flex flex-wrap gap-2 justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={loadGitData}
              disabled={isLoading}
            >
              <RefreshCcw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              {t('template.center.settingsDialog.git.actions.refresh')}
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => setCommitDialogOpen(true)}
              disabled={
                !gitStatus?.is_git_repo ||
                !(gitStatus.has_changes || (changeLog && changeLog.total_changes > 0)) ||
                isCommitting
              }
            >
              <GitCommit className="h-4 w-4 mr-2" />
              {t('template.center.settingsDialog.git.actions.commit')}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={handlePull}
              disabled={isPulling}
            >
              <GitPullRequest className="h-4 w-4 mr-2" />
              {t('template.center.settingsDialog.git.actions.pull')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRebuild}
              disabled={isRebuildPolling}
            >
              {isRebuildPolling ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('template.center.settingsDialog.git.actions.rebuilding')}
                </>
              ) : (
                <>
                  <RefreshCcw className="h-4 w-4 mr-2" />
                  {t('template.center.settingsDialog.git.actions.rebuild')}
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 變更記錄 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">
                {t('template.center.settingsDialog.git.changeLog.title')}
              </CardTitle>
              <CardDescription>
                {changeLog && changeLog.total_changes > 0
                  ? t('template.center.settingsDialog.git.status.changesCount', {
                    count: changeLog.total_changes,
                  })
                  : t('template.center.settingsDialog.git.changeLog.emptyMessage')}
              </CardDescription>
            </div>
            {changeLog && changeLog.total_changes > 0 && (
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={expandAll}>
                  {t('template.center.settingsDialog.git.changeLog.expandAll')}
                </Button>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={collapseAll}>
                  {t('template.center.settingsDialog.git.changeLog.collapseAll')}
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!changeLog || changeLog.total_changes === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              {t('template.center.settingsDialog.git.changeLog.emptyMessage')}
            </div>
          ) : (
            <div className="space-y-3">
              {changeLog.templates.map((template) => {
                const isExpanded = expandedTemplates.has(template.template_id);
                const treeNodes = templateTrees[template.template_id] ?? [];
                return (
                  <div key={template.template_id} className="border rounded-lg p-3">
                    <div
                      className="flex items-center justify-between cursor-pointer"
                      onClick={() => toggleTemplate(template.template_id)}
                    >
                      <div className="flex items-center gap-2">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span className="font-medium">{template.template_name}</span>
                        {renderStatusBadge(template.status)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t('template.center.settingsDialog.git.changeLog.filesCount', {
                          count: template.changed_files.length,
                        })}
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="mt-3 space-y-2 pl-6">
                        <p className="text-xs font-medium text-muted-foreground">
                          {t('template.center.settingsDialog.git.changeLog.treeTitle')}
                        </p>
                        {renderTreeNodes(template.template_id, treeNodes)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 重建進度對話框 */}
      <TaskProgressDialog
        open={rebuildProgressDialogOpen}
        onOpenChange={(open) => {
          setRebuildProgressDialogOpen(open);
          // 關閉對話框時重置進度
          if (!open) {
            resetRebuildProgress();
          }
        }}
        progress={rebuildProgress}
        title={t('template.center.settingsDialog.git.changeLog.rebuildProgressTitle')}
      />

      {/* Commit 對話框 */}
      {branches && (
        <CommitDialog
          open={commitDialogOpen}
          onOpenChange={setCommitDialogOpen}
          branches={branches.branches}
          currentBranch={branches.current_branch}
          onCommit={handleCommit}
          isCommitting={isCommitting}
        />
      )}
    </div>
  );
};
