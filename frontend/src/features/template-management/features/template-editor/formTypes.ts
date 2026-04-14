import { TemplateUpsertPayload } from '../../providers/TemplateManagementProvider';
import type {
  Template,
  TemplateCategory,
  TemplateMcpServer,
  TemplateSlashCommand,
  TemplateHook,
  TemplateSubAgent,
  TemplateOutputStyle,
} from '@/shared/types/templates';
import { flattenFileTree, buildFileTreeFromEntries, TemplateFileEntry } from '../../utils/templateFiles';

export interface McpServerFormValue {
  localId: string;
  name: string;
  type: TemplateMcpServer['type'];
  command: string;
  argsText: string;
  url: string;
  description: string;
  envText: string;
  headersText: string; // HTTP 標頭，僅在 HTTP/SSE 類型時使用
}

export interface SlashCommandFormValue {
  localId: string;
  fileName: string;
  content: string;
  description: string;
  size?: number;
  lastModified?: string;
}

export interface HookExecutionFormValue {
  type: 'command'; // 僅支援 command 類型
  command: string;
  timeout: number;
}

export interface HookMatcherFormValue {
  matcher?: string; // 可選，當為空時表示應用於所有情況
  hooks: HookExecutionFormValue[];
}

export interface HookFormValue {
  localId: string;
  event: string;
  matchers: HookMatcherFormValue[];
}

export interface SubAgentFormValue {
  localId: string;
  fileName: string;
  content: string;
  description: string;
  size?: number;
  lastModified?: string;
}

export interface OutputStyleFormValue {
  localId: string;
  fileName: string;
  content: string;
  description: string;
  size?: number;
  lastModified?: string;
}

export interface FileEntryFormValue extends TemplateFileEntry {
  localId: string;
}

export interface SkillFileFormValue extends TemplateFileEntry {
  localId: string;
}

export interface TemplateFormValues {
  templateId: string; // 模板代號 (kebab-case, 只能英文)
  name: string; // 模板名稱
  description: string;
  version: string;
  authorName: string;
  authorEmail: string;
  authorUrl: string;
  keywords: string[];
  categoryId?: string;
  documentation: string;
  claudeMd: string;
  isActive: boolean;
  initCommands: string;
  mcpServers: McpServerFormValue[];
  slashCommands: SlashCommandFormValue[];
  hooks: HookFormValue[];
  subAgents: SubAgentFormValue[];
  outputStyles: OutputStyleFormValue[];
  skills: SkillFileFormValue[];
  scripts: FileEntryFormValue[];
}

const generateLocalId = () => `local-${Math.random().toString(36).slice(2, 10)}`;

const toArgsText = (args?: string[]) => (args && args.length > 0 ? args.join('\n') : '');

const toEnvText = (env?: Record<string, string>) => {
  if (!env) return '';
  return Object.entries(env)
    .map(([key, value]) => `${key}=${value}`)
    .join('\n');
};

export const parseArgsText = (text: string): string[] =>
  text
    .split(/\n|,/)
    .map(item => item.trim())
    .filter(Boolean);

export const parseEnvText = (text: string): Record<string, string> | undefined => {
  const lines = text
    .split(/\n/)
    .map(item => item.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return undefined;
  }
  const env: Record<string, string> = {};
  lines.forEach(line => {
    const [key, ...rest] = line.split('=');
    if (!key) return;
    env[key.trim()] = rest.join('=').trim();
  });
  return env;
};

const toHeadersText = (headers?: Record<string, string>) => {
  if (!headers) return '';
  return Object.entries(headers)
    .map(([key, value]) => `${key}: ${value}`)
    .join('\n');
};

export const parseHeadersText = (text: string): Record<string, string> | undefined => {
  const lines = text
    .split(/\n/)
    .map(item => item.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return undefined;
  }
  const headers: Record<string, string> = {};
  lines.forEach(line => {
    const [key, ...rest] = line.split(':');
    if (!key) return;
    headers[key.trim()] = rest.join(':').trim();
  });
  return headers;
};

const toTimeoutText = (timeout?: number) => (typeof timeout === 'number' ? String(timeout) : '');

const parseTimeout = (text: string): number | undefined => {
  const value = Number(text);
  return Number.isFinite(value) && value > 0 ? value : undefined;
};

