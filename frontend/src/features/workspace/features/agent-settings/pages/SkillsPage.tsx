import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  FileViewerWorkbench,
  type FileViewerWorkbenchAdapter,
  type FileViewerWorkbenchTab,
} from '@/shared/components/file-workbench/viewer-entry';
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
  onSelect?: (file: AgentSelectedFile | null) => void;
}

const buildTabKey = (file: AgentSelectedFile): string => (
  `${file.scope}|${file.pluginId ?? ''}|${file.path}`
);

const fileBasename = (path: string): string => path.split('/').pop() || path;

const SkillsPage: React.FC<SkillsPageProps> = ({
  selectedFile,
  apiPrefix = 'claude-code',
  i18nNamespace = 'workspace.agentSettings.common',
  collectionType = 'skills',
  onSelect,
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const [openFiles, setOpenFiles] = useState<AgentSelectedFile[]>([]);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [contents, setContents] = useState<Record<string, string>>({});
  const [originalContents, setOriginalContents] = useState<Record<string, string>>({});
  const [loadingKeys, setLoadingKeys] = useState<string[]>([]);
  const [savingKeys, setSavingKeys] = useState<string[]>([]);

  const openFilesRef = useRef(openFiles);
  useEffect(() => {
    openFilesRef.current = openFiles;
  }, [openFiles]);

  const findFileByKey = useCallback((key: string): AgentSelectedFile | undefined => (
    openFilesRef.current.find(file => buildTabKey(file) === key)
  ), []);

  const loadFileContent = useCallback(async (file: AgentSelectedFile) => {
    const key = buildTabKey(file);
    setLoadingKeys(prev => (prev.includes(key) ? prev : [...prev, key]));
    try {
      const response = apiPrefix === 'codex'
        ? await api.getCodexFile(
          workspaceRuntime.runtimeBaseUrl,
          workspaceRuntime.workspaceId,
          collectionType,
          file.scope === 'plugin' ? 'plugin' : file.scope === 'user' ? 'user' : 'project',
          file.path,
          file.pluginId,
        )
        : await api[collectionType === 'scripts' ? 'getScript' : 'getSkill'](
          workspaceRuntime.runtimeBaseUrl,
          workspaceRuntime.workspaceId,
          file.path,
          file.scope,
        );
      const content = response.content || '';
      setContents(prev => ({ ...prev, [key]: content }));
      setOriginalContents(prev => ({ ...prev, [key]: content }));
    } catch (error) {
      logger.error('Failed to load file', { error });
      setContents(prev => ({ ...prev, [key]: '' }));
      setOriginalContents(prev => ({ ...prev, [key]: '' }));
    } finally {
      setLoadingKeys(prev => prev.filter(item => item !== key));
    }
  }, [api, apiPrefix, collectionType, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const lastProcessedSelectionKey = useRef<string | null>(null);

  useEffect(() => {
    if (!selectedFile) {
      lastProcessedSelectionKey.current = null;
      return;
    }
    const key = buildTabKey(selectedFile);
    if (lastProcessedSelectionKey.current === key) return;
    lastProcessedSelectionKey.current = key;
    setOpenFiles(prev => {
      if (prev.some(file => buildTabKey(file) === key)) {
        return prev;
      }
      return [...prev, selectedFile];
    });
    setActiveKey(key);
    if (originalContents[key] === undefined) {
      void loadFileContent(selectedFile);
    }
  }, [loadFileContent, originalContents, selectedFile]);

  const saveFile = useCallback(async (file: AgentSelectedFile, content: string) => {
    if (apiPrefix === 'codex') {
      await api.updateCodexFile(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        collectionType,
        file.scope === 'user' ? 'user' : 'project',
        file.path,
        content,
      );
    } else {
      await api[collectionType === 'scripts' ? 'updateScript' : 'updateSkill'](
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        file.path,
        { content },
        file.scope as 'project' | 'user',
      );
    }
  }, [api, apiPrefix, collectionType, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const adapter = useMemo<FileViewerWorkbenchAdapter>(() => ({
    readFile: async (key) => contents[key] ?? '',
    saveFile: async (key, content) => {
      const file = findFileByKey(key);
      if (!file) return;
      if (file.scope === 'plugin' || file.scope === 'extension') return;
      setSavingKeys(prev => (prev.includes(key) ? prev : [...prev, key]));
      try {
        await saveFile(file, content);
        setContents(prev => ({ ...prev, [key]: content }));
        setOriginalContents(prev => ({ ...prev, [key]: content }));
      } catch (error) {
        logger.error('Failed to save file', { error });
        throw error;
      } finally {
        setSavingKeys(prev => prev.filter(item => item !== key));
      }
    },
  }), [contents, findFileByKey, saveFile]);

  const tabs = useMemo<FileViewerWorkbenchTab[]>(() => openFiles.map(file => {
    const key = buildTabKey(file);
    const content = contents[key] ?? '';
    const original = originalContents[key] ?? '';
    return {
      id: key,
      path: key,
      name: fileBasename(file.path),
      content,
      originalContent: original,
      isModified: content !== original,
      isLoading: loadingKeys.includes(key),
    };
  }), [contents, loadingKeys, openFiles, originalContents]);

  const isPathWritable = useCallback((key: string): boolean => {
    const file = findFileByKey(key);
    if (!file) return false;
    return !(file.scope === 'plugin' || file.scope === 'extension');
  }, [findFileByKey]);

  const handleTabsChange = useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    const nextKeys = new Set(nextTabs.map(tab => tab.id));
    setOpenFiles(prev => prev.filter(file => nextKeys.has(buildTabKey(file))));
    setContents(prev => {
      const next: Record<string, string> = {};
      nextTabs.forEach(tab => {
        next[tab.id] = tab.content;
      });
      Object.entries(prev).forEach(([key, value]) => {
        if (next[key] === undefined && nextKeys.has(key)) {
          next[key] = value;
        }
      });
      return next;
    });
    setOriginalContents(prev => {
      const next: Record<string, string> = {};
      Object.entries(prev).forEach(([key, value]) => {
        if (nextKeys.has(key)) {
          next[key] = value;
        }
      });
      nextTabs.forEach(tab => {
        if (next[tab.id] === undefined) {
          next[tab.id] = tab.originalContent;
        }
      });
      return next;
    });
  }, []);

  const handleActiveTabChange = useCallback((nextKey: string | null) => {
    setActiveKey(nextKey);
    if (!onSelect) return;
    if (!nextKey) {
      onSelect(null);
      return;
    }
    const file = findFileByKey(nextKey);
    if (file) onSelect(file);
  }, [findFileByKey, onSelect]);

  const activeFile = activeKey ? findFileByKey(activeKey) : undefined;
  const isSavingActive = activeKey ? savingKeys.includes(activeKey) : false;
  const canSaveActive = activeFile ? !(activeFile.scope === 'plugin' || activeFile.scope === 'extension') : false;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex-1 overflow-hidden bg-background">
        {tabs.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t(`${i18nNamespace}.${collectionType}.noSelection`)}
          </div>
        ) : (
          <FileViewerWorkbench
            tabs={tabs}
            activeTabId={activeKey}
            adapter={adapter}
            capabilities={{
              canEdit: !isSavingActive,
              canSave: canSaveActive && !isSavingActive,
              canCopyPath: false,
              canRevealInTree: false,
              canCloseTabs: true,
            }}
            isPathWritable={isPathWritable}
            onTabsChange={handleTabsChange}
            onActiveTabChange={handleActiveTabChange}
          />
        )}
      </div>
    </div>
  );
};

export default SkillsPage;
