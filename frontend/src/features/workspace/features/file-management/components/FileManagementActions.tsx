/**
 * FileManagementActions - 檔案管理工具按鈕組
 * 提供檔案操作相關的工具按鈕
 */

import React, { useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('FileManagementActions');
import { Save, SaveAll, RefreshCw } from 'lucide-react';
import { Button } from '../../../../../shared/components/ui/button';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';

export const FileManagementActions: React.FC = () => {
  const { workspace, fileTreeActions, fileEditor } = useWorkspace();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const { t } = useI18n();

  // 檢查是否有修改的檔案
  const hasModifiedFiles = fileEditor.modifiedTabs.length > 0;

  // 當前活動檔案
  const activeTab = workspace.openTabs.find(tab => tab.id === workspace.activeTabId);
  const hasActiveFile = !!activeTab;
  const isActiveFileModified = activeTab ? fileEditor.modifiedTabs.includes(activeTab.id) : false;

  // 儲存當前檔案
  const handleSaveFile = async () => {
    if (!activeTab) return;

    setIsSaving(true);
    try {
      await fileEditor.saveFile(activeTab.id);
    } catch (error) {
      logger.error('儲存檔案失敗', { error });
    } finally {
      setIsSaving(false);
    }
  };

  // 儲存所有檔案
  const handleSaveAllFiles = async () => {
    setIsSavingAll(true);
    try {
      await fileEditor.saveAllFiles();
    } catch (error) {
      logger.error('儲存所有檔案失敗', { error });
    } finally {
      setIsSavingAll(false);
    }
  };

  // 重新整理當前檔案
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      if (hasActiveFile) {
        // 如果有開啟的檔案，重新載入當前檔案
        const result = await fileEditor.reloadCurrentFile();
        if (!result.success && result.error) {
          logger.error('重新載入檔案失敗', { error: result.error });
        }
      } else {
        // 如果沒有開啟的檔案，重新整理檔案樹
        await fileTreeActions.refreshFileTree();
      }
    } catch (error) {
      logger.error('重新整理失敗', { error });
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {/* 儲存當前檔案 */}
      {hasActiveFile && isActiveFileModified && (
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-xs"
          onClick={handleSaveFile}
          disabled={isSaving}
          title={t('workspace.fileManagement.actions.saveCurrent.tooltip')}
        >
          <Save className="h-3 w-3 mr-1" />
          {isSaving ? '儲存中...' : t('workspace.fileManagement.actions.saveCurrent.label')}
        </Button>
      )}

      {/* 儲存所有檔案 */}
      {hasModifiedFiles && (
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-xs"
          onClick={handleSaveAllFiles}
          disabled={isSavingAll}
          title={t('workspace.fileManagement.actions.saveAll.tooltip')}
        >
          <SaveAll className="h-3 w-3 mr-1" />
          {isSavingAll ? '儲存中...' : t('workspace.fileManagement.actions.saveAll.label')}
        </Button>
      )}

      {/* 重新整理 */}
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        onClick={handleRefresh}
        disabled={isRefreshing}
        title={t('workspace.fileManagement.actions.refresh.tooltip')}
      >
        <RefreshCw className={`h-3 w-3 mr-1 ${isRefreshing ? 'animate-spin' : ''}`} />
        {t('workspace.fileManagement.actions.refresh.label')}
      </Button>
    </div>
  );
};

export default FileManagementActions;
