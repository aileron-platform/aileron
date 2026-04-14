/**
 * VersionControlView - 版本控制側邊欄組件
 *
 * 效能優化：
 * - React Query 自動快取和背景更新
 * - 虛擬滾動處理大量項目
 * - 樂觀更新提升使用者體驗
 */

import React from 'react';
import { GitBranch, ChevronLeft } from 'lucide-react';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { FileChangesPanel } from './FileChangesPanel';
import { CommitHistoryPanel } from './CommitHistoryPanel';
import { useI18n } from '@/shared/hooks/useI18n';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';

export const VersionControlView: React.FC = () => {
  const {
    workspace,
    layout,
    toggleSecondColumn
  } = useWorkspace();
  const { t } = useI18n();

  // 根據當前子視圖決定標題
  const getTitle = () => {
    return workspace.versionControl?.subView === 'changes'
      ? t('workspace.versionControl.sidebar.title.changes')
      : t('workspace.versionControl.sidebar.title.history');
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="h-10 px-3 border-b border-sidebar-border bg-card flex items-center justify-between">
        <div className="flex items-center gap-2">
          {!layout.secondColumnCollapsed && (
            <>
              <GitBranch className="h-4 w-4 text-sidebar-primary" />
              <h2 className="text-sm font-medium text-sidebar-foreground">
                {getTitle()}
              </h2>
            </>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={toggleSecondColumn}
            className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground"
            title={layout.secondColumnCollapsed
              ? t('workspace.versionControl.sidebar.toggle.expand')
              : t('workspace.versionControl.sidebar.toggle.collapse')}
          >
            <ChevronLeft className={`w-3.5 h-3.5 transition-transform ${layout.secondColumnCollapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {!layout.secondColumnCollapsed ? (
          workspace.versionControl?.subView === 'changes' ? (
            <FileChangesPanel />
          ) : (
            <CommitHistoryPanel />
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

