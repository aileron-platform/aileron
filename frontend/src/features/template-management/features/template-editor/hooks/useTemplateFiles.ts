import { useState, useEffect } from 'react';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  getSlashCommandsFiles,
  getSlashCommandFile,
  createSlashCommandFile,
  updateSlashCommandFile,
  deleteSlashCommandFile,
  getSubAgentsFiles,
  getSubAgentFile,
  createSubAgentFile,
  updateSubAgentFile,
  deleteSubAgentFile,
} from '@/shared/services/templateApi';
import type { SlashCommandFormValue, SubAgentFormValue } from '../formTypes';
import { useI18n } from '@/shared/hooks/useI18n';

const generateLocalId = () => `local-${Math.random().toString(36).slice(2, 10)}`;

export const useTemplateFiles = (templateId: string) => {
  const { t } = useI18n();
  const { toast } = useToast();

  // SlashCommands 狀態
  const [slashCommands, setSlashCommands] = useState<SlashCommandFormValue[]>([]);
  const [slashCommandsLoading, setSlashCommandsLoading] = useState(false);
  const [slashCommandsError, setSlashCommandsError] = useState<string | null>(null);

  // SubAgents 狀態
  const [subAgents, setSubAgents] = useState<SubAgentFormValue[]>([]);
  const [subAgentsLoading, setSubAgentsLoading] = useState(false);
  const [subAgentsError, setSubAgentsError] = useState<string | null>(null);

  // 載入 SlashCommands 檔案列表
  const loadSlashCommands = async () => {
    if (!templateId) return;

    setSlashCommandsLoading(true);
    setSlashCommandsError(null);

    try {
      const response = await getSlashCommandsFiles(templateId);
      if (response.success && response.data) {
        const commands = response.data.map(file => ({
          localId: generateLocalId(),
          fileName: file.fileName,
          content: '', // 需要另外載入
          size: file.size,
          lastModified: file.lastModified,
        }));
        setSlashCommands(commands);
      } else {
        setSlashCommandsError(response.error || t('common.template.errors.loadFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.loadFailed');
      setSlashCommandsError(errorMessage);
      toast({
        title: t('common.template.errors.loadFailed'),
        description: '無法載入 Slash Commands 檔案列表。',
        variant: 'destructive',
      });
    } finally {
      setSlashCommandsLoading(false);
    }
  };

  // 載入 SubAgents 檔案列表
  const loadSubAgents = async () => {
    if (!templateId) return;

    setSubAgentsLoading(true);
    setSubAgentsError(null);

    try {
      const response = await getSubAgentsFiles(templateId);
      if (response.success && response.data) {
        const agents = response.data.map(file => ({
          localId: generateLocalId(),
          fileName: file.fileName,
          content: '', // 需要另外載入
          size: file.size,
          lastModified: file.lastModified,
        }));
        setSubAgents(agents);
      } else {
        setSubAgentsError(response.error || t('common.template.errors.loadFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.loadFailed');
      setSubAgentsError(errorMessage);
      toast({
        title: t('common.template.errors.loadFailed'),
        description: '無法載入 SubAgents 檔案列表。',
        variant: 'destructive',
      });
    } finally {
      setSubAgentsLoading(false);
    }
  };

  // 載入特定 SlashCommand 檔案內容
  const loadSlashCommandContent = async (fileName: string): Promise<string> => {
    if (!templateId) return '';

    try {
      const response = await getSlashCommandFile(templateId, fileName);
      if (response.success && response.data) {
        return response.data.content;
      } else {
        throw new Error(response.error || '載入檔案內容失敗');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '載入檔案內容失敗';
      toast({
        title: t('common.template.errors.loadFailed'),
        description: `無法載入 Slash Command「${fileName}」的內容。`,
        variant: 'destructive',
      });
      throw error;
    }
  };

  // 載入特定 SubAgent 檔案內容
  const loadSubAgentContent = async (fileName: string): Promise<string> => {
    if (!templateId) return '';

    try {
      const response = await getSubAgentFile(templateId, fileName);
      if (response.success && response.data) {
        return response.data.content;
      } else {
        throw new Error(response.error || '載入檔案內容失敗');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '載入檔案內容失敗';
      toast({
        title: t('common.template.errors.loadFailed'),
        description: `無法載入 SubAgent「${fileName}」的內容。`,
        variant: 'destructive',
      });
      throw error;
    }
  };

  // 建立 SlashCommand 檔案
  const createSlashCommand = async (fileName: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await createSlashCommandFile(templateId, { fileName, content });
      if (response.success) {
        const newCommand: SlashCommandFormValue = {
          localId: generateLocalId(),
          fileName,
          content,
          size: response.data?.size || content.length,
          lastModified: response.data?.lastModified || new Date().toISOString(),
        };
        setSlashCommands(prev => [...prev, newCommand]);

        toast({
          title: '建立成功',
          description: `Slash Command「${fileName}」已建立。`,
        });

        return true;
      } else {
        throw new Error(response.error || t('common.template.errors.createFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.createFailed');
      toast({
        title: t('common.template.errors.createFailed'),
        description: `無法建立 Slash Command「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 更新 SlashCommand 檔案
  const updateSlashCommand = async (fileName: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await updateSlashCommandFile(templateId, fileName, { content });
      if (response.success) {
        setSlashCommands(prev =>
          prev.map(cmd =>
            cmd.fileName === fileName
              ? {
                  ...cmd,
                  content,
                  size: response.data?.size || content.length,
                  lastModified: response.data?.lastModified || new Date().toISOString(),
                }
              : cmd
          )
        );

        toast({
          title: '更新成功',
          description: `Slash Command「${fileName}」已更新。`,
        });

        return true;
      } else {
        throw new Error(response.error || t('common.template.errors.updateFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.updateFailed');
      toast({
        title: t('common.template.errors.updateFailed'),
        description: `無法更新 Slash Command「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 刪除 SlashCommand 檔案
  const deleteSlashCommand = async (fileName: string) => {
    if (!templateId) return false;

    try {
      await deleteSlashCommandFile(templateId, fileName);
      setSlashCommands(prev => prev.filter(cmd => cmd.fileName !== fileName));

      toast({
        title: '刪除成功',
        description: `Slash Command「${fileName}」已刪除。`,
      });

      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.deleteFailed');
      toast({
        title: t('common.template.errors.deleteFailed'),
        description: `無法刪除 Slash Command「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 建立 SubAgent 檔案
  const createSubAgent = async (fileName: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await createSubAgentFile(templateId, { fileName, content });
      if (response.success) {
        const newAgent: SubAgentFormValue = {
          localId: generateLocalId(),
          fileName,
          content,
          size: response.data?.size || content.length,
          lastModified: response.data?.lastModified || new Date().toISOString(),
        };
        setSubAgents(prev => [...prev, newAgent]);

        toast({
          title: '建立成功',
          description: `SubAgent「${fileName}」已建立。`,
        });

        return true;
      } else {
        throw new Error(response.error || t('common.template.errors.createFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.createFailed');
      toast({
        title: t('common.template.errors.createFailed'),
        description: `無法建立 SubAgent「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 更新 SubAgent 檔案
  const updateSubAgent = async (fileName: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await updateSubAgentFile(templateId, fileName, { content });
      if (response.success) {
        setSubAgents(prev =>
          prev.map(agent =>
            agent.fileName === fileName
              ? {
                  ...agent,
                  content,
                  size: response.data?.size || content.length,
                  lastModified: response.data?.lastModified || new Date().toISOString(),
                }
              : agent
          )
        );

        toast({
          title: '更新成功',
          description: `SubAgent「${fileName}」已更新。`,
        });

        return true;
      } else {
        throw new Error(response.error || t('common.template.errors.updateFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.updateFailed');
      toast({
        title: t('common.template.errors.updateFailed'),
        description: `無法更新 SubAgent「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 刪除 SubAgent 檔案
  const deleteSubAgent = async (fileName: string) => {
    if (!templateId) return false;

    try {
      await deleteSubAgentFile(templateId, fileName);
      setSubAgents(prev => prev.filter(agent => agent.fileName !== fileName));

      toast({
        title: '刪除成功',
        description: `SubAgent「${fileName}」已刪除。`,
      });

      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.deleteFailed');
      toast({
        title: t('common.template.errors.deleteFailed'),
        description: `無法刪除 SubAgent「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 初始化載入
  useEffect(() => {
    if (templateId) {
      loadSlashCommands();
      loadSubAgents();
    }
  }, [templateId]);

  return {
    // SlashCommands
    slashCommands,
    slashCommandsLoading,
    slashCommandsError,
    loadSlashCommands,
    loadSlashCommandContent,
    createSlashCommand,
    updateSlashCommand,
    deleteSlashCommand,

    // SubAgents
    subAgents,
    subAgentsLoading,
    subAgentsError,
    loadSubAgents,
    loadSubAgentContent,
    createSubAgent,
    updateSubAgent,
    deleteSubAgent,
  };
};