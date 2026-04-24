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
import type { TemplateFormValues, McpServerFormValue, HookFormValue, CommandFormValue, AgentFormValue, OutputStyleFormValue } from '../formTypes';
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
          description: t('template.editor.toasts.error.description'),
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

  const saveCanonicalTemplate = useCallback(
    async (values: TemplateFormValues) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: t('template.editor.toasts.error.description'),
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);
        await templateApi.updateCanonicalTemplate(templateId, {
          name: values.name,
          description: values.description,
          version: values.version,
          author: {
            name: values.authorName,
            email: values.authorEmail || undefined,
            url: values.authorUrl || undefined,
          },
          keywords: values.keywords,
          categoryId: values.categoryId || undefined,
          documentation: values.documentation || undefined,
          agentsMd: values.agentsMd || undefined,
          initCommands: values.initCommands || undefined,
          mcpServers: values.mcpServers.map(item => ({
            id: item.localId,
            name: item.name,
            type: item.type,
            command: item.command || undefined,
            args: parseArgsText(item.argsText),
            url: item.url || undefined,
            description: item.description || undefined,
            env: parseEnvText(item.envText),
            headers: parseHeadersText(item.headersText),
          })),
          commands: values.commands.map(item => ({
            id: item.localId,
            fileName: item.fileName,
            content: item.content,
            description: item.description,
          })),
          hooks: values.hooks.flatMap((hookForm) =>
            hookForm.matchers.flatMap((matcher, matcherIndex) =>
              matcher.hooks.map((hookExec) => ({
                id: `${hookForm.localId}-${matcherIndex}`,
                name: `${hookForm.event}-${matcherIndex + 1}`,
                event: hookForm.event,
                matcher: matcher.matcher,
                action: hookExec.type as 'command',
                command: hookExec.command,
                script: undefined,
                timeout: hookExec.timeout,
              })),
            ),
          ),
          agents: values.agents.map(item => ({
            id: item.localId,
            fileName: item.fileName,
            content: item.content,
            description: item.description,
          })),
          outputStyle: values.outputStyle.map(item => ({
            id: item.localId,
            fileName: item.fileName,
            content: item.content,
            description: item.description,
          })),
          skills: values.skills.map(item => ({
            id: item.localId,
            name: item.path.split('/').pop() || item.path,
            path: item.path,
            type: 'file',
            content: item.content,
          })),
          scripts: values.scripts.map(item => ({
            id: item.localId,
            name: item.path.split('/').pop() || item.path,
            path: item.path,
            type: 'file',
            content: item.content,
          })),
          isActive: values.isActive,
        });

        toast({
          title: t('template.editor.toasts.saveSuccess.title'),
          description: t('template.editor.toasts.saveSuccess.description'),
          variant: 'success',
        });

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveCanonicalTemplate failed', { error });
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
          description: t('template.editor.toasts.error.description'),
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
          description: t('template.editor.toasts.saveSuccess.description'),
          variant: 'success',
        });

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveMcpConfig failed', { error });
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
   * 儲存 Hooks 配置
   */
  const saveHooksConfig = useCallback(
    async (hooks: HookFormValue[]) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: t('template.editor.toasts.error.description'),
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
          description: t('template.editor.toasts.saveSuccess.description'),
          variant: 'success',
        });

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveHooksConfig failed', { error });
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
   * 載入 Commands 設定
   */
  const loadCommands = useCallback(
    () =>
      loadTemplateFiles<CommandFormValue>(
        templateApi.getCommandsFiles,
        templateApi.getCommandFile,
        (file, content) => ({
          localId: `local-${file.file_name}`,
          fileName: file.file_name,
          content: content.content,
          description: file.file_name.replace('.md', ''),
          size: file.size,
          lastModified: file.last_modified,
        }),
        { label: 'commands', slug: 'Commands' }
      ),
    [loadTemplateFiles]
  );

  /**
   * 儲存 Commands 設定
   */
  const saveCommands = useCallback(
    async (commands: CommandFormValue[], existingCommands: CommandFormValue[] = []) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: t('template.editor.toasts.error.description'),
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);

        const existingFileNames = new Set(existingCommands.map(cmd => cmd.fileName));
        const newCommands = commands.filter(cmd => !existingFileNames.has(cmd.fileName));
        const existingCommandsMap = new Map(existingCommands.map(cmd => [cmd.fileName, cmd]));
        const updatedCommands = commands.filter(cmd => {
          const existing = existingCommandsMap.get(cmd.fileName);
          return existing && cmd.content !== existing.content;
        });

        // 逐個儲存新的 Command 檔案
        for (const command of newCommands) {
          await templateApi.createCommandFile(templateId, {
            file_name: command.fileName,
            content: command.content,
          });
        }

        // 逐個更新現有的 Command 檔案
        for (const command of updatedCommands) {
          await templateApi.updateCommandFile(templateId, command.fileName, {
            content: command.content,
          });
        }

        if (newCommands.length > 0 || updatedCommands.length > 0) {
          toast({
            title: t('template.editor.toasts.saveSuccess.title'),
            description: t('template.editor.toasts.saveSuccess.description'),
            variant: 'success',
          });
        }

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveCommands failed', { error });

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
   * 載入 Agents 設定
   */
  const loadAgents = useCallback(
    () =>
      loadTemplateFiles<AgentFormValue>(
        templateApi.getAgentsFiles,
        templateApi.getAgentFile,
        (file, content) => ({
          localId: `local-${file.file_name}`,
          fileName: file.file_name,
          content: content.content,
          description: file.file_name.replace('.md', ''),
          size: file.size,
          lastModified: file.last_modified,
        }),
        { label: 'agents', slug: 'Agents' }
      ),
    [loadTemplateFiles]
  );

  /**
   * 儲存 Agents 設定
   */
  const saveAgents = useCallback(
    async (agents: AgentFormValue[], existingAgents: AgentFormValue[] = []) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: t('template.editor.toasts.error.description'),
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);

        const existingFileNames = new Set(existingAgents.map(agent => agent.fileName));
        const newAgents = agents.filter(agent => !existingFileNames.has(agent.fileName));
        const existingAgentsMap = new Map(existingAgents.map(agent => [agent.fileName, agent]));
        const updatedAgents = agents.filter(agent => {
          const existing = existingAgentsMap.get(agent.fileName);
          return existing && agent.content !== existing.content;
        });

        // 逐個儲存新的 Agent 檔案
        for (const agent of newAgents) {
          await templateApi.createAgentFile(templateId, {
            file_name: agent.fileName,
            content: agent.content,
          });
        }

        // 逐個更新現有的 Agent 檔案
        for (const agent of updatedAgents) {
          await templateApi.updateAgentFile(templateId, agent.fileName, {
            content: agent.content,
          });
        }

        if (newAgents.length > 0 || updatedAgents.length > 0) {
          toast({
            title: t('template.editor.toasts.saveSuccess.title'),
            description: t('template.editor.toasts.saveSuccess.description'),
            variant: 'success',
          });
        }

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveAgents failed', { error });

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
   * 載入 Output Style 設定
   */
  const loadOutputStyle = useCallback(
    () =>
      loadTemplateFiles<OutputStyleFormValue>(
        templateApi.getOutputStyleFiles,
        templateApi.getOutputStyleFile,
        (file, content) => ({
          localId: `local-${file.file_name}`,
          fileName: file.file_name,
          content: content.content,
          description: file.file_name.replace('.md', ''),
          size: file.size,
          lastModified: file.last_modified,
        }),
        { label: 'output style', slug: 'OutputStyle' }
      ),
    [loadTemplateFiles]
  );

  /**
   * 儲存 Output Style 設定
   */
  const saveOutputStyle = useCallback(
    async (outputStyle: OutputStyleFormValue[], existingOutputStyle: OutputStyleFormValue[] = []) => {
      if (!templateId) {
        toast({
          title: t('template.editor.toasts.error.title'),
          description: t('template.editor.toasts.error.description'),
          variant: 'destructive',
        });
        return false;
      }

      try {
        setIsSaving(true);

        const existingFileNames = new Set(existingOutputStyle.map(style => style.fileName));
        const newOutputStyle = outputStyle.filter(style => !existingFileNames.has(style.fileName));
        const existingOutputStyleMap = new Map(existingOutputStyle.map(style => [style.fileName, style]));
        const updatedOutputStyle = outputStyle.filter(style => {
          const existing = existingOutputStyleMap.get(style.fileName);
          return existing && style.content !== existing.content;
        });

        // 逐個儲存新的 Output Style 檔案
        for (const style of newOutputStyle) {
          await templateApi.createOutputStyleFile(templateId, {
            file_name: style.fileName,
            content: style.content,
          });
        }

        // 逐個更新現有的 Output Style 檔案
        for (const style of updatedOutputStyle) {
          await templateApi.updateOutputStyleFile(templateId, style.fileName, {
            content: style.content,
          });
        }

        onSuccess?.();
        return true;
      } catch (error) {
        logger.error('saveOutputStyle failed', { error });

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

  return {
    isSaving,
    saveBasicInfo,
    saveCanonicalTemplate,
    saveMcpConfig,
    saveHooksConfig,
    saveCommands,
    saveAgents,
    saveOutputStyle,
    loadCommands,
    loadAgents,
    loadOutputStyle,
  };
}
