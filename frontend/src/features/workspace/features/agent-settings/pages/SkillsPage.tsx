import React, { useMemo, useState } from 'react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { Wand2 } from 'lucide-react';
import { FileEditor } from '@/shared/components/file-editors';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { SelectedFile } from '../../claude-code/components/ClaudeCodeFileManager';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('SkillsPage');

export interface SkillsPageProps {
  selectedFile: SelectedFile | null;
  apiPrefix?: string;
  i18nNamespace?: string;
}

const SkillsPage: React.FC<SkillsPageProps> = ({ selectedFile, apiPrefix = 'claude-code', i18nNamespace = 'workspace.claudeCode' }) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

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
    api
      .getSkill(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId, selectedFile.path, selectedFile.scope)
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
      // Plugin 檔案是唯讀的，只有 project 和 user scope 可以儲存
      await api.updateSkill(
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

  // 判斷是否為 plugin scope 的檔案（唯讀）
  const isPluginFile = selectedFile?.scope === 'plugin';
  const fileName = selectedFile?.path.split('/').pop() || '';

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <FeatureHeader
        title={t(`${i18nNamespace}.skills.header.title`, { defaultValue: '編輯器' })}
        icon={Wand2}
      />

      <div className="flex-1 overflow-hidden border-t border-border bg-background">
        {!selectedFile ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t(`${i18nNamespace}.skills.noSelection`, { defaultValue: '請從左側選擇技能檔案以檢視內容。' })}
          </div>
        ) : (
          <FileEditor
            key={selectedFile.path}
            fileName={fileName}
            filePath={selectedFile.path}
            fileContent={fileContent}
            fileIcon={<Wand2 className="h-4 w-4 text-purple-600 dark:text-purple-400" />}
            readOnly={isPluginFile}
            onSave={handleSaveFile}
            isLoading={isLoadingFile}
            isSaving={isSaving}
          />
        )}
      </div>
    </div>
  );
};

export default SkillsPage;
