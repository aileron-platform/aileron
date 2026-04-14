import React, { useState } from 'react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { FileCode } from 'lucide-react';
import { FileEditor } from '@/shared/components/file-editors';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { claudeCodeApi } from '../services/claudeCodeApi';
import type { SelectedFile } from '../components/ClaudeCodeFileManager';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('ScriptsPage');

interface ScriptsPageProps {
  selectedFile: SelectedFile | null;
}

const ScriptsPage: React.FC<ScriptsPageProps> = ({ selectedFile }) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();

  // 檔案狀態
  const [fileContent, setFileContent] = useState('');
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // 當選擇的檔案改變時，載入內容
  React.useEffect(() => {
    if (!selectedFile) {
      setFileContent('');
      return;
    }

    setIsLoadingFile(true);
    claudeCodeApi
      .getScript(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId, selectedFile.path, selectedFile.scope as 'project' | 'user')
      .then((response) => {
        // 新的統一 API 回應格式：直接包含 content 欄位
        setFileContent(response.content || '');
      })
      .catch((error) => {
        logger.error('Failed to load file', { error });
        setFileContent('');
      })
      .finally(() => {
        setIsLoadingFile(false);
      });
  }, [selectedFile, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  // 儲存檔案
  const handleSaveFile = async (content: string) => {
    if (!selectedFile) return;

    setIsSaving(true);
    try {
      await claudeCodeApi.updateScript(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        selectedFile.path,
        { content },
        selectedFile.scope as 'project' | 'user'
      );
    } catch (error) {
      logger.error('Failed to save file', { error });
      throw error;
    } finally {
      setIsSaving(false);
    }
  };

  const fileName = selectedFile?.path.split('/').pop() || '';

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <FeatureHeader
        title={t('workspace.claudeCode.scripts.header.title', { defaultValue: '腳本檔案預覽' })}
        icon={FileCode}
      />

      <div className="flex-1 overflow-hidden border-t border-border bg-background">
        {!selectedFile ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t('workspace.claudeCode.scripts.noSelection', { defaultValue: '請從左側選擇腳本檔案以檢視內容。' })}
          </div>
        ) : (
          <FileEditor
            key={selectedFile.path}
            fileName={fileName}
            filePath={selectedFile.path}
            fileContent={fileContent}
            fileIcon={<FileCode className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />}
            onSave={handleSaveFile}
            isLoading={isLoadingFile}
            isSaving={isSaving}
          />
        )}
      </div>
    </div>
  );
};

export default ScriptsPage;

