/**
 * VersionControlFeature - 版本控制功能組件
 *
 * 提供版本控制的側邊欄和主內容區域組件
 */

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { GitBranch, History, ChevronLeft, RefreshCw } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { FileChangesPanel } from './components/FileChangesPanel';
import { CommitHistoryPanel } from './components/CommitHistoryPanel';
import { DiffViewer } from './components/DiffViewer';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { useQueryClient } from '@tanstack/react-query';
import { refreshVersionControlQueries } from './lib/queryClient';
import type {
  VersionControlFileChange,
  VersionControlCommitSummary,
} from './types';

// 版本控制狀態類型
interface VersionControlState {
  selectedFile: VersionControlFileChange | null;
  selectedCommit: VersionControlCommitSummary | null;
}

// 版本控制操作類型
interface VersionControlActions {
  selectFile: (file: VersionControlFileChange | null) => void;
  selectCommit: (commit: VersionControlCommitSummary | null) => void;
}

// 版本控制 Context
const VersionControlContext =
  createContext<(VersionControlState & VersionControlActions) | null>(null);

// 版本控制側邊欄組件（第二欄）
export const VersionControlSidebar: React.FC = () => {
  const { state, workspace, workspaceRuntime, dispatch } = useWorkspace();
  const context = useContext(VersionControlContext);
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const workspaceId = workspaceRuntime.workspaceId ?? '';
  const selectedGitContextId = state.versionControl.selectedGitContextId;

  const handleToggleCollapse = () => {
    dispatch({ type: 'TOGGLE_SECOND_COLUMN' });
  };

  const handleRefresh = useCallback(async () => {
    if (!workspaceId) {
      return;
    }

    setIsRefreshing(true);
    try {
      await refreshVersionControlQueries(queryClient, workspaceId, {
        includeBranches: true,
        includeCommits: true,
        includeContexts: true,
        contextId: selectedGitContextId,
      });
    } finally {
      setIsRefreshing(false);
    }
  }, [queryClient, selectedGitContextId, workspaceId]);

  if (!context) {
    return (
      <div className="h-full flex flex-col">
        <div className={`h-10 px-3 border-b border-border bg-card flex items-center ${state.secondColumnCollapsed ? 'justify-center' : 'justify-between'}`}>
          {!state.secondColumnCollapsed && (
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-medium text-foreground">
                {workspace.versionControl?.subView === 'changes'
                  ? t('workspace.versionControl.sidebar.title.changes')
                  : t('workspace.versionControl.sidebar.title.history')}
              </h2>
            </div>
          )}
          <div className="flex items-center gap-1">
            {!state.secondColumnCollapsed && workspace.versionControl?.subView === 'changes' && (
              <button
                onClick={() => {
                  void handleRefresh();
                }}
                className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground transition-colors disabled:opacity-50"
                title={t('workspace.versionControl.actions.refresh.tooltip')}
                aria-label={t('workspace.versionControl.actions.refresh.label')}
                disabled={isRefreshing}
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
              </button>
            )}
            <button
              onClick={handleToggleCollapse}
              className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground"
              title={state.secondColumnCollapsed
                ? t('workspace.versionControl.sidebar.toggle.expand')
                : t('workspace.versionControl.sidebar.toggle.collapse')}
            >
              <ChevronLeft className={`w-3.5 h-3.5 transition-transform ${state.secondColumnCollapsed ? 'rotate-180' : ''}`} />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          {!state.secondColumnCollapsed ? (
            <div className="p-4">
              <div className="text-sm text-foreground opacity-60">
                {t('workspace.versionControl.sidebar.loadingDescription')}
              </div>
            </div>
          ) : (
            <CollapsedSidebarPlaceholder
              icon={GitBranch}
              className="text-primary"
              iconClassName="text-primary"
            />
          )}
        </div>
      </div>
    );
  }

  const { selectFile, selectCommit, selectedCommit } = context;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className={`h-10 px-3 border-b border-border bg-card flex items-center ${state.secondColumnCollapsed ? 'justify-center' : 'justify-between'}`}>
        {!state.secondColumnCollapsed && (
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-medium text-foreground">
              {workspace.versionControl?.subView === 'changes'
                ? t('workspace.versionControl.sidebar.title.changes')
                : t('workspace.versionControl.sidebar.title.history')}
            </h2>
          </div>
        )}
        <div className="flex items-center gap-1">
          {!state.secondColumnCollapsed && workspace.versionControl?.subView === 'changes' && (
            <button
              onClick={() => {
                void handleRefresh();
              }}
              className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground transition-colors disabled:opacity-50"
              title={t('workspace.versionControl.actions.refresh.tooltip')}
              aria-label={t('workspace.versionControl.actions.refresh.label')}
              disabled={isRefreshing}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>
          )}
          <button
            onClick={handleToggleCollapse}
            className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground"
            title={state.secondColumnCollapsed
              ? t('workspace.versionControl.sidebar.toggle.expand')
              : t('workspace.versionControl.sidebar.toggle.collapse')}
          >
            <ChevronLeft className={`w-3.5 h-3.5 transition-transform ${state.secondColumnCollapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {!state.secondColumnCollapsed ? (
          workspace.versionControl?.subView === 'changes' ? (
            <FileChangesPanel
              onFileSelect={selectFile}
            />
          ) : (
            <CommitHistoryPanel
              selectedCommitId={selectedCommit ? selectedCommit.id : ''}
              onCommitSelect={selectCommit}
              onFileSelect={selectFile}
            />
          )
        ) : (
          <CollapsedSidebarPlaceholder
            icon={GitBranch}
            className="text-primary"
            iconClassName="text-primary"
          />
        )}
      </div>
    </div>
  );
};

// 版本控制主內容組件（第三欄）
export const VersionControlMainContent: React.FC = () => {
  const { workspace } = useWorkspace();
  const context = useContext(VersionControlContext);
  const { t } = useI18n();

  if (!context) {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-medium text-foreground">
              {t('workspace.versionControl.main.loadingTitle')}
            </h2>
          </div>
        </div>
        {/* Content */}
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <div className="text-center">
            <GitBranch className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg">{t('workspace.versionControl.main.loadingDescription')}</p>
          </div>
        </div>
      </div>
    );
  }

  const { selectedFile, selectedCommit } = context;

  if (workspace.versionControl?.subView === 'changes') {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-medium text-foreground">
              {selectedFile
                ? t('workspace.versionControl.main.changes.titleWithFile', { path: selectedFile.path })
                : t('workspace.versionControl.main.changes.titleWithoutFile')}
            </h2>
          </div>
        </div>
        {/* Content */}
        <div className="flex-1 overflow-hidden">
          <DiffViewer
            selectedFile={selectedFile}
          />
        </div>
      </div>
    );
  } else {
    // 在 history 模式下，主內容區域顯示選中檔案的 diff
    if (selectedFile) {
      return (
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-medium text-foreground">
                {t('workspace.versionControl.main.history.titleWithFile', { path: selectedFile.path })}
              </h2>
            </div>
          </div>
          {/* Content */}
          <div className="flex-1 overflow-hidden">
            <DiffViewer
              selectedFile={selectedFile}
            />
          </div>
        </div>
      );
    } else {
      return (
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-medium text-foreground">
                {selectedCommit
                  ? t('workspace.versionControl.main.history.titleWithCommit')
                  : t('workspace.versionControl.main.history.titleWithoutCommit')}
              </h2>
            </div>
          </div>
          {/* Content */}
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <History className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg">
                {selectedCommit
                  ? t('workspace.versionControl.main.history.titleWithCommit')
                  : t('workspace.versionControl.main.history.titleWithoutCommit')}
              </p>
              <p className="text-sm mt-2">
                {selectedCommit
                  ? t('workspace.versionControl.main.history.descriptionWithCommit')
                  : t('workspace.versionControl.main.history.descriptionWithoutCommit')}
              </p>
            </div>
          </div>
        </div>
      );
    }
  }
};

// 版本控制 Provider 組件
const VersionControlProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedFile, setSelectedFile] = useState<VersionControlFileChange | null>(null);
  const [selectedCommit, setSelectedCommit] = useState<VersionControlCommitSummary | null>(null);

  const selectFile = useCallback((file: VersionControlFileChange | null) => {
    setSelectedFile(file);
  }, []);

  const selectCommit = useCallback((commit: VersionControlCommitSummary | null) => {
    setSelectedCommit(commit);
    // 當選擇新的 commit 時，清除檔案選擇
    setSelectedFile(null);
  }, []);

  const contextValue = useMemo(
    () => ({
      selectedFile,
      selectedCommit,
      selectFile,
      selectCommit,
    }),
    [selectedFile, selectedCommit, selectFile, selectCommit],
  );

  return (
    <VersionControlContext.Provider value={contextValue}>
      {children}
    </VersionControlContext.Provider>
  );
};

// 版本控制容器組件
export const VersionControlContainer: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <VersionControlProvider>
      {children}
    </VersionControlProvider>
  );
};

// 導出主要組件
export const VersionControlFeature = {
  Sidebar: VersionControlSidebar,
  MainContent: VersionControlMainContent,
  Container: VersionControlContainer,
};

// 默認導出一個 React 組件，供 lazy loading 使用
const VersionControlFeatureDefault: React.FC = () => {
  return (
    <VersionControlContainer>
      <div className="h-full flex">
        <div className="w-1/2">
          <VersionControlSidebar />
        </div>
        <div className="w-1/2">
          <VersionControlMainContent />
        </div>
      </div>
    </VersionControlContainer>
  );
};

export default VersionControlFeatureDefault;
