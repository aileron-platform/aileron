import { ApiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';
import type { SlashCommandItem, SlashCommandScope } from '@/shared/types/slashCommands';
import {
  buildSkillDisplayName,
  buildSkillInvocation,
  buildSlashCommandCategory,
  buildSlashCommandDisplayName,
  buildSlashCommandInvocation,
} from '@/shared/types/slashCommands';

/**
 * Create an authenticated Runtime API client.
 */
const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

const logger = createLogger('slashCommandApi');

interface SlashCommandSummaryResponse {
  fileName: string;
  namespace?: string | null;
  description?: string | null;
  scope: SlashCommandScope;
  size: string;
  pluginName?: string | null;
  marketplaceName?: string | null;
}

interface SlashCommandScopeGroupResponse {
  scope: SlashCommandScope;
  documents: SlashCommandSummaryResponse[];
}

interface SlashCommandCollectionResponse {
  workspaceId: string;
  scopes: SlashCommandScopeGroupResponse[];
}

interface SkillTreeNodeResponse {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  scope?: SlashCommandScope;
  children?: SkillTreeNodeResponse[] | null;
  skillName?: string;
  skillDescription?: string;
}

interface SkillTreeResponse {
  path: string;
  scope?: SlashCommandScope;
  nodes: SkillTreeNodeResponse[];
  total: number;
}


interface PluginSkillResponse {
  pluginName: string;
  marketplaceName: string;
  skillName: string;
  skillPath: string;
}

interface CodexFileSummaryResponse {
  name: string;
  path: string;
  sizeBytes: number;
  source: 'user' | 'project' | 'plugin' | 'built_in';
  readOnly?: boolean;
  metadata?: {
    pluginId?: string;
    pluginName?: string;
    marketplaceName?: string;
    [key: string]: unknown;
  };
}

interface CodexFileListResponse {
  workspaceId: string;
  layer: SlashCommandScope;
  resource: string;
  directory: string;
  files: CodexFileSummaryResponse[];
}

const mapSummaryToItem = (
  scope: SlashCommandScope,
  summary: SlashCommandSummaryResponse,
): SlashCommandItem => {
  const namespace = summary.namespace?.trim() || undefined;
  const pluginName = summary.pluginName?.trim() || undefined;

  // Build display names for plugin and non-plugin command scopes.
  const displayName = buildSlashCommandDisplayName(summary.fileName, namespace, pluginName);
  const category = buildSlashCommandCategory(scope, namespace);
  const id = namespace ? `${scope}:${namespace}:${summary.fileName}` : `${scope}:${summary.fileName}`;

  return {
    id,
    fileName: summary.fileName,
    kind: 'slash-command',
    namespace,
    pluginName,
    displayName,
    category,
    scope,
    description: summary.description ?? '',
    invocation: buildSlashCommandInvocation(displayName),
    tags: [],
  };
};

const collectSkillNodes = (nodes: SkillTreeNodeResponse[] = []): SkillTreeNodeResponse[] => {
  const result: SkillTreeNodeResponse[] = [];

  const walk = (node: SkillTreeNodeResponse) => {
    if (node.type === 'file' && node.name === 'SKILL.md' && node.scope) {
      result.push(node);
      return;
    }
    node.children?.forEach(walk);
  };

  nodes.forEach(walk);
  return result;
};

const parseSkillFrontMatter = (content: string): { skillName?: string; skillDescription?: string } => {
  if (!content.startsWith('---\n')) {
    return {};
  }

  const endMarker = content.indexOf('\n---\n', 4);
  if (endMarker === -1) {
    return {};
  }

  const frontMatter = content.slice(4, endMarker);
  const metadata: { skillName?: string; skillDescription?: string } = {};
  frontMatter.split('\n').forEach((line) => {
    const separatorIndex = line.indexOf(':');
    if (separatorIndex === -1) return;

    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim().replace(/^['"]|['"]$/g, '');
    if (key === 'name' && value) {
      metadata.skillName = value;
    }
    if (key === 'description' && value) {
      metadata.skillDescription = value;
    }
  });

  return metadata;
};

const mapSkillNodeToItem = (node: SkillTreeNodeResponse, scope: SlashCommandScope): SlashCommandItem => {
  const segments = node.path.split('/').filter(Boolean);
  const directoryName = segments.length >= 2 ? segments[segments.length - 2] : segments[0] || 'skill';
  const skillName = node.skillName?.trim() || directoryName;

  return {
    id: `${scope}:skill:${skillName}`,
    fileName: 'SKILL.md',
    kind: 'skill',
    scope,
    displayName: buildSkillDisplayName(skillName),
    category: scope,
    description: node.skillDescription?.trim() || '',
    invocation: buildSkillInvocation(skillName),
    tags: [],
  };
};

const mapPluginSkillToItem = (
  scope: SlashCommandScope,
  skill: PluginSkillResponse,
): SlashCommandItem => ({
  id: `${scope}:skill:${skill.pluginName}:${skill.skillName}`,
  fileName: 'SKILL.md',
  kind: 'skill',
  scope,
  pluginName: skill.pluginName,
  displayName: buildSkillDisplayName(skill.skillName, skill.pluginName),
  category: skill.pluginName,
  description: '',
  invocation: buildSkillInvocation(skill.skillName, skill.pluginName),
  tags: [],
});

const mapCodexPluginSkillToItem = (
  skill: CodexFileSummaryResponse,
  metadata: { skillName?: string; skillDescription?: string } = {},
): SlashCommandItem => {
  const pluginName = skill.metadata?.pluginName?.trim() || skill.metadata?.pluginId?.trim() || 'plugin';
  const segments = skill.path.split('/').filter(Boolean);
  const directoryName = segments.length >= 2 ? segments[segments.length - 2] : skill.name || 'skill';
  const skillName = metadata.skillName?.trim() || directoryName;

  return {
    id: `plugin:skill:${pluginName}:${skillName}:${skill.path}`,
    fileName: 'SKILL.md',
    kind: 'skill',
    scope: 'plugin',
    pluginName,
    displayName: buildSkillDisplayName(skillName, pluginName),
    category: pluginName,
    description: metadata.skillDescription?.trim() || '',
    invocation: buildSkillInvocation(skillName, pluginName),
    tags: [],
  };
};

const isCodexSkillDocument = (file: CodexFileSummaryResponse): boolean => {
  return file.name === 'SKILL.md' || file.path === 'SKILL.md' || file.path.endsWith('/SKILL.md');
};

const loadSkillMetadata = async (
  client: ApiClient,
  workspaceId: string,
  apiPrefix: string,
  scope: 'project' | 'user',
  node: SkillTreeNodeResponse,
): Promise<void> => {
  if (node.skillName || node.skillDescription) return;

  const params = new URLSearchParams();
  params.set('path', node.path);
  params.set('scope', scope);
  const content = await client.get<{ content?: string }>(
    `/api/v1/workspaces/${workspaceId}/${apiPrefix}/skills/content?${params.toString()}`,
  );
  const metadata = parseSkillFrontMatter(content.content ?? '');
  node.skillName = metadata.skillName;
  node.skillDescription = metadata.skillDescription;
};

const loadCodexPluginSkillMetadata = async (
  client: ApiClient,
  workspaceId: string,
  skill: CodexFileSummaryResponse,
): Promise<{ skillName?: string; skillDescription?: string }> => {
  const params = new URLSearchParams();
  params.set('layer', 'plugin');
  params.set('path', skill.path);
  const pluginId = skill.metadata?.pluginId?.trim();
  if (pluginId) {
    params.set('pluginId', pluginId);
  }
  const content = await client.get<{ content?: string }>(
    `/api/v1/workspaces/${workspaceId}/codex/skills/file?${params.toString()}`,
  );
  return parseSkillFrontMatter(content.content ?? '');
};

export const slashCommandApi = {
  async list(
    runtimeBaseUrl: string,
    workspaceId: string,
    apiPrefix: string = 'claude-code',
    signal?: AbortSignal,
  ): Promise<SlashCommandItem[]> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const path = `/api/v1/workspaces/${workspaceId}/${apiPrefix}/slash-commands`;
    const response = await client.get<SlashCommandCollectionResponse>(path);
    const items = response.scopes.flatMap(({ scope, documents }) =>
      documents.map((document) => mapSummaryToItem(scope, document)),
    );
    return items.sort((a, b) => a.displayName.localeCompare(b.displayName));
  },

  async listSkills(
    runtimeBaseUrl: string,
    workspaceId: string,
    apiPrefix: string = 'claude-code',
    availableScopes: string[] = ['project', 'user', 'plugin'],
  ): Promise<SlashCommandItem[]> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const scopes = (['project', 'user', 'plugin'] as const).filter((scope) => availableScopes.includes(scope));
    const skillItems: SlashCommandItem[] = [];

    for (const scope of scopes) {
      try {
        if (scope === 'plugin') {
          if (apiPrefix === 'codex') {
            const response = await client.get<CodexFileListResponse>(
              `/api/v1/workspaces/${workspaceId}/codex/skills/files?layer=plugin`,
            );
            const pluginSkills = response.files.filter((file) => file.source === 'plugin' && isCodexSkillDocument(file));
            const items = await Promise.all(pluginSkills.map(async (skill) => {
              try {
                const metadata = await loadCodexPluginSkillMetadata(client, workspaceId, skill);
                return mapCodexPluginSkillToItem(skill, metadata);
              } catch (error) {
                logger.warn('Failed to load Codex plugin skill metadata', {
                  error,
                  workspaceId,
                  path: skill.path,
                  pluginId: skill.metadata?.pluginId,
                });
                return mapCodexPluginSkillToItem(skill);
              }
            }));
            skillItems.push(...items);
            continue;
          }

          const pluginSkills = await client.get<PluginSkillResponse[]>(
            `/api/v1/workspaces/${workspaceId}/${apiPrefix}/skills/plugins`,
          );
          skillItems.push(...pluginSkills.map((skill) => mapPluginSkillToItem(scope, skill)));
          continue;
        }

        const tree = await client.get<SkillTreeResponse>(
          `/api/v1/workspaces/${workspaceId}/${apiPrefix}/skills/tree?scope=${scope}&maxDepth=8`,
        );
        const skillNodes = collectSkillNodes(tree.nodes);
        await Promise.all(skillNodes.map(async (node) => {
          try {
            await loadSkillMetadata(client, workspaceId, apiPrefix, scope, node);
          } catch (error) {
            logger.warn('Failed to load skill metadata', {
              error,
              workspaceId,
              apiPrefix,
              scope,
              path: node.path,
            });
          }
        }));
        skillItems.push(...skillNodes.map((node) => mapSkillNodeToItem(node, scope)));
      } catch (error) {
        logger.warn('Failed to load slash picker skills for scope', {
          error,
          workspaceId,
          apiPrefix,
          scope,
        });
      }
    }

    return skillItems.sort((a, b) => a.displayName.localeCompare(b.displayName));
  },

  async listPickerItems(
    runtimeBaseUrl: string,
    workspaceId: string,
    apiPrefix: string = 'claude-code',
    availableScopes: string[] = ['project', 'user', 'plugin'],
  ): Promise<SlashCommandItem[]> {
    const [commandsResult, skillsResult] = await Promise.allSettled([
      this.list(runtimeBaseUrl, workspaceId, apiPrefix),
      this.listSkills(runtimeBaseUrl, workspaceId, apiPrefix, availableScopes),
    ]);
    const commands = commandsResult.status === 'fulfilled' ? commandsResult.value : [];
    const skills = skillsResult.status === 'fulfilled' ? skillsResult.value : [];

    if (commandsResult.status === 'rejected') {
      logger.warn('Failed to load slash picker commands', {
        error: commandsResult.reason,
        workspaceId,
        apiPrefix,
      });
    }

    if (skillsResult.status === 'rejected') {
      logger.warn('Failed to load slash picker skills', {
        error: skillsResult.reason,
        workspaceId,
        apiPrefix,
      });
    }

    return [...commands, ...skills].sort((a, b) => a.displayName.localeCompare(b.displayName));
  },
};

export type SlashCommandApi = typeof slashCommandApi;
