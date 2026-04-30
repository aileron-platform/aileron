import React, { useMemo, useState } from 'react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { Wand2 } from 'lucide-react';
import { FileEditor } from '@/shared/components/file-workbench';
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

  const [fileContent, setFileContent] = useState('');
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  React.useEffect(() => {
    if (!selectedFile) {
      setFileContent('');
      return;
    }

    setIsLoadingFile(true);
    api
      .getSkill(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId, selectedFile.path, selectedFile.scope)
      .then((response) => {
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

  const handleSaveFile = async (content: string) => {
    if (!selectedFile) return;

    setIsSaving(true);
    try {
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

  const isPluginFile = selectedFile?.scope === 'plugin';
  const fileName = selectedFile?.path.split('/').pop() || '';

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <FeatureHeader
        title={t(`${i18nNamespace}.skills.header.title`)}
        icon={Wand2}
      />

      <div className="flex-1 overflow-hidden border-t border-border bg-background">
        {!selectedFile ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t(`${i18nNamespace}.skills.noSelection`)}
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
