/**
 * Template API Hook
 * 模板 API 操作 Hook
 */

import { useState, useCallback } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useTemplateApi');
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import * as templateApi from '@/shared/services/templateApi';
import type { TemplateFormValues, McpServerFormValue, HookFormValue, SlashCommandFormValue, SubAgentFormValue, OutputStyleFormValue } from '../formTypes';
import { parseArgsText, parseEnvText, parseHeadersText } from '../formTypes';


export interface UseTemplateApiOptions {
  templateId?: string;
  onSuccess?: () => void;
}

export function useTemplateApi(options: UseTemplateApiOptions = {}) {
  const { templateId, onSuccess } = options;
  const { toast } = useToast();
  const { t } = useI18n();
  const [isSaving, setIsSaving] = useState(false);

  /**
   * 儲存基本資訊
   */
  const saveBasicInfo = useCallback(
    async (values: TemplateFormValues) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: '模板 ID 不存在',
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);
        await templateApi.updateTemplate(templateId, {
          name: values.name,
          description: values.description,
          version: values.version,
          author: {
            name: values.authorName,
            email: values.authorEmail || undefined,
            url: values.authorUrl || undefined,
          },
          keywords: values.keywords,
          categoryId: values.categoryId,
          initCommands: values.initCommands || undefined,
        });

        toast({
          title: t('template.editor.toasts.saveSuccess.title'),
          description: t('template.editor.toasts.saveSuccess.description'),
          variant: 'success',
        });

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveBasicInfo failed', { error });
        toast({
          title: t('template.editor.toasts.saveFailed.title'),
          description: t('template.editor.toasts.saveFailed.description'),
          variant: 'destructive',
        });
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [templateId, toast, t, onSuccess]
  );

  /**
   * 儲存 MCP 配置
   */
  const saveMcpConfig = useCallback(
    async (servers: McpServerFormValue[]) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: '模板 ID 不存在',
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);

        // 轉換格式
        const mcpServers: Record<string, templateApi.McpServer> = {};
        servers.forEach((server) => {
          const args = parseArgsText(server.argsText);
          const env = parseEnvText(server.envText);
          const headers = parseHeadersText(server.headersText);

          mcpServers[server.name] = {
            description: server.description,
            type: server.type,
            command: server.command || undefined,
            args: args.length > 0 ? args : undefined,
            env,
            url: server.url || undefined,
            headers,
          };
        });

        await templateApi.updateMcpConfig(templateId, { mcpServers });

        toast({
          title: t('template.editor.toasts.saveSuccess.title'),
          description: 'MCP 配置已儲存',
          variant: 'success',
        });

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveMcpConfig failed', { error });
        toast({
          title: t('template.editor.toasts.saveFailed.title'),
          description: 'MCP 配置儲存失敗',
          variant: 'destructive',
        });
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [templateId, toast, t, onSuccess]
  );

  /**
   * 儲存 Hooks 配置
   */
  const saveHooksConfig = useCallback(
    async (hooks: HookFormValue[]) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: '模板 ID 不存在',
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);

        // 轉換格式：按事件類型分組
        const hooksConfig: Record<string, templateApi.HookRule[]> = {};
        hooks.forEach((hook) => {
          if (!hooksConfig[hook.event]) {
            hooksConfig[hook.event] = [];
          }

          // 對於每個匹配器，創建一個HookRule
          hook.matchers.forEach((matcher) => {
            hooksConfig[hook.event].push({
              matcher: matcher.matcher || '*', // 如果沒有匹配器，默認為 "*"
              hooks: matcher.hooks.map((exec) => ({
                type: exec.type as 'command', // 使用原本的類型
                command: exec.command || undefined,
                timeout: exec.timeout || undefined,
              })),
            });
          });
        });

        await templateApi.updateHooksConfig(templateId, { hooks: hooksConfig });

        toast({
          title: t('template.editor.toasts.saveSuccess.title'),
          description: 'Hooks 配置已儲存',
          variant: 'success',
        });

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveHooksConfig failed', { error });
        toast({
          title: t('template.editor.toasts.saveFailed.title'),
          description: 'Hooks 配置儲存失敗',
          variant: 'destructive',
        });
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [templateId, toast, t, onSuccess]
  );

  const loadTemplateFiles = useCallback(
    async <TFormValue>(
      listFetcher: (templateId: string) => Promise<templateApi.TemplateFileListResponse>,
      contentFetcher: (
        templateId: string,
        fileName: string
      ) => Promise<templateApi.TemplateFileResponse>,
      transform: (
        file: templateApi.TemplateFile,
        content: templateApi.TemplateFileContent
      ) => TFormValue,
      logContext: { label: string; slug: string }
    ): Promise<TFormValue[]> => {
      if (!templateId) {
        return [];
      }

      try {
        const response = await listFetcher(templateId);
        if (!response.success || !response.data) {
          logger.warn(`Failed to load ${logContext.label} files`, { error: response.error });
          return [];
        }

        const items: TFormValue[] = [];
        for (const file of response.data) {
          try {
            const fileResponse = await contentFetcher(templateId, file.file_name);
            if (fileResponse.success && fileResponse.data) {
              items.push(transform(file, fileResponse.data));
            }
          } catch (error) {
            logger.error(`Failed to load content for ${logContext.label} ${file.file_name}`, { error });
          }
        }

        return items;
      } catch (error) {
        logger.error(`load${logContext.slug} failed`, { error });
        return [];
      }
    },
    [templateId]
  );

  /**
   * 載入 Slash Commands 配置
   */
  const loadSlashCommands = useCallback(
    () =>
      loadTemplateFiles<SlashCommandFormValue>(
        templateApi.getSlashCommandsFiles,
        templateApi.getSlashCommandFile,
        (file, content) => ({
          localId: `local-${file.file_name}`,
          fileName: file.file_name,
          content: content.content,
          description: file.file_name.replace('.md', ''),
          size: file.size,
          lastModified: file.last_modified,
        }),
        { label: 'slash commands', slug: 'SlashCommands' }
      ),
    [loadTemplateFiles]
  );

  /**
   * 儲存 Slash Commands 配置
   */
  const saveSlashCommands = useCallback(
    async (slashCommands: SlashCommandFormValue[], existingCommands: SlashCommandFormValue[] = []) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: '模板 ID 不存在',
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);

        const existingFileNames = new Set(existingCommands.map(cmd => cmd.fileName));
        const newCommands = slashCommands.filter(cmd => !existingFileNames.has(cmd.fileName));
        const existingCommandsMap = new Map(existingCommands.map(cmd => [cmd.fileName, cmd]));
        const updatedCommands = slashCommands.filter(cmd => {
          const existing = existingCommandsMap.get(cmd.fileName);
          return existing && cmd.content !== existing.content;
        });

        // 逐個儲存新的 Slash Command 檔案
        for (const command of newCommands) {
          await templateApi.createSlashCommandFile(templateId, {
            file_name: command.fileName,
            content: command.content,
          });
        }

        // 逐個更新現有的 Slash Command 檔案
        for (const command of updatedCommands) {
          await templateApi.updateSlashCommandFile(templateId, command.fileName, {
            content: command.content,
          });
        }

        if (newCommands.length > 0 || updatedCommands.length > 0) {
          toast({
            title: t('template.editor.toasts.saveSuccess.title'),
            description: `已儲存 ${newCommands.length} 個新的，更新 ${updatedCommands.length} 個 Slash Command`,
            variant: 'success',
          });
        }

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveSlashCommands failed', { error });

        // 檢查是否為認證錯誤
        let errorMessage = 'Slash Commands 配置儲存失敗';
        if (error instanceof Error && error.message.includes('401')) {
          errorMessage = '認證失敗，請重新登入';
        } else if (error instanceof Error && error.message.includes('403')) {
          errorMessage = '權限不足，無法儲存 Slash Commands';
        }

        toast({
          title: t('template.editor.toasts.saveFailed.title'),
          description: errorMessage,
          variant: 'destructive',
        });
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [templateId, toast, t, onSuccess]
  );

  /**
   * 載入 SubAgents 配置
   */
  const loadSubAgents = useCallback(
    () =>
      loadTemplateFiles<SubAgentFormValue>(
        templateApi.getSubAgentsFiles,
        templateApi.getSubAgentFile,
        (file, content) => ({
          localId: `local-${file.file_name}`,
          fileName: file.file_name,
          content: content.content,
          description: file.file_name.replace('.md', ''),
          size: file.size,
          lastModified: file.last_modified,
        }),
        { label: 'subagents', slug: 'SubAgents' }
      ),
    [loadTemplateFiles]
  );

  /**
   * 儲存 SubAgents 配置
   */
  const saveSubAgents = useCallback(
    async (subAgents: SubAgentFormValue[], existingSubAgents: SubAgentFormValue[] = []) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: '模板 ID 不存在',
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);

        const existingFileNames = new Set(existingSubAgents.map(agent => agent.fileName));
        const newSubAgents = subAgents.filter(agent => !existingFileNames.has(agent.fileName));
        const existingSubAgentsMap = new Map(existingSubAgents.map(agent => [agent.fileName, agent]));
        const updatedSubAgents = subAgents.filter(agent => {
          const existing = existingSubAgentsMap.get(agent.fileName);
          return existing && agent.content !== existing.content;
        });

        // 逐個儲存新的 SubAgent 檔案
        for (const agent of newSubAgents) {
          await templateApi.createSubAgentFile(templateId, {
            file_name: agent.fileName,
            content: agent.content,
          });
        }

        // 逐個更新現有的 SubAgent 檔案
        for (const agent of updatedSubAgents) {
          await templateApi.updateSubAgentFile(templateId, agent.fileName, {
            content: agent.content,
          });
        }

        if (newSubAgents.length > 0 || updatedSubAgents.length > 0) {
          toast({
            title: t('template.editor.toasts.saveSuccess.title'),
            description: `已儲存 ${newSubAgents.length} 個新的，更新 ${updatedSubAgents.length} 個 SubAgent`,
            variant: 'success',
          });
        }

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveSubAgents failed', { error });

        // 檢查是否為認證錯誤
        let errorMessage = 'SubAgents 配置儲存失敗';
        if (error instanceof Error && error.message.includes('401')) {
          errorMessage = '認證失敗，請重新登入';
        } else if (error instanceof Error && error.message.includes('403')) {
          errorMessage = '權限不足，無法儲存 SubAgents';
        }

        toast({
          title: t('template.editor.toasts.saveFailed.title'),
          description: errorMessage,
          variant: 'destructive',
        });
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [templateId, toast, t, onSuccess]
  );

  /**
   * 載入 OutputStyles 配置
   */
  const loadOutputStyles = useCallback(
    () =>
      loadTemplateFiles<OutputStyleFormValue>(
        templateApi.getOutputStylesFiles,
        templateApi.getOutputStyleFile,
        (file, content) => ({
          localId: `local-${file.file_name}`,
          fileName: file.file_name,
          content: content.content,
          description: file.file_name.replace('.md', ''),
          size: file.size,
          lastModified: file.last_modified,
        }),
        { label: 'output-styles', slug: 'OutputStyles' }
      ),
    [loadTemplateFiles]
  );

  /**
   * 儲存 OutputStyles 配置
   */
  const saveOutputStyles = useCallback(
    async (outputStyles: OutputStyleFormValue[], existingOutputStyles: OutputStyleFormValue[] = []) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: '模板 ID 不存在',
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);

        const existingFileNames = new Set(existingOutputStyles.map(style => style.fileName));
        const newOutputStyles = outputStyles.filter(style => !existingFileNames.has(style.fileName));
        const existingOutputStylesMap = new Map(existingOutputStyles.map(style => [style.fileName, style]));
        const updatedOutputStyles = outputStyles.filter(style => {
          const existing = existingOutputStylesMap.get(style.fileName);
          return existing && style.content !== existing.content;
        });

        // 逐個儲存新的 OutputStyle 檔案
        for (const style of newOutputStyles) {
          await templateApi.createOutputStyleFile(templateId, {
            file_name: style.fileName,
            content: style.content,
          });
        }

        // 逐個更新現有的 OutputStyle 檔案
        for (const style of updatedOutputStyles) {
          await templateApi.updateOutputStyleFile(templateId, style.fileName, {
            content: style.content,
          });
        }

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveOutputStyles failed', { error });

        // 檢查是否為認證錯誤
        let errorMessage = 'OutputStyles 配置儲存失敗';
        if (error instanceof Error && error.message.includes('401')) {
          errorMessage = '認證失敗，請重新登入';
        } else if (error instanceof Error && error.message.includes('403')) {
          errorMessage = '權限不足，無法儲存 OutputStyles';
        }

        toast({
          title: t('template.editor.toasts.saveFailed.title'),
          description: errorMessage,
          variant: 'destructive',
        });
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [templateId, toast, t, onSuccess]
  );

  return {
    isSaving,
    saveBasicInfo,
    saveMcpConfig,
    saveHooksConfig,
    saveSlashCommands,
    saveSubAgents,
    saveOutputStyles,
    loadSlashCommands,
    loadSubAgents,
    loadOutputStyles,
  };
}
