import { ApiClient } from '@/shared/api/apiClient';
import type { SlashCommandItem, SlashCommandScope } from '@/shared/types/slashCommands';
import {
  buildSkillDisplayName,
  buildSkillInvocation,
  buildSlashCommandCategory,
  buildSlashCommandDisplayName,
  buildSlashCommandInvocation,
} from '@/shared/types/slashCommands';

/**
 * 創建帶認證的 Runtime API Client
 */
const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

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

const mapSummaryToItem = (
  scope: SlashCommandScope,
  summary: SlashCommandSummaryResponse,
): SlashCommandItem => {
  const namespace = summary.namespace?.trim() || undefined;
  const pluginName = summary.pluginName?.trim() || undefined;

  // 使用 buildSlashCommandDisplayName 組合顯示名稱
  // Plugin: {pluginName}:{fileName}
  // 非 Plugin: {namespace}/{fileName} 或 {fileName}
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

const collectSkillNodes = (nodes: SkillTreeNodeResponse[]): SkillTreeNodeResponse[] => {
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
      if (scope === 'plugin') {
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
      skillItems.push(...skillNodes.map((node) => mapSkillNodeToItem(node, scope)));
    }

    return skillItems.sort((a, b) => a.displayName.localeCompare(b.displayName));
  },

  async listPickerItems(
    runtimeBaseUrl: string,
    workspaceId: string,
    apiPrefix: string = 'claude-code',
    availableScopes: string[] = ['project', 'user', 'plugin'],
  ): Promise<SlashCommandItem[]> {
    const [commands, skills] = await Promise.all([
      this.list(runtimeBaseUrl, workspaceId, apiPrefix),
      this.listSkills(runtimeBaseUrl, workspaceId, apiPrefix, availableScopes),
    ]);

    return [...commands, ...skills].sort((a, b) => a.displayName.localeCompare(b.displayName));
  },
};

export type SlashCommandApi = typeof slashCommandApi;
