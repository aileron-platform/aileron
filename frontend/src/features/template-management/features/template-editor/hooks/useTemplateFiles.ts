import { useState, useEffect } from 'react';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  getCommandsFiles,
  getCommandFile,
  createCommandFile,
  updateCommandFile,
  deleteCommandFile,
  getAgentsFiles,
  getAgentFile,
  createAgentFile,
  updateAgentFile,
  deleteAgentFile,
} from '@/shared/services/templateApi';
import type { CommandFormValue, AgentFormValue } from '../formTypes';
import { useI18n } from '@/shared/hooks/useI18n';

const generateLocalId = () => `local-${Math.random().toString(36).slice(2, 10)}`;

export const useTemplateFiles = (templateId: string) => {
  const { t } = useI18n();
  const { toast } = useToast();

  // Commands 狀態
  const [commands, setCommands] = useState<CommandFormValue[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);
  const [commandsError, setCommandsError] = useState<string | null>(null);

  // Agents 狀態
  const [agents, setAgents] = useState<AgentFormValue[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState<string | null>(null);

  // 載入 Commands 檔案列表
  const loadCommands = async () => {
    if (!templateId) return;

    setCommandsLoading(true);
    setCommandsError(null);

    try {
      const response = await getCommandsFiles(templateId);
      if (response.success && response.data) {
        const commands = response.data.map(file => ({
          localId: generateLocalId(),
          fileName: file.fileName,
          content: '', // 需要另外載入
          size: file.size,
          lastModified: file.lastModified,
        }));
        setCommands(commands);
      } else {
        setCommandsError(response.error || t('common.template.errors.loadFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.loadFailed');
      setCommandsError(errorMessage);
      toast({
        title: t('common.template.errors.loadFailed'),
        description: t('template.editor.commands.sidebar.empty'),
        variant: 'destructive',
      });
    } finally {
      setCommandsLoading(false);
    }
  };

  // 載入 Agents 檔案列表
  const loadAgents = async () => {
    if (!templateId) return;

    setAgentsLoading(true);
    setAgentsError(null);

    try {
      const response = await getAgentsFiles(templateId);
      if (response.success && response.data) {
        const agents = response.data.map(file => ({
          localId: generateLocalId(),
          fileName: file.fileName,
          content: '', // 需要另外載入
          size: file.size,
          lastModified: file.lastModified,
        }));
        setAgents(agents);
      } else {
        setAgentsError(response.error || t('common.template.errors.loadFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.loadFailed');
      setAgentsError(errorMessage);
      toast({
        title: t('common.template.errors.loadFailed'),
        description: t('template.editor.agents.sidebar.empty'),
        variant: 'destructive',
      });
    } finally {
      setAgentsLoading(false);
    }
  };

  // 載入特定 Command 檔案內容
  const loadCommandContent = async (fileName: string): Promise<string> => {
    if (!templateId) return '';

    try {
      const response = await getCommandFile(templateId, fileName);
      if (response.success && response.data) {
        return response.data.content;
      } else {
        throw new Error(response.error || t('common.template.errors.loadFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.loadFailed');
      toast({
        title: t('common.template.errors.loadFailed'),
        description: `${t('template.common.features.commands')}「${fileName}」${t('common.template.errors.loadFailed')}`,
        variant: 'destructive',
      });
      throw error;
    }
  };

  // 載入特定 Agent 檔案內容
  const loadAgentContent = async (fileName: string): Promise<string> => {
    if (!templateId) return '';

    try {
      const response = await getAgentFile(templateId, fileName);
      if (response.success && response.data) {
        return response.data.content;
      } else {
        throw new Error(response.error || t('common.template.errors.loadFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.loadFailed');
      toast({
        title: t('common.template.errors.loadFailed'),
        description: `${t('template.common.features.agents')}「${fileName}」${t('common.template.errors.loadFailed')}`,
        variant: 'destructive',
      });
      throw error;
    }
  };

  // 建立 Command 檔案
  const createCommand = async (fileName: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await createCommandFile(templateId, { fileName, content });
      if (response.success) {
        const newCommand: CommandFormValue = {
          localId: generateLocalId(),
          fileName,
          content,
          size: response.data?.size || content.length,
          lastModified: response.data?.lastModified || new Date().toISOString(),
        };
        setCommands(prev => [...prev, newCommand]);

        toast({
          title: t('template.editor.commands.dialog.actions.create'),
          description: t('template.detail.commands.empty.title') + `：${fileName}`,
        });

        return true;
      } else {
        throw new Error(response.error || t('common.template.errors.createFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.createFailed');
      toast({
        title: t('common.template.errors.createFailed'),
        description: `${t('template.common.features.commands')}「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 更新 Command 檔案
  const updateCommand = async (fileName: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await updateCommandFile(templateId, fileName, { content });
      if (response.success) {
        setCommands(prev =>
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
          title: t('template.editor.commands.dialog.actions.save'),
          description: `${t('template.common.features.commands')}「${fileName}」已更新。`,
        });

        return true;
      } else {
        throw new Error(response.error || t('common.template.errors.updateFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.updateFailed');
      toast({
        title: t('common.template.errors.updateFailed'),
        description: `${t('template.common.features.commands')}「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 刪除 Command 檔案
  const deleteCommand = async (fileName: string) => {
    if (!templateId) return false;

    try {
      await deleteCommandFile(templateId, fileName);
      setCommands(prev => prev.filter(cmd => cmd.fileName !== fileName));

      toast({
        title: t('common.delete'),
        description: `${t('template.common.features.commands')}「${fileName}」已刪除。`,
      });

      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.deleteFailed');
      toast({
        title: t('common.template.errors.deleteFailed'),
        description: `${t('template.common.features.commands')}「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 建立 Agent 檔案
  const createAgent = async (fileName: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await createAgentFile(templateId, { fileName, content });
      if (response.success) {
        const newAgent: AgentFormValue = {
          localId: generateLocalId(),
          fileName,
          content,
          size: response.data?.size || content.length,
          lastModified: response.data?.lastModified || new Date().toISOString(),
        };
        setAgents(prev => [...prev, newAgent]);

        toast({
          title: t('template.editor.agents.dialog.actions.create'),
          description: t('template.editor.agents.toasts.createSuccess.description', { name: fileName }),
        });

        return true;
      } else {
        throw new Error(response.error || t('common.template.errors.createFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.createFailed');
      toast({
        title: t('common.template.errors.createFailed'),
        description: `${t('template.common.features.agents')}「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 更新 Agent 檔案
  const updateAgent = async (fileName: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await updateAgentFile(templateId, fileName, { content });
      if (response.success) {
        setAgents(prev =>
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
          title: t('template.editor.agents.dialog.actions.save'),
          description: t('template.editor.agents.toasts.updateSuccess.description', { name: fileName }),
        });

        return true;
      } else {
        throw new Error(response.error || t('common.template.errors.updateFailed'));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.updateFailed');
      toast({
        title: t('common.template.errors.updateFailed'),
        description: `${t('template.common.features.agents')}「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 刪除 Agent 檔案
  const deleteAgent = async (fileName: string) => {
    if (!templateId) return false;

    try {
      await deleteAgentFile(templateId, fileName);
      setAgents(prev => prev.filter(agent => agent.fileName !== fileName));

      toast({
        title: t('common.delete'),
        description: t('template.editor.agents.toasts.deleteSuccess.description', { name: fileName }),
      });

      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.template.errors.deleteFailed');
      toast({
        title: t('common.template.errors.deleteFailed'),
        description: `${t('template.common.features.agents')}「${fileName}」：${errorMessage}`,
        variant: 'destructive',
      });
      return false;
    }
  };

  // 初始化載入
  useEffect(() => {
    if (templateId) {
      loadCommands();
      loadAgents();
    }
  }, [templateId]);

  return {
    // Commands
    commands,
    commandsLoading,
    commandsError,
    loadCommands,
    loadCommandContent,
    createCommand,
    updateCommand,
    deleteCommand,

    // Agents
    agents,
    agentsLoading,
    agentsError,
    loadAgents,
    loadAgentContent,
    createAgent,
    updateAgent,
    deleteAgent,
  };
};