export const mapTemplateToFormValues = (template: Template): TemplateFormValues => ({
  templateId: template.id, // 模板代號
  name: template.name, // 模板名稱
  description: template.description ?? '',
  version: template.version,
  authorName: template.author.name,
  authorEmail: template.author.email ?? '',
  authorUrl: template.author.url ?? '',
  keywords: template.keywords ?? [],
  categoryId: template.categoryId,
  documentation: template.documentation ?? '',
  claudeMd: template.claudeMd ?? '',
  isActive: template.isActive ?? true,
  initCommands: template.initCommands ?? '',
  mcpServers: template.mcpServers.map<McpServerFormValue>(item => ({
    localId: generateLocalId(),
    name: item.name ?? '',
    type: item.type ?? 'stdio',
    command: item.command ?? '',
    argsText: toArgsText(item.args),
    url: item.url ?? '',
    description: item.description ?? '',
    envText: toEnvText(item.env),
    headersText: toHeadersText(item.headers),
  })),
  slashCommands: template.slashCommands.map<SlashCommandFormValue>(item => ({
    localId: generateLocalId(),
    fileName: item.fileName,
    content: item.content,
    description: item.description ?? '',
    size: item.content.length,
  })),
  hooks: (() => {
    // 按事件分組 hooks
    const groupedHooks: Record<string, typeof template.hooks> = {};
    template.hooks.forEach(hook => {
      if (!groupedHooks[hook.event]) {
        groupedHooks[hook.event] = [];
      }
      groupedHooks[hook.event].push(hook);
    });

    // 轉換為 HookFormValue 格式
    return Object.entries(groupedHooks).map(([event, eventHooks]) => ({
      localId: generateLocalId(),
      event,
      matchers: eventHooks.map(hook => ({
        matcher: hook.matcher ?? '*',
        hooks: [{
          type: hook.action as 'command',
          command: hook.command ?? '',
          timeout: hook.timeout ?? 30,
        }]
      }))
    }));
  })(),
  subAgents: template.subAgents.map<SubAgentFormValue>(item => ({
    localId: generateLocalId(),
    fileName: item.fileName,
    content: item.content,
    description: item.description ?? '',
    size: item.content.length,
  })),
  outputStyles: template.outputStyles.map<OutputStyleFormValue>(item => ({
    localId: generateLocalId(),
    fileName: item.fileName,
    content: item.content,
    description: item.description ?? '',
    size: item.content.length,
  })),
  skills: flattenFileTree(template.skills).map<SkillFileFormValue>(entry => ({
    localId: generateLocalId(),
    path: entry.path,
    content: entry.content ?? '',
  })),
  scripts: flattenFileTree(template.scripts).map<FileEntryFormValue>(entry => ({
    localId: generateLocalId(),
    path: entry.path,
    content: entry.content ?? '',
  })),
});

export const createEmptyFormValues = (categories: TemplateCategory[]): TemplateFormValues => ({
  templateId: '', // 模板代號
  name: '', // 模板名稱
  description: '',
  version: '1.0.0',
  authorName: '',
  authorEmail: '',
  authorUrl: '',
  keywords: [],
  categoryId: categories[0]?.id ?? '',
  documentation: '',
  claudeMd: '',
  isActive: true,
  initCommands: '',
  mcpServers: [],
  slashCommands: [],
  hooks: [],
  subAgents: [],
  outputStyles: [],
  skills: [],
  scripts: [],
});

export const mapFormValuesToPayload = (values: TemplateFormValues): TemplateUpsertPayload => ({
  templateId: values.templateId, // 模板代號
  name: values.name, // 模板名稱
  description: values.description,
  categoryId: values.categoryId,
  version: values.version,
  author: {
    name: values.authorName,
    email: values.authorEmail || undefined,
    url: values.authorUrl || undefined,
  },
  keywords: values.keywords,
  documentation: values.documentation,
  claudeMd: values.claudeMd,
  isActive: values.isActive,
  initCommands: values.initCommands,
  mcpServers: values.mcpServers.map<TemplateMcpServer>(item => ({
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
  slashCommands: values.slashCommands.map<TemplateSlashCommand>(item => ({
    id: item.localId,
    fileName: item.fileName,
    content: item.content,
    description: item.description,
  })),
  hooks: (() => {
    // 展開所有匹配器為單一的 TemplateHook
    const allHooks: TemplateHook[] = [];
    values.hooks.forEach(hookForm => {
      hookForm.matchers.forEach((matcher, matcherIndex) => {
        matcher.hooks.forEach(hookExec => {
          allHooks.push({
            id: `${hookForm.localId}-${matcherIndex}`,
            name: `${hookForm.event} Hook - Matcher ${matcherIndex + 1}`,
            event: hookForm.event,
            matcher: matcher.matcher,
            action: hookExec.type as 'command',
            command: hookExec.command,
            script: undefined,
            timeout: hookExec.timeout,
          });
        });
      });
    });
    return allHooks;
  })(),
  subAgents: values.subAgents.map<TemplateSubAgent>(item => ({
    id: item.localId,
    fileName: item.fileName,
    content: item.content,
    description: item.description,
  })),
  outputStyles: values.outputStyles.map<TemplateOutputStyle>(item => ({
    id: item.localId,
    fileName: item.fileName,
    content: item.content,
    description: item.description,
  })),
  skills: buildFileTreeFromEntries(
    values.skills.map(item => ({
      path: item.path,
      content: item.content,
    })),
  ),
  scripts: buildFileTreeFromEntries(
    values.scripts.map(item => ({
      path: item.path,
      content: item.content,
    })),
  ),
});
