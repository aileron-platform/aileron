import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { ScrollText, Wand2 } from 'lucide-react';
import { FileEditor } from '@/shared/components/file-workbench/viewer-entry';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { AgentFileCollection, AgentSelectedFile } from '../types';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('SkillsPage');

export interface SkillsPageProps {
  selectedFile: AgentSelectedFile | null;
  apiPrefix?: string;
  i18nNamespace?: string;
  collectionType?: AgentFileCollection;
}

const SkillsPage: React.FC<SkillsPageProps> = ({
  selectedFile,
  apiPrefix = 'claude-code',
  i18nNamespace = 'workspace.agentSettings.common',
  collectionType = 'skills',
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const [fileContent, setFileContent] = useState('');
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const codexResourceQuery = useQuery({
    queryKey: ['codex-skill-resource-config', workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId, selectedFile?.scope],
    queryFn: () => api.listCodexFiles(
      workspaceRuntime.runtimeBaseUrl,
      workspaceRuntime.workspaceId,
      collectionType,
      selectedFile?.scope === 'user' ? 'user' : 'project',
    ),
    enabled: apiPrefix === 'codex' && collectionType === 'skills' && Boolean(selectedFile && workspaceRuntime.runtimeBaseUrl && workspaceRuntime.workspaceId),
  });

  React.useEffect(() => {
    if (!selectedFile) {
      setFileContent('');
      return;
    }
    if (apiPrefix === 'codex' && selectedFile.scope === 'plugin') {
      setFileContent('');
      return;
    }

    setIsLoadingFile(true);
    const loadFile = apiPrefix === 'codex'
      ? api.getCodexFile(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        collectionType,
        selectedFile.scope === 'user' ? 'user' : 'project',
        selectedFile.path,
      )
      : api[collectionType === 'scripts' ? 'getScript' : 'getSkill'](
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        selectedFile.path,
        selectedFile.scope,
      );
    loadFile
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
  }, [api, apiPrefix, collectionType, selectedFile, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const handleSaveFile = async (content: string) => {
    if (!selectedFile) return;

    setIsSaving(true);
    try {
      if (apiPrefix === 'codex') {
        await api.updateCodexFile(
          workspaceRuntime.runtimeBaseUrl,
          workspaceRuntime.workspaceId,
          collectionType,
          selectedFile.scope === 'user' ? 'user' : 'project',
          selectedFile.path,
          content,
        );
      } else {
        await api[collectionType === 'scripts' ? 'updateScript' : 'updateSkill'](
          workspaceRuntime.runtimeBaseUrl,
          workspaceRuntime.workspaceId,
          selectedFile.path,
          { content },
          selectedFile.scope as 'project' | 'user'
        );
      }
    } catch (error) {
      logger.error('Failed to save file', { error });
      throw error;
    } finally {
      setIsSaving(false);
    }
  };

  const isPluginFile = selectedFile?.scope === 'plugin';
  const fileName = selectedFile?.path.split('/').pop() || '';
  const FileIcon = collectionType === 'scripts' ? ScrollText : Wand2;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <FeatureHeader
        title={t(`${i18nNamespace}.${collectionType}.header.title`)}
        icon={FileIcon}
      />

      <div className="flex-1 overflow-hidden border-t border-border bg-background">
        {!selectedFile ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t(`${i18nNamespace}.${collectionType}.noSelection`)}
          </div>
        ) : (
          <div className="flex h-full flex-col">
            {apiPrefix === 'codex' && codexResourceQuery.data?.config && Object.keys(codexResourceQuery.data.config).length > 0 ? (
              <pre className="max-h-28 overflow-auto border-b border-border bg-muted/40 p-3 text-xs">
                {JSON.stringify(codexResourceQuery.data.config, null, 2)}
              </pre>
            ) : null}
            <div className="min-h-0 flex-1">
              <FileEditor
                key={selectedFile.path}
                fileName={fileName}
                filePath={selectedFile.path}
                fileContent={fileContent}
                fileIcon={<FileIcon className="h-4 w-4 text-purple-600 dark:text-purple-400" />}
                readOnly={isPluginFile}
                onSave={handleSaveFile}
                isLoading={isLoadingFile}
                isSaving={isSaving}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SkillsPage;
