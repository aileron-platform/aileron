import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Bot,
  ChevronLeft,
  ChevronRight,
  Command,
  Copy,
  Database,
  Download,
  Edit,
  FileArchive,
  FileText,
  FolderPlus,
  Info,
  MoreHorizontal,
  Network,
  PenSquare,
  Plus,
  RefreshCw,
  Save,
  Server,
  Sparkles,
  Trash2,
  Terminal,
  Upload,
  Wand2,
  Workflow,
  Zap,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { TopTabsBar, TopTabsCountBadge, TopTabsList, TopTabsTrigger } from '@/shared/components/navigation/TopTabs';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceFeatureContentItem, MarketplacePackageDetail, MarketplacePackageFile, MarketplaceProvider } from '@/shared/types/marketplace';
import {
  BatchDeleteDialog,
  FileCreateDialog,
  FileDeleteDialog,
  FileRenameDialog,
  FileTreeContextMenu,
  FileTreePanel,
  getAllDirectoryNodes,
  useFileTreeContextMenu,
  useFileTreeState,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { CodeTextEditor, FileEditor } from '@/shared/components/file-workbench/viewer-entry';
import { MarkdownDocumentShell } from '@/shared/components/document-workflow';
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';
import WarningIcon from '@/shared/components/ui/WarningIcon';
import {
  HookMatcherActionsEditor,
  type HookMatcher,
  type HookMatcherActionsLabels,
} from '@/shared/components/hook-workflow';
import {
  MCPTransportFieldsEditor,
  createMCPKeyValueRows,
  parseMCPArgsText,
  parseMCPKeyValueText,
  toMCPKeyValueRecord,
  toMCPKeyValueText,
  type MCPKeyValueRow,
  type MCPTransport,
  type MCPTransportFieldsLabels,
} from '@/shared/components/mcp-workflow';
import {
  SettingsWorkflowActionButton,
  SettingsWorkflowCountBadge,
  SettingsWorkflowShell,
} from '@/shared/components/settings-workflow';
import { cn } from '@/shared/utils/cn';
import { MarketplaceSectionSidebarShell } from '../../components/MarketplaceSectionSidebarShell';
import { createPackage, getPackage, savePackage as saveMarketplacePackage } from '../../api/marketplaceApi';
import { downloadBlob } from '../../utils/downloadBlob';

export interface MarketplaceEditorViewProps {
  mode: 'create' | 'edit';
}

const marketplaceEditorTabs = ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'outputStyle', 'policies', 'skills', 'files'] as const;
type MarketplaceEditorTab = typeof marketplaceEditorTabs[number];

const providerEditorTabs: Record<MarketplaceProvider, MarketplaceEditorTab[]> = {
  'claude-code': ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'outputStyle', 'skills', 'files'],
  codex: ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'skills', 'files'],
  gemini: ['basic', 'agentsMd', 'hooks', 'agents', 'commands', 'policies', 'skills', 'files'],
};

const tabIcons: Record<MarketplaceEditorTab, React.ComponentType<{ className?: string }>> = {
  basic: Info,
  agentsMd: FileText,
  skills: Wand2,
  commands: Command,
  agents: Bot,
  hooks: Zap,
  mcp: Network,
  outputStyle: Wand2,
  policies: Workflow,
  files: FileArchive,
};

const getMarketplaceEditorTabLabelKey = (
  provider: MarketplaceProvider,
  tab: MarketplaceEditorTab,
): string => {
  if (provider === 'claude-code' && tab === 'agentsMd') {
    return 'marketplace.editor.tabs.claudeMd';
  }
  if (provider === 'gemini' && tab === 'agentsMd') {
    return 'marketplace.editor.tabs.geminiMd';
  }
  if (tab === 'agents') {
    return 'marketplace.editor.tabs.subagents';
  }
  if (tab === 'commands') {
    return 'marketplace.editor.tabs.slashCommand';
  }
  return `marketplace.editor.tabs.${tab}`;
};

const countMarketplaceFileNodes = (nodes: FileTreeNode[]): number => (
  nodes.reduce((count, node) => (
    count + (node.type === 'file' ? 1 : 0) + (node.children ? countMarketplaceFileNodes(node.children) : 0)
  ), 0)
);

const getMarketplacePackageRoot = (provider: MarketplaceProvider, packageId: string): string => (
  provider === 'gemini'
    ? `gemini/extensions/${packageId}`
    : `${provider}/plugins/${packageId}`
);

const createMarketplacePackageFileTree = (
  provider: MarketplaceProvider,
  packageRoot: string,
  displayName: string,
  packageFiles: MarketplacePackageFile[],
): FileTreeNode[] => {
  const rootPath = `/${packageRoot}`;
  if (packageFiles.length > 0) {
    return marketplacePackageFilesToFileTree(packageFiles, rootPath, provider === 'gemini' ? 'extension' : 'plugin');
  }

  const packageName = packageRoot.split('/').at(-1) ?? packageRoot;
  const scope = provider === 'gemini' ? 'extension' : 'plugin';
  const manifestPath = provider === 'gemini'
    ? `${rootPath}/gemini-extension.json`
    : `${rootPath}/${provider === 'codex' ? '.codex-plugin' : '.claude-plugin'}/plugin.json`;
  const manifestDirectory = provider === 'gemini' ? null : {
    id: manifestPath.split('/').slice(0, -1).join('/'),
    name: provider === 'codex' ? '.codex-plugin' : '.claude-plugin',
    path: manifestPath.split('/').slice(0, -1).join('/'),
    type: 'directory' as const,
    scope: 'plugin' as const,
    children: [
      {
        id: manifestPath,
        name: 'plugin.json',
        path: manifestPath,
        type: 'file' as const,
        extension: 'json',
        scope: 'plugin' as const,
        size: 128,
        metadata: {
          content: `{\n  "id": "${packageName}",\n  "name": "${displayName}",\n  "version": "0.1.0"\n}`,
        },
      },
    ],
  };

  return [
    {
      id: rootPath,
      name: packageName,
      path: rootPath,
      type: 'directory',
      scope,
      children: [
        ...(manifestDirectory ? [manifestDirectory] : [
          {
            id: manifestPath,
            name: 'gemini-extension.json',
            path: manifestPath,
            type: 'file' as const,
            extension: 'json',
            scope: 'extension' as const,
            size: 128,
            metadata: {
              content: `{\n  "name": "${packageName}",\n  "version": "0.1.0",\n  "contextFileName": "GEMINI.md"\n}`,
            },
          },
        ]),
        {
          id: `${rootPath}/README.md`,
          name: 'README.md',
          path: `${rootPath}/README.md`,
          type: 'file',
          extension: 'md',
          scope: provider === 'gemini' ? 'extension' : 'plugin',
          size: 96,
          metadata: {
            content: `# ${displayName}\n\nPackage README for ${packageRoot}.`,
          },
        },
        {
          id: `${rootPath}/assets`,
          name: 'assets',
          path: `${rootPath}/assets`,
          type: 'directory',
          scope: provider === 'gemini' ? 'extension' : 'plugin',
          children: [
            {
              id: `${rootPath}/assets/icon.svg`,
              name: 'icon.svg',
              path: `${rootPath}/assets/icon.svg`,
              type: 'file',
              extension: 'svg',
              scope: provider === 'gemini' ? 'extension' : 'plugin',
              size: 96,
              metadata: {
                content: '<svg viewBox="0 0 24 24" role="img"><path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z" /></svg>',
              },
            },
            {
              id: `${rootPath}/assets/logo.png`,
              name: 'logo.png',
              path: `${rootPath}/assets/logo.png`,
              type: 'file',
              extension: 'png',
              scope: provider === 'gemini' ? 'extension' : 'plugin',
              size: 68,
              metadata: {
                binary: true,
                mimeType: 'image/png',
                previewDataUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
              },
            },
          ],
        },
        {
          id: `${rootPath}/scripts`,
          name: 'scripts',
          path: `${rootPath}/scripts`,
          type: 'directory',
          scope: provider === 'gemini' ? 'extension' : 'plugin',
          children: [
            {
              id: `${rootPath}/scripts/install-check.sh`,
              name: 'install-check.sh',
              path: `${rootPath}/scripts/install-check.sh`,
              type: 'file',
              extension: 'sh',
              scope: provider === 'gemini' ? 'extension' : 'plugin',
              size: 64,
              metadata: {
                content: '#!/usr/bin/env bash\nset -euo pipefail\n\necho "Checking package prerequisites"\n',
              },
            },
          ],
        },
        {
          id: `${rootPath}/LICENSE`,
          name: 'LICENSE',
          path: `${rootPath}/LICENSE`,
          type: 'file',
          extension: 'txt',
          scope: provider === 'gemini' ? 'extension' : 'plugin',
          size: 32,
          metadata: {
            content: 'MIT License\n\nCopyright (c) 2026',
          },
        },
      ],
    },
  ];
};

interface MarketplaceEditorResourceItem {
  id: string;
  titleKey?: string;
  descriptionKey?: string;
  path: string;
  content: string;
  title?: string;
  description?: string;
  badge?: string;
  code?: string;
  meta?: Array<{ labelKey: string; value: string }>;
}

type MarketplaceEditorFeatureItems = Record<Exclude<MarketplaceEditorTab, 'basic' | 'agentsMd'>, MarketplaceEditorResourceItem[]>;

const emptyMarketplaceFeatureItems = (): MarketplaceEditorFeatureItems => ({
  skills: [],
  agents: [],
  commands: [],
  mcp: [],
  hooks: [],
  outputStyle: [],
  policies: [],
  files: [],
});

const marketplaceFeatureItemFromDetail = (
  item: MarketplaceFeatureContentItem,
  fallbackPath: string,
): MarketplaceEditorResourceItem => {
  const path = item.path ?? fallbackPath;
  const extension = path.split('.').pop() || 'txt';
  return {
    id: item.id || path || item.name,
    title: item.name,
    description: item.description ?? '',
    path,
    content: item.content ?? stringifyMarketplaceJson(item.data ?? {}),
    badge: extension,
  };
};

const marketplaceRecordFromJsonContent = (content: string): Record<string, unknown> | null => {
  try {
    const value: unknown = JSON.parse(content);
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return value as Record<string, unknown>;
    }
  } catch {
    return null;
  }
  return null;
};

const marketplaceStringValue = (value: unknown): string | undefined => (
  typeof value === 'string' ? value : undefined
);

const marketplaceStringArrayValue = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.filter((entry): entry is string => typeof entry === 'string');
  }
  return typeof value === 'string' ? parseMCPArgsText(value) : [];
};

const marketplaceKeyValueRowsFromRecord = (value: unknown): MCPKeyValueRow[] => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return [];
  }
  return createMCPKeyValueRows(
    Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, entry]) => typeof entry === 'string')
        .map(([key, entry]) => [key, entry as string]),
    ),
  );
};

const marketplaceMcpTransportValue = (value: unknown, url: string): MCPTransport => {
  if (value === 'stdio' || value === 'sse' || value === 'http') {
    return value;
  }
  return url ? 'http' : 'stdio';
};

const marketplaceMcpServerValueFromItem = (
  item: MarketplaceEditorResourceItem,
  t: (key: string) => string,
): MarketplaceMcpServerDialogValue => {
  const data = marketplaceRecordFromJsonContent(item.content) ?? {};
  const url = marketplaceStringValue(data.url) ?? '';
  const command = marketplaceStringValue(data.command) ?? (item.code ?? '').split(' ')[0] ?? '';
  const args = marketplaceStringArrayValue(data.args);
  const fallbackArgs = parseMCPArgsText((item.code ?? '').split(' ').slice(1).join('\n'));
  const initialEnvKey = item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.env')?.value ?? '';
  const env = marketplaceKeyValueRowsFromRecord(data.env);
  const transport = marketplaceMcpTransportValue(
    data.transport ?? item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.transport')?.value ?? item.badge,
    url,
  );

  return {
    name: marketplaceStringValue(data.name) ?? marketplaceEditorItemTitle(item, t),
    description: marketplaceStringValue(data.description) ?? marketplaceEditorItemDescription(item, t),
    transport,
    command,
    args: args.length > 0 ? args : fallbackArgs,
    url,
    env: env.length > 0 ? env : (initialEnvKey ? createMCPKeyValueRows({ [initialEnvKey]: '${workspaceFolder}' }) : []),
    headers: marketplaceKeyValueRowsFromRecord(data.headers),
  };
};

const marketplaceMcpRecordFromValue = (value: MarketplaceMcpServerDialogValue): Record<string, unknown> => ({
  ...(value.name.trim() ? { name: value.name.trim() } : {}),
  ...(value.description.trim() ? { description: value.description.trim() } : {}),
  ...(value.transport ? { transport: value.transport } : {}),
  ...(value.command.trim() ? { command: value.command.trim() } : {}),
  ...(value.args.length > 0 ? { args: value.args.filter(Boolean) } : {}),
  ...(value.url.trim() ? { url: value.url.trim() } : {}),
  ...(value.env.some(row => row.key.trim()) ? {
    env: Object.fromEntries(value.env.filter(row => row.key.trim()).map(row => [row.key.trim(), row.value])),
  } : {}),
  ...(value.headers.some(row => row.key.trim()) ? {
    headers: Object.fromEntries(value.headers.filter(row => row.key.trim()).map(row => [row.key.trim(), row.value])),
  } : {}),
});

const marketplaceMcpServerContentFromValue = (value: MarketplaceMcpServerDialogValue): string => (
  JSON.stringify(marketplaceMcpRecordFromValue(value), null, 2)
);

const marketplaceMcpResourceItemFromValue = (
  item: MarketplaceEditorResourceItem,
  value: MarketplaceMcpServerDialogValue,
): MarketplaceEditorResourceItem => {
  const commandText = [value.command, ...value.args].filter(Boolean).join(' ');
  return {
    ...item,
    title: value.name,
    description: value.description,
    content: marketplaceMcpServerContentFromValue(value),
    badge: value.transport,
    code: commandText,
    meta: [
      { labelKey: 'marketplace.editor.featureMeta.labels.transport', value: value.transport },
      ...(value.env[0]?.key ? [{ labelKey: 'marketplace.editor.featureMeta.labels.env', value: value.env[0].key }] : []),
    ],
  };
};

const marketplaceApplyMcpItemsToPackageFiles = (
  files: MarketplacePackageFile[],
  items: MarketplaceEditorResourceItem[],
): MarketplacePackageFile[] => {
  const fileMap = new Map(files.map(file => [file.path, { ...file }]));
  const rootMcpPaths = new Set(['.mcp.json', 'mcp.json']);
  const rootItems = items.filter(item => rootMcpPaths.has(item.path));
  const standaloneItems = items.filter(item => !rootMcpPaths.has(item.path));

  if (rootItems.length > 0) {
    const rootPath = rootItems[0].path;
    const existing = marketplaceRecordFromJsonContent(fileMap.get(rootPath)?.content ?? '') ?? {};
    const existingServers = existing.mcpServers && typeof existing.mcpServers === 'object' && !Array.isArray(existing.mcpServers)
      ? (existing.mcpServers as Record<string, unknown>)
      : {};
    const mcpServers = { ...existingServers };
    rootItems.forEach(item => {
      const serverName = item.title || item.id.split(':').pop() || item.id;
      const serverConfig = marketplaceRecordFromJsonContent(item.content) ?? {};
      mcpServers[serverName] = serverConfig;
    });
    const content = JSON.stringify({ ...existing, mcpServers }, null, 2) + '\n';
    fileMap.set(rootPath, {
      path: rootPath,
      content,
      binary: false,
      mimeType: 'application/json',
      size: content.length,
    });
  }

  standaloneItems.forEach(item => {
    fileMap.set(item.path, {
      path: item.path,
      content: item.content,
      binary: false,
      mimeType: 'application/json',
      size: item.content.length,
    });
  });

  return Array.from(fileMap.values()).sort((first, second) => first.path.localeCompare(second.path));
};

const marketplaceFeatureItemsFromDetail = (detail: MarketplacePackageDetail | null): MarketplaceEditorFeatureItems | null => {
  if (!detail) return null;
  const content = detail.featureContent;
  return {
    ...emptyMarketplaceFeatureItems(),
    skills: content.skills.map(item => marketplaceFeatureItemFromDetail(item, `skills/${item.id}/SKILL.md`)),
    agents: content.agents.map(item => marketplaceFeatureItemFromDetail(item, `agents/${item.id}.md`)),
    commands: content.commands.map(item => marketplaceFeatureItemFromDetail(item, `commands/${item.id}.md`)),
    outputStyle: content.outputStyles.map(item => marketplaceFeatureItemFromDetail(item, `output-styles/${item.id}.md`)),
    mcp: content.mcpServers.map(item => marketplaceFeatureItemFromDetail(item, `mcp/${item.id}.json`)),
    hooks: content.hooks.map(item => marketplaceFeatureItemFromDetail(item, `hooks/${item.id}.json`)),
    policies: (content.policies ?? []).map(item => marketplaceFeatureItemFromDetail(item, `policies/${item.id}.toml`)),
  };
};

const marketplaceEditorItemTitle = (item: MarketplaceEditorResourceItem, t: (key: string) => string): string => (
  item.title ?? (item.titleKey ? t(item.titleKey) : item.id)
);

const marketplaceEditorItemDescription = (item: MarketplaceEditorResourceItem, t: (key: string) => string): string => (
  item.description ?? (item.descriptionKey ? t(item.descriptionKey) : '')
);

const claudeCodeScaffoldFeatureItems: MarketplaceEditorFeatureItems = {
  skills: [
    {
      id: 'review-checklist',
      titleKey: 'marketplace.editor.scaffold.skills.reviewChecklist.title',
      descriptionKey: 'marketplace.editor.scaffold.skills.reviewChecklist.description',
      path: 'skills/review-checklist/SKILL.md',
      content: '# Review checklist\n\nUse this skill to review staged changes with findings-first output.\n\n## Workflow\n\n1. Inspect changed files.\n2. Identify correctness risks.\n3. Check missing verification.\n4. Report actionable findings before summary.',
      badge: 'md',
    },
    {
      id: 'risk-map',
      titleKey: 'marketplace.editor.scaffold.skills.riskMap.title',
      descriptionKey: 'marketplace.editor.scaffold.skills.riskMap.description',
      path: 'skills/risk-map/SKILL.md',
      content: '# Risk map\n\nMap modified files to likely runtime, product, and deployment risks.\n\n## Inputs\n\n- Git diff\n- Package boundaries\n- Existing test coverage',
      badge: 'md',
    },
  ],
  agents: [
    {
      id: 'review-agent',
      titleKey: 'marketplace.editor.scaffold.agents.reviewAgent.title',
      descriptionKey: 'marketplace.editor.scaffold.agents.reviewAgent.description',
      path: 'agents/review-agent.md',
      content: '# Review agent\n\nYou are a focused review subagent. Prioritize bugs, behavioral regressions, and missing tests.\n\n## Output\n\n- Findings first\n- Open questions second\n- Summary last',
      badge: 'agent',
    },
  ],
  commands: [
    {
      id: 'review-summary',
      titleKey: 'marketplace.editor.scaffold.commands.reviewSummary.title',
      descriptionKey: 'marketplace.editor.scaffold.commands.reviewSummary.description',
      path: 'commands/review-summary.md',
      content: '# /review-summary\n\nGenerate a concise summary from staged changes.\n\n```bash\n/review-summary --changes staged\n```\n\nInclude changed areas, test impact, and unresolved risk.',
      badge: 'slash',
      code: '/review-summary --changes staged',
    },
    {
      id: 'review-tests',
      titleKey: 'marketplace.editor.scaffold.commands.reviewTests.title',
      descriptionKey: 'marketplace.editor.scaffold.commands.reviewTests.description',
      path: 'commands/review-tests.md',
      content: '# /review-tests\n\nSuggest targeted verification commands for the current diff.\n\n```bash\n/review-tests --focus risk\n```\n\nPrefer commands that already exist in the repository.',
      badge: 'slash',
      code: '/review-tests --focus risk',
    },
  ],
  mcp: [
    {
      id: 'repository-context',
      titleKey: 'marketplace.editor.scaffold.mcp.repositoryContext.title',
      descriptionKey: 'marketplace.editor.scaffold.mcp.repositoryContext.description',
      path: 'mcp/repository-context.json',
      content: '{\n  "name": "repository-context",\n  "transport": "stdio",\n  "command": "node",\n  "args": ["servers/repository-context.js"],\n  "env": {\n    "REPOSITORY_ROOT": "${workspaceFolder}"\n  }\n}',
      badge: 'stdio',
      code: 'node servers/repository-context.js',
      meta: [
        { labelKey: 'marketplace.editor.featureMeta.labels.transport', value: 'stdio' },
        { labelKey: 'marketplace.editor.featureMeta.labels.env', value: 'REPOSITORY_ROOT' },
      ],
    },
  ],
  hooks: [
    {
      id: 'review-pre-submit',
      titleKey: 'marketplace.editor.scaffold.hooks.reviewPreSubmit.title',
      descriptionKey: 'marketplace.editor.scaffold.hooks.reviewPreSubmit.description',
      path: 'hooks/review-pre-submit.json',
      content: '{\n  "hooks": {\n    "PreToolUse": [\n      {\n        "matcher": "Submit|Bash",\n        "hooks": [\n          {\n            "type": "command",\n            "command": "npm test -- --runInBand",\n            "timeout": 120\n          }\n        ]\n      }\n    ]\n  }\n}',
      badge: 'PreToolUse',
      code: 'npm test -- --runInBand',
      meta: [
        { labelKey: 'marketplace.editor.featureMeta.labels.type', value: 'command' },
        { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: 'Submit|Bash' },
        { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: '120s' },
      ],
    },
  ],
  outputStyle: [
    {
      id: 'review-findings',
      titleKey: 'marketplace.editor.scaffold.outputStyle.reviewFindings.title',
      descriptionKey: 'marketplace.editor.scaffold.outputStyle.reviewFindings.description',
      path: 'output-styles/review-findings.md',
      content: '# Review findings\n\nFormat review output in this order:\n\n1. Findings ordered by severity with file references.\n2. Open questions or assumptions.\n3. Short summary of the reviewed change.\n\nKeep the response concise and actionable.',
      badge: 'md',
    },
  ],
  policies: [],
  files: [
    {
      id: 'package-icon',
      titleKey: 'marketplace.editor.scaffold.files.packageIcon.title',
      descriptionKey: 'marketplace.editor.scaffold.files.packageIcon.description',
      path: 'assets/icon.svg',
      content: '<svg viewBox="0 0 24 24" role="img"><path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z" /></svg>',
      badge: 'svg',
    },
    {
      id: 'license',
      titleKey: 'marketplace.editor.scaffold.files.license.title',
      descriptionKey: 'marketplace.editor.scaffold.files.license.description',
      path: 'LICENSE',
      content: 'MIT License\n\nCopyright (c) 2026',
      badge: 'txt',
    },
  ],
};

const providerScaffoldFeatureItems: Record<MarketplaceProvider, MarketplaceEditorFeatureItems> = {
  'claude-code': claudeCodeScaffoldFeatureItems,
  codex: {
    ...claudeCodeScaffoldFeatureItems,
    skills: [
      {
        id: 'codex-codebase-map',
        titleKey: 'marketplace.editor.scaffold.skills.reviewChecklist.title',
        descriptionKey: 'marketplace.editor.scaffold.skills.reviewChecklist.description',
        title: 'Codebase map',
        description: 'Codex skill for mapping app boundaries before implementation.',
        path: 'skills/codebase-map/SKILL.md',
        content: '# Codebase map\n\nMap files, ownership boundaries, and likely test surfaces before changing code.\n\n## Workflow\n\n1. Inspect routes and feature folders.\n2. Identify shared components.\n3. List impacted tests.',
        badge: 'md',
      },
    ],
    agents: [
      {
        id: 'codex-implementation-subagent',
        titleKey: 'marketplace.editor.scaffold.agents.reviewAgent.title',
        descriptionKey: 'marketplace.editor.scaffold.agents.reviewAgent.description',
        title: 'implementation-subagent',
        description: 'Codex subagent for bounded implementation work.',
        path: 'agents/implementation-subagent.md',
        content: '# Implementation subagent\n\nYou own a narrow code change and report files changed, tests run, and follow-up risks.',
        badge: 'subagent',
      },
    ],
    commands: [
      {
        id: 'codex-plan-change',
        titleKey: 'marketplace.editor.scaffold.commands.reviewSummary.title',
        descriptionKey: 'marketplace.editor.scaffold.commands.reviewSummary.description',
        title: '/plan-change',
        description: 'Draft a compact implementation plan for the current Codex task.',
        path: 'commands/plan-change.md',
        content: '# /plan-change\n\nCreate a short implementation plan from the current request and code context.',
        badge: 'slash',
        code: '/plan-change',
      },
    ],
    mcp: [
      {
        id: 'codex-figma-context',
        titleKey: 'marketplace.editor.scaffold.mcp.repositoryContext.title',
        descriptionKey: 'marketplace.editor.scaffold.mcp.repositoryContext.description',
        title: 'figma-context',
        description: 'Codex MCP server for Figma design metadata.',
        path: 'mcp/figma-context.json',
        content: '{\n  "name": "figma-context",\n  "transport": "http",\n  "url": "https://api.figma.com/mcp"\n}',
        badge: 'http',
        code: '',
        meta: [
          { labelKey: 'marketplace.editor.featureMeta.labels.transport', value: 'http' },
        ],
      },
    ],
    hooks: [
      {
        id: 'codex-test-before-finish',
        titleKey: 'marketplace.editor.scaffold.hooks.reviewPreSubmit.title',
        descriptionKey: 'marketplace.editor.scaffold.hooks.reviewPreSubmit.description',
        title: 'test-before-finish',
        description: 'Runs targeted verification before finishing a Codex change.',
        path: 'hooks/test-before-finish.json',
        content: '{\n  "hooks": {\n    "Stop": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "npm test", "timeout": 120 }] }]\n  }\n}',
        badge: 'Stop',
        code: 'npm test',
        meta: [
          { labelKey: 'marketplace.editor.featureMeta.labels.type', value: 'command' },
          { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: '*' },
          { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: '120s' },
        ],
      },
    ],
    outputStyle: [],
    policies: [],
  },
  gemini: {
    ...claudeCodeScaffoldFeatureItems,
    skills: [
      {
        id: 'gemini-workspace-scan',
        titleKey: 'marketplace.editor.scaffold.skills.reviewChecklist.title',
        descriptionKey: 'marketplace.editor.scaffold.skills.reviewChecklist.description',
        title: 'Workspace scan',
        description: 'Gemini skill for summarizing workspace structure.',
        path: 'skills/workspace-scan/SKILL.md',
        content: '# Workspace scan\n\nScan workspace folders and produce a concise project map for Gemini CLI.',
        badge: 'md',
      },
    ],
    agents: [
      {
        id: 'gemini-research-subagent',
        titleKey: 'marketplace.editor.scaffold.agents.reviewAgent.title',
        descriptionKey: 'marketplace.editor.scaffold.agents.reviewAgent.description',
        title: 'research-subagent',
        description: 'Gemini subagent for local documentation and codebase research.',
        path: 'agents/research-subagent.md',
        content: '# Research subagent\n\nGather local context, cite relevant files, and return concise findings.',
        badge: 'subagent',
      },
    ],
    commands: [
      {
        id: 'gemini-workspace-summary',
        titleKey: 'marketplace.editor.scaffold.commands.reviewSummary.title',
        descriptionKey: 'marketplace.editor.scaffold.commands.reviewSummary.description',
        title: '/workspace-summary',
        description: 'Gemini slash command for workspace status summaries.',
        path: 'commands/workspace-summary.toml',
        content: 'prompt = """\nSummarize workspace structure, changed files, and likely next steps for `{{args}}`.\n\nInclude concise risks and recommended verification.\n"""',
        badge: 'toml',
        code: '/workspace-summary',
      },
    ],
    mcp: [],
    hooks: [
      {
        id: 'gemini-session-start',
        titleKey: 'marketplace.editor.scaffold.hooks.reviewPreSubmit.title',
        descriptionKey: 'marketplace.editor.scaffold.hooks.reviewPreSubmit.description',
        title: 'session-start-context',
        description: 'Loads workspace context when a Gemini session starts.',
        path: 'hooks/session-start-context.json',
        content: '{\n  "hooks": {\n    "BeforeTool": [{ "matcher": "*", "sequential": true, "hooks": [{ "type": "command", "name": "load-context", "command": "gemini context load", "timeout": 60000, "description": "Load workspace context before tool execution." }] }]\n  }\n}',
        badge: 'BeforeTool',
        code: 'gemini context load',
        meta: [
          { labelKey: 'marketplace.editor.featureMeta.labels.type', value: 'command' },
          { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: '*' },
          { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: '60000ms' },
          { labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: 'true' },
        ],
      },
    ],
    outputStyle: [],
    policies: [
      {
        id: 'gemini-safe-shell',
        titleKey: 'marketplace.editor.scaffold.policies.safeShell.title',
        descriptionKey: 'marketplace.editor.scaffold.policies.safeShell.description',
        title: 'safe-shell',
        description: 'Gemini policy rules for blocking destructive shell patterns.',
        path: 'policies/safe-shell.toml',
        content: '[rule]\nname = "block-destructive-shell"\ndescription = "Block destructive shell commands in shared workspaces."\n\n[[rule.matchers]]\ntool = "run_shell_command"\npattern = "rm -rf"\n',
        badge: 'toml',
      },
    ],
  },
};

const getMarketplaceScaffoldFeatureItems = (provider: MarketplaceProvider): MarketplaceEditorFeatureItems => providerScaffoldFeatureItems[provider];

export const MarketplaceEditorView: React.FC<MarketplaceEditorViewProps> = ({ mode }) => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const params = useParams();
  const routeProvider = params.provider === 'codex' || params.provider === 'gemini' || params.provider === 'claude-code'
    ? params.provider
    : null;
  const [provider, setProvider] = React.useState<MarketplaceProvider | null>(
    routeProvider ?? (mode === 'edit' ? 'claude-code' : null),
  );
  const [packageId, setPackageId] = React.useState(params.packageId ?? '');
  const [displayName, setDisplayName] = React.useState(params.packageId ?? '');
  const [description, setDescription] = React.useState('');
  const [isDirty, setIsDirty] = React.useState(false);
  const [resourceCommitVersion, setResourceCommitVersion] = React.useState(0);
  const [resourceDiscardVersion, setResourceDiscardVersion] = React.useState(0);
  const [activeTab, setActiveTab] = React.useState<MarketplaceEditorTab>('basic');
  const [saveStatus, setSaveStatus] = React.useState<'idle' | 'success' | 'error' | 'conflict'>('idle');
  const [showLeaveDialog, setShowLeaveDialog] = React.useState(false);
  const [revision, setRevision] = React.useState('');
  const [loadedDetail, setLoadedDetail] = React.useState<MarketplacePackageDetail | null>(null);
  const [packageFiles, setPackageFiles] = React.useState<MarketplacePackageFile[]>([]);
  const [requiredDraft, setRequiredDraft] = React.useState<MarketplaceRequiredDraft | null>(null);
  const visibleEditorTabs = provider ? providerEditorTabs[provider] : [];
  const resolvedPackageId = packageId || t('marketplace.editor.fields.packageIdPreviewFallback');
  const resolvedDisplayName = displayName || packageId || t('marketplace.editor.fields.displayNamePlaceholder');
  const packageRoot = provider ? getMarketplacePackageRoot(provider, resolvedPackageId) : '';
  const featureItems = React.useMemo(
    () => {
      if (!provider) return null;
      const detailItems = marketplaceFeatureItemsFromDetail(loadedDetail);
      if (detailItems) return detailItems;
      return mode === 'create' ? getMarketplaceScaffoldFeatureItems(provider) : emptyMarketplaceFeatureItems();
    },
    [loadedDetail, mode, provider],
  );
  const packageFileTree = React.useMemo(
    () => provider ? createMarketplacePackageFileTree(provider, packageRoot, resolvedDisplayName, packageFiles) : [],
    [packageFiles, packageRoot, provider, resolvedDisplayName],
  );

  const markDirty = () => {
    setIsDirty(true);
    setSaveStatus('idle');
  };
  const handleMcpItemsChange = React.useCallback((items: MarketplaceEditorResourceItem[]) => {
    setPackageFiles(prev => marketplaceApplyMcpItemsToPackageFiles(prev, items));
  }, []);
  const savePackage = async (): Promise<boolean> => {
    if (!provider) {
      setSaveStatus('error');
      return false;
    }
    if (!packageId.trim()) {
      setSaveStatus('error');
      return false;
    }
    if (requiredDraft?.listingJsonError || requiredDraft?.manifestJsonError) {
      setSaveStatus('error');
      return false;
    }
    try {
      if (mode === 'create') {
        const created = await createPackage({
          provider,
          packageId: packageId.trim(),
          displayName: displayName.trim() || packageId.trim(),
          description: description.trim(),
        });
        setRevision(created.revision);
      } else {
        const listing = provider === 'gemini' ? undefined : parseMarketplaceJsonObject(requiredDraft?.listingJson ?? '');
        const manifest = parseMarketplaceJsonObject(requiredDraft?.manifestJson ?? '');
        const result = await saveMarketplacePackage({
          provider,
          packageId: packageId.trim(),
          revision,
          ...(listing ? { listing } : {}),
          ...(manifest ? { manifest } : {}),
          packageFiles,
        });
        setLoadedDetail(result.package);
        setPackageFiles(result.package.packageFiles);
        setRevision(result.revision);
        setDisplayName(result.package.displayName);
        setDescription(result.package.description ?? '');
      }
      setResourceCommitVersion(version => version + 1);
      setIsDirty(false);
      setSaveStatus('success');
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setSaveStatus(message.includes('revision_conflict') ? 'conflict' : 'error');
      return false;
    }
  };
  const discardPackageDrafts = () => {
    setResourceDiscardVersion(version => version + 1);
    setIsDirty(false);
    setSaveStatus('idle');
  };
  const navigateBack = () => {
    if (isDirty) {
      setShowLeaveDialog(true);
      return;
    }
    navigate('/marketplace/packages');
  };

  React.useEffect(() => {
    if (!provider) return;
    if (!providerEditorTabs[provider].includes(activeTab)) {
      setActiveTab('basic');
    }
  }, [activeTab, provider]);

  React.useEffect(() => {
    if (mode !== 'edit' || !provider || !params.packageId) return;
    let isActive = true;
    void getPackage(provider, params.packageId)
      .then(detail => {
        if (!isActive) return;
        setLoadedDetail(detail);
        setPackageId(detail.packageId);
        setDisplayName(detail.displayName);
        setDescription(detail.description ?? '');
        setRevision(detail.revision);
        setPackageFiles(detail.packageFiles);
      })
      .catch(() => {
        if (isActive) setSaveStatus('error');
      });
    return () => { isActive = false; };
  }, [mode, params.packageId, provider]);

  React.useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!isDirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  if (mode === 'create' && !provider) {
    return (
      <MarketplaceProviderSelectionStep
        onBack={() => navigate('/marketplace/packages')}
        onSelect={(nextProvider) => {
          setProvider(nextProvider);
          setActiveTab('basic');
        }}
      />
    );
  }

  if (!provider || !featureItems) {
    return null;
  }

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={mode === 'create' ? t('marketplace.editor.createTitle') : t('marketplace.editor.editTitle')}
        icon={PenSquare}
        info={(
          <div className="flex items-center gap-2 text-xs">
            {isDirty ? <span className="text-amber-600">{t('marketplace.editor.dirty')}</span> : null}
            {saveStatus === 'success' ? <span className="text-emerald-600">{t('marketplace.editor.saveStatus.success')}</span> : null}
            {saveStatus === 'error' ? <span className="text-destructive">{t('marketplace.editor.saveStatus.validationError')}</span> : null}
            {saveStatus === 'conflict' ? <span className="text-destructive">{t('marketplace.editor.saveStatus.revisionConflict')}</span> : null}
          </div>
        )}
        actions={(
          <div className="flex items-center gap-2">
            {isDirty ? (
              <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={discardPackageDrafts}>
                {t('marketplace.editor.actions.discard')}
              </Button>
            ) : null}
            <Button size="sm" className="h-7 px-2 text-xs" onClick={savePackage}>
              <Save className="mr-1.5 h-3.5 w-3.5" />
              {t('marketplace.editor.actions.save')}
            </Button>
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={navigateBack}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              {t('marketplace.common.actions.back')}
            </Button>
          </div>
        )}
      />

      <div className="h-[calc(100%-3rem)] overflow-auto">
        <Tabs value={activeTab} onValueChange={value => setActiveTab(value as MarketplaceEditorTab)} className="flex h-full flex-col">
          <TopTabsBar>
            <TopTabsList>
              {visibleEditorTabs.map(tab => {
                const Icon = tabIcons[tab];
                const count = tab === 'basic' || tab === 'agentsMd'
                  ? 0
                  : tab === 'files'
                    ? countMarketplaceFileNodes(packageFileTree)
                    : (featureItems?.[tab].length ?? 0);
                return (
                  <TopTabsTrigger key={tab} value={tab}>
                    <Icon className="h-4 w-4" />
                    {t(getMarketplaceEditorTabLabelKey(provider, tab))}
                    <TopTabsCountBadge count={count} />
                  </TopTabsTrigger>
                );
              })}
            </TopTabsList>
          </TopTabsBar>

          <TabsContent value="basic" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceEditorBasicSection
              mode={mode}
              provider={provider}
              packageId={packageId}
              displayName={displayName}
              description={description}
              detail={loadedDetail}
              onPackageIdChange={(value) => { setPackageId(value); markDirty(); }}
              onDisplayNameChange={(value) => { setDisplayName(value); markDirty(); }}
              onDescriptionChange={(value) => { setDescription(value); markDirty(); }}
              onRequiredDraftChange={setRequiredDraft}
              onDirty={markDirty}
            />
          </TabsContent>

          <TabsContent value="agentsMd" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceAgentsMdEditor onDirty={markDirty} />
          </TabsContent>

          <TabsContent value="skills" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceSkillsFileManager key={`${provider}-skills`} items={featureItems.skills} onDirty={markDirty} />
          </TabsContent>

          <TabsContent value="agents" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceMarkdownEditorViewer
              key={`${provider}-agents`}
              tab="agents"
              icon={Bot}
              items={featureItems.agents}
              commitVersion={resourceCommitVersion}
              discardVersion={resourceDiscardVersion}
              onDirty={markDirty}
            />
          </TabsContent>

          <TabsContent value="commands" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceMarkdownEditorViewer
              key={`${provider}-commands`}
              tab="commands"
              icon={Command}
              items={featureItems.commands}
              format={provider === 'gemini' ? 'toml' : 'markdown'}
              commitVersion={resourceCommitVersion}
              discardVersion={resourceDiscardVersion}
              onDirty={markDirty}
            />
          </TabsContent>

          <TabsContent value="mcp" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceEditorFeatureSection
              key={`${provider}-mcp`}
              provider={provider}
              tab="mcp"
              icon={Network}
              items={featureItems.mcp}
              onDirty={markDirty}
              onItemsChange={handleMcpItemsChange}
            />
          </TabsContent>

          <TabsContent value="hooks" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceEditorFeatureSection key={`${provider}-hooks`} provider={provider} tab="hooks" icon={Zap} items={featureItems.hooks} onDirty={markDirty} />
          </TabsContent>

          <TabsContent value="outputStyle" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceMarkdownEditorViewer
              key={`${provider}-output-style`}
              tab="outputStyle"
              icon={Wand2}
              items={featureItems.outputStyle}
              commitVersion={resourceCommitVersion}
              discardVersion={resourceDiscardVersion}
              onDirty={markDirty}
            />
          </TabsContent>

          <TabsContent value="policies" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplaceMarkdownEditorViewer
              key={`${provider}-policies`}
              tab="policies"
              icon={Workflow}
              items={featureItems.policies}
              format="toml"
              commitVersion={resourceCommitVersion}
              discardVersion={resourceDiscardVersion}
              onDirty={markDirty}
            />
          </TabsContent>

          <TabsContent value="files" className="flex-1 overflow-auto !m-0 !p-0">
            <MarketplacePackageFileManager
              key={packageRoot}
              packageRoot={packageRoot}
              initialNodes={packageFileTree}
              onDirty={markDirty}
              onPackageFilesChange={setPackageFiles}
            />
          </TabsContent>
        </Tabs>
      </div>
      <MarketplaceEditorLeaveDialog
        open={showLeaveDialog}
        onOpenChange={setShowLeaveDialog}
        onSave={() => {
          void savePackage().then(saved => {
            if (saved) navigate('/marketplace/packages');
          });
        }}
        onDiscard={() => navigate('/marketplace/packages')}
      />
    </div>
  );
};

interface MarketplaceEditorLeaveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: () => void;
  onDiscard: () => void;
}

const MarketplaceEditorLeaveDialog: React.FC<MarketplaceEditorLeaveDialogProps> = ({
  open,
  onOpenChange,
  onSave,
  onDiscard,
}) => {
  const { t } = useI18n();

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>{t('marketplace.editor.unsaved.title')}</AlertDialogTitle>
          <AlertDialogDescription>{t('marketplace.editor.unsaved.description')}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => onOpenChange(false)}>
            {t('marketplace.common.actions.cancel')}
          </AlertDialogCancel>
          <AlertDialogAction className="border border-input bg-background text-foreground hover:bg-accent hover:text-accent-foreground" onClick={onDiscard}>
            {t('marketplace.editor.actions.discard')}
          </AlertDialogAction>
          <AlertDialogAction onClick={onSave}>
            {t('marketplace.editor.actions.save')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

interface MarketplaceProviderSelectionStepProps {
  onBack: () => void;
  onSelect: (provider: MarketplaceProvider) => void;
}

const marketplaceProviderOptions: Array<{
  provider: MarketplaceProvider;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  {
    provider: 'claude-code',
    icon: Bot,
  },
  {
    provider: 'codex',
    icon: Terminal,
  },
  {
    provider: 'gemini',
    icon: Sparkles,
  },
];

const MarketplaceProviderSelectionStep: React.FC<MarketplaceProviderSelectionStepProps> = ({
  onBack,
  onSelect,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('marketplace.editor.providerStep.title')}
        icon={FolderPlus}
        info={(
          <span className="text-xs text-muted-foreground">
            {t('marketplace.editor.providerStep.description')}
          </span>
        )}
        actions={(
          <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onBack}>
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.common.actions.back')}
          </Button>
        )}
      />

      <div className="h-[calc(100%-3rem)] overflow-auto p-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-foreground">
              {t('marketplace.editor.providerStep.heading')}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t('marketplace.editor.providerStep.help')}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {marketplaceProviderOptions.map(({ provider: optionProvider, icon: Icon }) => {
              const editorTabs = providerEditorTabs[optionProvider].filter(tab => tab !== 'basic' && tab !== 'files');

              return (
              <button
                key={optionProvider}
                type="button"
                className="group flex h-full flex-col rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary/60 hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => onSelect(optionProvider)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-muted-foreground group-hover:text-primary">
                      <Icon className="h-4 w-4" />
                    </span>
                    <div>
                      <div className="text-sm font-semibold text-foreground">
                        {t(`marketplace.providers.${optionProvider}`)}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {t(`marketplace.editor.providerStep.options.${optionProvider}.description`)}
                      </div>
                    </div>
                  </div>
                  <ChevronRight className="mt-1 h-4 w-4 text-muted-foreground group-hover:text-primary" />
                </div>

                <div className="mt-4 space-y-2">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t('marketplace.editor.providerStep.sectionsLabel')}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {editorTabs.map(tab => (
                      <Badge key={tab} variant="secondary" className="rounded-md px-2 py-0.5 text-[11px]">
                        {t(getMarketplaceEditorTabLabelKey(optionProvider, tab))}
                      </Badge>
                    ))}
                  </div>
                </div>
              </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

interface MarketplaceEditorBasicSectionProps {
  mode: 'create' | 'edit';
  provider: MarketplaceProvider;
  packageId: string;
  displayName: string;
  description: string;
  detail: MarketplacePackageDetail | null;
  onPackageIdChange: (value: string) => void;
  onDisplayNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onRequiredDraftChange: (draft: MarketplaceRequiredDraft) => void;
  onDirty: () => void;
}

interface MarketplaceRequiredDraft {
  marketplaceName: string;
  ownerName: string;
  packageName: string;
  sourcePath: string;
  codexInstallationPolicy: string;
  codexAuthenticationPolicy: string;
  category: string;
  manifestName: string;
  manifestVersion: string;
  manifestDescription: string;
  listingJson: string;
  manifestJson: string;
  listingJsonError: string | null;
  manifestJsonError: string | null;
}

type MarketplaceJsonDocument = 'listing' | 'manifest';
type MarketplaceRequiredEditorTab = 'form' | 'json';

interface MarketplaceRequiredDraftFallbacks {
  packageName: string;
  codexMarketplaceName: string;
  claudeMarketplaceName: string;
  ownerName: string;
  description: string;
}

const marketplaceJsonIndent = 2;

const stringifyMarketplaceJson = (value: Record<string, unknown>): string => (
  JSON.stringify(value, null, marketplaceJsonIndent)
);

const isJsonObject = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

const marketplaceBinaryExtensions = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'ico', 'pdf', 'zip', 'tar', 'gz', 'woff', 'woff2']);
const marketplacePreviewableImageExtensions = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp']);

const isMarketplaceBinaryFile = (node: FileTreeNode | null): boolean => {
  if (!node || node.type !== 'file') return false;
  if (node.metadata?.binary === true) return true;
  const extension = node.extension?.toLowerCase() ?? node.name.split('.').pop()?.toLowerCase() ?? '';
  return marketplaceBinaryExtensions.has(extension);
};

const isMarketplacePreviewableBinaryFile = (node: FileTreeNode | null): boolean => {
  if (!node || !isMarketplaceBinaryFile(node)) return false;
  const extension = node.extension?.toLowerCase() ?? node.name.split('.').pop()?.toLowerCase() ?? '';
  return marketplacePreviewableImageExtensions.has(extension) && typeof node.metadata?.previewDataUrl === 'string';
};

const getStringField = (value: unknown, fallback = ''): string => (
  typeof value === 'string' ? value : fallback
);

const parseMarketplaceJsonObject = (value: string): Record<string, unknown> | null => {
  try {
    const parsed: unknown = JSON.parse(value);
    return isJsonObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
};

const createMarketplaceSourceValue = (provider: MarketplaceProvider, sourcePath: string): string | Record<string, string> => (
  provider === 'codex'
    ? { source: 'local', path: sourcePath }
    : sourcePath
);

const createMarketplaceListingJson = (
  provider: MarketplaceProvider,
  draft: Pick<MarketplaceRequiredDraft, 'packageName' | 'sourcePath' | 'codexInstallationPolicy' | 'codexAuthenticationPolicy' | 'category'>,
): Record<string, unknown> => {
  if (provider === 'gemini') {
    return {};
  }

  const entry: Record<string, unknown> = {
    name: draft.packageName,
    source: createMarketplaceSourceValue(provider, draft.sourcePath),
  };

  if (provider === 'codex') {
    entry.policy = {
      installation: draft.codexInstallationPolicy,
      authentication: draft.codexAuthenticationPolicy,
    };
    entry.category = draft.category;
  }

  return entry;
};

const createMarketplaceManifestJson = (
  provider: MarketplaceProvider,
  draft: Pick<MarketplaceRequiredDraft, 'manifestName' | 'manifestVersion' | 'manifestDescription'>,
): Record<string, unknown> => ({
  name: draft.manifestName,
  ...(provider === 'claude-code' ? {} : { version: draft.manifestVersion }),
  ...(provider === 'codex' ? { description: draft.manifestDescription } : {}),
});

const createInitialMarketplaceRequiredDraft = (
  provider: MarketplaceProvider,
  packageId: string,
  displayName: string,
  description: string,
  fallbacks: MarketplaceRequiredDraftFallbacks,
): MarketplaceRequiredDraft => {
  const fallbackPackageName = packageId || displayName;
  const fallbackDescription = description || fallbacks.description;
  const draft = {
    marketplaceName: provider === 'codex' ? fallbacks.codexMarketplaceName : fallbacks.claudeMarketplaceName,
    ownerName: fallbacks.ownerName,
    packageName: fallbackPackageName,
    sourcePath: `./plugins/${fallbackPackageName}`,
    codexInstallationPolicy: 'AVAILABLE',
    codexAuthenticationPolicy: 'ON_INSTALL',
    category: 'Productivity',
    manifestName: fallbackPackageName,
    manifestVersion: '0.1.0',
    manifestDescription: fallbackDescription,
    listingJson: '',
    manifestJson: '',
    listingJsonError: null,
    manifestJsonError: null,
  };

  return {
    ...draft,
    listingJson: provider === 'gemini'
      ? ''
      : stringifyMarketplaceJson(createMarketplaceListingJson(provider, draft)),
    manifestJson: stringifyMarketplaceJson(createMarketplaceManifestJson(provider, draft)),
  };
};

const createMarketplaceRequiredDraftFromDetail = (
  provider: MarketplaceProvider,
  detail: MarketplacePackageDetail | null,
  packageId: string,
  displayName: string,
  description: string,
  fallbacks: MarketplaceRequiredDraftFallbacks,
): MarketplaceRequiredDraft => {
  const draft = createInitialMarketplaceRequiredDraft(provider, packageId, displayName, description, fallbacks);
  if (!detail) return draft;
  const manifest = isJsonObject(detail.manifestMetadata) ? detail.manifestMetadata : {};
  const manifestName = getStringField(manifest.name, detail.packageId);
  const manifestDescription = getStringField(manifest.description, detail.description ?? draft.manifestDescription);
  const next = {
    ...draft,
    packageName: detail.packageId,
    manifestName,
    manifestVersion: getStringField(manifest.version, detail.version ?? draft.manifestVersion),
    manifestDescription,
    manifestJson: stringifyMarketplaceJson({
      ...manifest,
      name: manifestName,
      ...(provider !== 'claude-code' ? { version: getStringField(manifest.version, detail.version ?? draft.manifestVersion) } : {}),
      ...(provider === 'codex' ? { description: manifestDescription } : {}),
    }),
  };
  return {
    ...next,
    listingJson: provider === 'gemini'
      ? ''
      : mergeMarketplaceListingJson(provider, draft.listingJson, next),
  };
};

const mergeMarketplaceListingJson = (
  provider: MarketplaceProvider,
  currentJson: string,
  draft: MarketplaceRequiredDraft,
): string => {
  const current = parseMarketplaceJsonObject(currentJson) ?? {};

  const nextEntry: Record<string, unknown> = {
    ...current,
    name: draft.packageName,
    source: createMarketplaceSourceValue(provider, draft.sourcePath),
  };

  if (provider === 'codex') {
    const policy = isJsonObject(current.policy) ? current.policy : {};
    nextEntry.policy = {
      ...policy,
      installation: draft.codexInstallationPolicy,
      authentication: draft.codexAuthenticationPolicy,
    };
    nextEntry.category = draft.category;
  }

  return stringifyMarketplaceJson(nextEntry);
};

const mergeMarketplaceManifestJson = (
  provider: MarketplaceProvider,
  currentJson: string,
  draft: MarketplaceRequiredDraft,
): string => {
  const current = parseMarketplaceJsonObject(currentJson) ?? {};
  const next: Record<string, unknown> = {
    ...current,
    name: draft.manifestName,
  };

  if (provider !== 'claude-code') {
    next.version = draft.manifestVersion;
  }
  if (provider === 'codex') {
    next.description = draft.manifestDescription;
  }

  return stringifyMarketplaceJson(next);
};

const MarketplaceEditorBasicSection: React.FC<MarketplaceEditorBasicSectionProps> = ({
  mode,
  provider,
  packageId,
  displayName,
  description,
  detail,
  onPackageIdChange,
  onDisplayNameChange,
  onDescriptionChange,
  onRequiredDraftChange,
  onDirty,
}) => {
  const { t } = useI18n();
  const requiredDraftFallbacks = React.useMemo<MarketplaceRequiredDraftFallbacks>(() => ({
    packageName: t('marketplace.editor.defaults.packageName'),
    codexMarketplaceName: t('marketplace.editor.defaults.codexMarketplaceName'),
    claudeMarketplaceName: t('marketplace.editor.defaults.claudeMarketplaceName'),
    ownerName: t('marketplace.editor.defaults.ownerName'),
    description: t('marketplace.editor.defaults.description'),
  }), [t]);
  const [draft, setDraft] = React.useState<MarketplaceRequiredDraft>(() => (
    createMarketplaceRequiredDraftFromDetail(provider, detail, packageId, displayName, description, requiredDraftFallbacks)
  ));
  const [providerGuidanceDraft, setProviderGuidanceDraft] = React.useState('');
  const [readmeDraft, setReadmeDraft] = React.useState('');

  React.useEffect(() => {
    if (!detail) return;
    setDraft(createMarketplaceRequiredDraftFromDetail(provider, detail, packageId, displayName, description, requiredDraftFallbacks));
  }, [detail?.revision, provider]);

  React.useEffect(() => {
    onRequiredDraftChange(draft);
  }, [draft, onRequiredDraftChange]);

  const resolvedPackageId = draft.packageName || packageId || t('marketplace.editor.fields.packageIdPreviewFallback');
  const resolvedDisplayName = displayName || draft.packageName || t('marketplace.editor.fields.displayNamePlaceholder');
  const manifestFile = {
    'claude-code': '.claude-plugin/plugin.json',
    codex: '.codex-plugin/plugin.json',
    gemini: 'gemini-extension.json',
  }[provider];
  const registryPath = provider === 'gemini'
    ? `gemini/extensions/${resolvedPackageId}`
    : `${provider}/plugins/${resolvedPackageId}`;

  const updateRequiredDraft = (updates: Partial<MarketplaceRequiredDraft>) => {
    setDraft(prev => {
      const next = { ...prev, ...updates };
      return {
        ...next,
        listingJson: provider === 'gemini'
          ? next.listingJson
          : mergeMarketplaceListingJson(provider, prev.listingJson, next),
        manifestJson: mergeMarketplaceManifestJson(provider, prev.manifestJson, next),
        listingJsonError: provider === 'gemini' ? next.listingJsonError : null,
        manifestJsonError: null,
      };
    });
    onDirty();
  };

  const updatePackageName = (value: string) => {
    onPackageIdChange(value);
    onDisplayNameChange(value);
    updateRequiredDraft({
      packageName: value,
      manifestName: value,
      sourcePath: `./plugins/${value || requiredDraftFallbacks.packageName}`,
    });
  };

  const updateManifestDescription = (value: string) => {
    onDescriptionChange(value);
    updateRequiredDraft({ manifestDescription: value });
  };

  const updateJsonDraft = (document: MarketplaceJsonDocument, value: string) => {
    const parsed = parseMarketplaceJsonObject(value);
    const errorKey = parsed ? null : t('marketplace.editor.required.json.parseError');

    if (!parsed) {
      setDraft(prev => ({
        ...prev,
        [document === 'listing' ? 'listingJson' : 'manifestJson']: value,
        [document === 'listing' ? 'listingJsonError' : 'manifestJsonError']: errorKey,
      }));
      onDirty();
      return;
    }

    setDraft(prev => {
      if (document === 'listing') {
        const source = parsed.source;
        const sourcePath = typeof source === 'string'
          ? source
          : isJsonObject(source)
            ? getStringField(source.path, prev.sourcePath)
            : prev.sourcePath;
        const policy = isJsonObject(parsed.policy) ? parsed.policy : {};
        const packageName = getStringField(parsed.name, prev.packageName);
        const next = {
          ...prev,
          packageName,
          manifestName: packageName,
          sourcePath,
          codexInstallationPolicy: getStringField(policy.installation, prev.codexInstallationPolicy),
          codexAuthenticationPolicy: getStringField(policy.authentication, prev.codexAuthenticationPolicy),
          category: getStringField(parsed.category, prev.category),
          listingJson: '',
          listingJsonError: null,
        };

        if (packageName !== prev.packageName) {
          onPackageIdChange(packageName);
          onDisplayNameChange(packageName);
        }

        return {
          ...next,
          listingJson: mergeMarketplaceListingJson(provider, stringifyMarketplaceJson(parsed), next),
        };
      }

      const manifestName = getStringField(parsed.name, prev.manifestName);
      const manifestDescription = getStringField(parsed.description, prev.manifestDescription);
      if (manifestName !== prev.manifestName) {
        onPackageIdChange(manifestName);
        onDisplayNameChange(manifestName);
      }
      if (provider === 'codex' && manifestDescription !== prev.manifestDescription) {
        onDescriptionChange(manifestDescription);
      }

      return {
        ...prev,
        packageName: manifestName,
        manifestName,
        manifestVersion: getStringField(parsed.version, prev.manifestVersion),
        manifestDescription,
        manifestJson: stringifyMarketplaceJson(parsed),
        manifestJsonError: null,
      };
    });
    onDirty();
  };

  return (
    <div className="h-full overflow-auto p-6">
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fields.provider')}
            </label>
            <Select value={provider} disabled>
              <SelectTrigger className="cursor-not-allowed bg-muted">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="claude-code">{t('marketplace.providers.claude-code')}</SelectItem>
                <SelectItem value="codex">{t('marketplace.providers.codex')}</SelectItem>
                <SelectItem value="gemini">{t('marketplace.providers.gemini')}</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t('marketplace.editor.fields.providerHint')}
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fields.packageId')}
            </label>
            <Input
              value={draft.packageName}
              placeholder={t('marketplace.editor.fields.packageIdPlaceholder')}
              disabled={mode === 'edit'}
              className={mode === 'edit' ? 'cursor-not-allowed bg-muted' : ''}
              onChange={event => updatePackageName(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {t('marketplace.editor.fields.packageIdHint')}
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fields.displayName')}
            </label>
            <Input
              value={displayName}
              placeholder={t('marketplace.editor.fields.displayNamePlaceholder')}
              onChange={event => onDisplayNameChange(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fields.registryPath')}
            </label>
            <Input
              value={registryPath}
              readOnly
              className="cursor-not-allowed bg-muted font-mono text-sm"
            />
          </div>
        </div>

        <MarketplaceEditorFormSection
          title={t('marketplace.editor.requiredFields.title')}
          description={t('marketplace.editor.requiredFields.description')}
        >
          <MarketplaceFormJsonTabs
            formLabel={t('marketplace.editor.requiredTabs.form')}
            jsonLabel={t('marketplace.editor.requiredTabs.json')}
            form={(
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {provider !== 'gemini' ? (
                  <MarketplaceEditorReadonlyField
                    label={t('marketplace.editor.packageSections.fields.marketplaceName')}
                    value={draft.marketplaceName}
                    hint={t('marketplace.editor.packageSections.fields.rootMetadataHint')}
                  />
                ) : null}
                {provider === 'claude-code' ? (
                  <MarketplaceEditorReadonlyField
                    label={t('marketplace.editor.packageSections.fields.ownerName')}
                    value={draft.ownerName}
                    hint={t('marketplace.editor.packageSections.fields.rootMetadataHint')}
                  />
                ) : null}
                <MarketplaceEditorEditableField
                  label={t('marketplace.editor.packageSections.fields.packageName')}
                  value={draft.packageName}
                  onChange={updatePackageName}
                />
                {provider !== 'gemini' ? (
                  <MarketplaceEditorEditableField
                    label={t('marketplace.editor.packageSections.fields.source')}
                    value={draft.sourcePath}
                    onChange={value => updateRequiredDraft({ sourcePath: value })}
                  />
                ) : null}
                {provider === 'codex' ? (
                  <>
                    <MarketplaceEditorEditableField
                      label={t('marketplace.editor.packageSections.fields.policyInstallation')}
                      value={draft.codexInstallationPolicy}
                      onChange={value => updateRequiredDraft({ codexInstallationPolicy: value })}
                    />
                    <MarketplaceEditorEditableField
                      label={t('marketplace.editor.packageSections.fields.policyAuthentication')}
                      value={draft.codexAuthenticationPolicy}
                      onChange={value => updateRequiredDraft({ codexAuthenticationPolicy: value })}
                    />
                    <MarketplaceEditorEditableField
                      label={t('marketplace.editor.packageSections.fields.category')}
                      value={draft.category}
                      onChange={value => updateRequiredDraft({ category: value })}
                    />
                  </>
                ) : null}
                {provider !== 'claude-code' ? (
                  <>
                    <MarketplaceEditorEditableField
                      label={t('marketplace.editor.packageSections.fields.version')}
                      value={draft.manifestVersion}
                      onChange={value => updateRequiredDraft({ manifestVersion: value })}
                    />
                    {provider === 'codex' ? (
                      <div className="md:col-span-2">
                        <MarketplaceEditorTextAreaField
                          label={t('marketplace.editor.packageSections.fields.description')}
                          value={draft.manifestDescription}
                          rows={3}
                          onChange={updateManifestDescription}
                        />
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            )}
            json={(
              <MarketplaceRequiredJsonDocuments
                provider={provider}
                marketplaceFilePath={provider === 'codex' ? 'codex/.agents/plugins/marketplace.json' : 'claude-code/.claude-plugin/marketplace.json'}
                manifestFilePath={provider === 'gemini' ? `${registryPath}/gemini-extension.json` : `${registryPath}/${manifestFile}`}
                listingJson={draft.listingJson}
                listingJsonError={draft.listingJsonError}
                manifestJson={draft.manifestJson}
                manifestJsonError={draft.manifestJsonError}
                onListingJsonChange={value => updateJsonDraft('listing', value)}
                onManifestJsonChange={value => updateJsonDraft('manifest', value)}
              />
            )}
          />
        </MarketplaceEditorFormSection>

        {provider === 'gemini' ? (
          <MarketplaceEditorFormSection
            title={t('marketplace.editor.packageSections.providerGuidance.title')}
            description={t('marketplace.editor.packageSections.providerGuidance.description')}
            fileName="GEMINI.md"
          >
            <MarkdownEditor
              value={providerGuidanceDraft || `# ${resolvedDisplayName}\n\n${t('marketplace.editor.packageSections.providerGuidance.defaultBody')}`}
              onChange={(value) => {
                setProviderGuidanceDraft(value);
                onDirty();
              }}
              placeholder={t('marketplace.editor.packageSections.providerGuidance.placeholder')}
              className="min-h-[18rem]"
              textareaClassName="min-h-[12rem]"
            />
          </MarketplaceEditorFormSection>
        ) : null}

        <MarketplaceEditorFormSection
          title={t('marketplace.editor.tabs.readme')}
          description={t('marketplace.editor.packageSections.readme.description')}
          fileName="README.md"
        >
          <MarkdownEditor
            value={readmeDraft || `# ${resolvedDisplayName}\n\n${draft.manifestDescription}`}
            onChange={(value) => {
              setReadmeDraft(value);
              onDirty();
            }}
            placeholder={t('marketplace.editor.packageSections.readme.placeholder')}
            className="min-h-[22rem]"
            textareaClassName="min-h-[16rem]"
          />
        </MarketplaceEditorFormSection>
      </div>
    </div>
  );
};

interface MarketplaceEditorFormSectionProps {
  title: string;
  description: string;
  fileName?: string;
  children: React.ReactNode;
}

const MarketplaceEditorFormSection: React.FC<MarketplaceEditorFormSectionProps> = ({
  title,
  description,
  fileName,
  children,
}) => (
  <section className="space-y-4 border-t border-border pt-6 first:border-t-0 first:pt-0">
    <div className="flex items-center justify-between gap-3">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {fileName ? (
        <div className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
          {fileName}
        </div>
      ) : null}
    </div>
    {children}
  </section>
);

interface MarketplaceJsonDraftEditorProps {
  title: string;
  filePath: string;
  badgeSuffix?: string;
  value: string;
  error: string | null;
  onChange: (value: string) => void;
}

interface MarketplaceRequiredJsonDocumentsProps {
  provider: MarketplaceProvider;
  marketplaceFilePath: string;
  manifestFilePath: string;
  listingJson: string;
  listingJsonError: string | null;
  manifestJson: string;
  manifestJsonError: string | null;
  onListingJsonChange: (value: string) => void;
  onManifestJsonChange: (value: string) => void;
}

interface MarketplaceFormJsonTabsProps {
  formLabel: string;
  jsonLabel: string;
  form: React.ReactNode;
  json: React.ReactNode;
}

const MarketplaceFormJsonTabs: React.FC<MarketplaceFormJsonTabsProps> = ({
  formLabel,
  jsonLabel,
  form,
  json,
}) => {
  const [activeTab, setActiveTab] = React.useState<MarketplaceRequiredEditorTab>('form');

  return (
    <Tabs value={activeTab} onValueChange={value => setActiveTab(value as MarketplaceRequiredEditorTab)} className="space-y-6">
      <TabsList className="h-9 justify-start">
        <TabsTrigger value="form" className="h-7 px-3 text-xs">
          {formLabel}
        </TabsTrigger>
        <TabsTrigger value="json" className="h-7 px-3 text-xs">
          {jsonLabel}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="form" className="!m-0 pt-2">
        {form}
      </TabsContent>
      <TabsContent value="json" className="!m-0 pt-2">
        {json}
      </TabsContent>
    </Tabs>
  );
};

const MarketplaceRequiredJsonDocuments: React.FC<MarketplaceRequiredJsonDocumentsProps> = ({
  provider,
  marketplaceFilePath,
  manifestFilePath,
  listingJson,
  listingJsonError,
  manifestJson,
  manifestJsonError,
  onListingJsonChange,
  onManifestJsonChange,
}) => {
  const [activeDocument, setActiveDocument] = React.useState<MarketplaceJsonDocument>(
    provider === 'gemini' ? 'manifest' : 'listing',
  );
  const { t } = useI18n();
  const listingTitle = t('marketplace.editor.required.json.tabs.entry');
  const manifestTitle = provider === 'gemini'
    ? t('marketplace.editor.required.json.tabs.extension')
    : t('marketplace.editor.required.json.tabs.plugin');

  if (provider === 'gemini') {
    return (
      <MarketplaceJsonDraftEditor
        title={manifestTitle}
        filePath={manifestFilePath}
        value={manifestJson}
        error={manifestJsonError}
        onChange={onManifestJsonChange}
      />
    );
  }

  return (
    <Tabs value={activeDocument} onValueChange={value => setActiveDocument(value as MarketplaceJsonDocument)} className="space-y-5">
      <TabsList className="h-10 justify-start gap-2 p-1">
        <MarketplaceJsonDocumentTab
          value="listing"
          title={listingTitle}
          infoLabel={t('marketplace.editor.required.json.infoLabel', { document: listingTitle })}
          info={t('marketplace.editor.required.json.popovers.entry')}
        />
        <MarketplaceJsonDocumentTab
          value="manifest"
          title={manifestTitle}
          infoLabel={t('marketplace.editor.required.json.infoLabel', { document: manifestTitle })}
          info={t('marketplace.editor.required.json.popovers.plugin')}
        />
      </TabsList>
      <TabsContent value="listing" className="!m-0 pt-2">
        <MarketplaceJsonDraftEditor
          title={listingTitle}
          filePath={marketplaceFilePath}
          badgeSuffix={t('marketplace.editor.required.json.fileBadge.thisEntryOnly')}
          value={listingJson}
          error={listingJsonError}
          onChange={onListingJsonChange}
        />
      </TabsContent>
      <TabsContent value="manifest" className="!m-0 pt-2">
        <MarketplaceJsonDraftEditor
          title={manifestTitle}
          filePath={manifestFilePath}
          value={manifestJson}
          error={manifestJsonError}
          onChange={onManifestJsonChange}
        />
      </TabsContent>
    </Tabs>
  );
};

interface MarketplaceJsonDocumentTabProps {
  value: MarketplaceJsonDocument;
  title: string;
  infoLabel: string;
  info: string;
}

const MarketplaceJsonDocumentTab: React.FC<MarketplaceJsonDocumentTabProps> = ({
  value,
  title,
  infoLabel,
  info,
}) => {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="inline-flex h-8 items-center rounded-sm">
      <TabsTrigger value={value} className="h-8 rounded-r-none px-3 text-xs">
        {title}
      </TabsTrigger>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={infoLabel}
            className="ml-1 inline-flex h-8 w-8 items-center justify-center rounded-sm text-muted-foreground hover:bg-background/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="text-xs leading-relaxed" side="bottom" align="start">
          {info}
        </PopoverContent>
      </Popover>
    </div>
  );
};

const MarketplaceJsonDraftEditor: React.FC<MarketplaceJsonDraftEditorProps> = ({
  title,
  filePath,
  badgeSuffix,
  value,
  error,
  onChange,
}) => (
  <div className="space-y-3 rounded-md border border-border bg-muted/20 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
          {filePath}
        </span>
        {badgeSuffix ? (
          <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
            {badgeSuffix}
          </span>
        ) : null}
      </div>
    </div>
    <div aria-label={title} className="h-[28rem] overflow-hidden rounded-md border border-border bg-background">
      <CodeTextEditor
        fileName={filePath}
        content={value}
        originalContent={value}
        onContentChange={onChange}
        onModifiedChange={() => undefined}
      />
    </div>
    {error ? (
      <p className="text-xs font-medium text-destructive">{error}</p>
    ) : null}
  </div>
);

interface MarketplaceEditorReadonlyFieldProps {
  label: string;
  value: string;
  hint?: string;
}

const MarketplaceEditorReadonlyField: React.FC<MarketplaceEditorReadonlyFieldProps> = ({ label, value, hint }) => (
  <div className="space-y-2">
    <label className="text-sm font-semibold text-foreground">{label}</label>
    <Input value={value} readOnly className="cursor-not-allowed bg-muted font-mono text-sm" />
    {hint ? (
      <p className="text-xs text-muted-foreground">{hint}</p>
    ) : null}
  </div>
);

interface MarketplaceEditorEditableFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

const MarketplaceEditorEditableField: React.FC<MarketplaceEditorEditableFieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <label className="text-sm font-semibold text-foreground">{label}</label>
    <Input value={value} onChange={event => onChange(event.target.value)} />
  </div>
);

interface MarketplaceEditorTextAreaFieldProps {
  label: string;
  value: string;
  rows?: number;
  onChange: (value: string) => void;
}

const MarketplaceEditorTextAreaField: React.FC<MarketplaceEditorTextAreaFieldProps> = ({
  label,
  value,
  rows = 3,
  onChange,
}) => (
  <div className="space-y-2">
    <label className="text-sm font-semibold text-foreground">{label}</label>
    <Textarea value={value} rows={rows} onChange={event => onChange(event.target.value)} />
  </div>
);

interface MarketplaceAgentsMdEditorProps {
  onDirty: () => void;
}

const MarketplaceAgentsMdEditor: React.FC<MarketplaceAgentsMdEditorProps> = ({ onDirty }) => {
  const { t } = useI18n();
  const [content, setContent] = React.useState(
    '# AGENTS.md\n\nUse this package to guide CLI behavior in the target workspace.\n\n## Review policy\n\n- Report findings before summaries.\n- Include concrete file references.\n- Prefer existing verification commands.\n',
  );
  const [savedContent, setSavedContent] = React.useState(content);
  const hasUnsavedChanges = content !== savedContent;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    downloadBlob(blob, 'AGENTS.md');
  };

  return (
    <MarkdownDocumentShell
      title={t('marketplace.editor.agentsMd.title')}
      refreshLabel={t('marketplace.common.actions.refresh')}
      saveLabel={t('marketplace.common.actions.save')}
      runtimeLoadingLabel={t('marketplace.editor.agentsMd.status.loading')}
      loadingLabel={t('marketplace.editor.agentsMd.status.loading')}
      isRuntimeReady
      isLoading={false}
      isSaving={false}
      value={content}
      onChange={(value) => {
        setContent(value);
        onDirty();
      }}
      onRefresh={() => setContent(savedContent)}
      onSave={() => setSavedContent(content)}
      saveDisabled={!hasUnsavedChanges}
      statusMessage={(
        <span className="font-mono text-xs text-muted-foreground">
          AGENTS.md
        </span>
      )}
      placeholder={t('marketplace.editor.agentsMd.placeholder')}
      headerExtras={(
        <>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => void handleCopy()}
          >
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.editor.agentsMd.actions.copy')}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={handleDownload}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.editor.agentsMd.actions.download')}
          </Button>
        </>
      )}
    />
  );
};

interface MarketplaceSkillsFileManagerProps {
  items: MarketplaceEditorResourceItem[];
  onDirty: () => void;
}

const MarketplaceSkillsFileManager: React.FC<MarketplaceSkillsFileManagerProps> = ({ items, onDirty }) => {
  const { t } = useI18n();
  const initialNodes = React.useMemo(() => marketplaceFeatureItemsToFileTree(items, 'skills'), [items]);
  const firstFilePath = React.useMemo(() => marketplaceFindFirstFilePath(initialNodes), [initialNodes]);
  const treeState = useFileTreeState({
    initialNodes,
    initialExpandedIds: marketplaceDirectoryPaths(initialNodes),
    initialSelectedId: firstFilePath,
    enableMultiSelect: true,
  });
  const [dialogState, setDialogState] = React.useState<MarketplaceFileDialogState>(null);
  const [activePath, setActivePath] = React.useState(firstFilePath ?? '');
  const [draggingPath, setDraggingPath] = React.useState<string | null>(null);
  const [dragOverPath, setDragOverPath] = React.useState<string | null>(null);
  const [clipboardItem, setClipboardItem] = React.useState<FileTreeNode | null>(null);
  const [contents, setContents] = React.useState<Record<string, string>>(
    () => marketplaceFileContentsFromTree(initialNodes),
  );

  const activeNode = React.useMemo(
    () => treeState.flatNodes.find(node => node.path === activePath && node.type === 'file') ?? null,
    [activePath, treeState.flatNodes],
  );

  React.useEffect(() => {
    if (activeNode) return;
    const nextFile = treeState.flatNodes.find(node => node.type === 'file');
    setActivePath(nextFile?.path ?? '');
  }, [activeNode, treeState.flatNodes]);

  const handleNodeClick = React.useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    treeState.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file' && modifier === 'none') {
      setActivePath(node.path);
    }
  }, [treeState]);

  const handleNodeDoubleClick = React.useCallback((node: FileTreeNode) => {
    if (node.type === 'file') {
      setActivePath(node.path);
    } else {
      treeState.toggleNode(node.path);
    }
  }, [treeState]);

  const handleContextMenu = React.useCallback((node: FileTreeNode, event: React.MouseEvent) => {
    treeState.openContextMenu(event.clientX, event.clientY, node);
  }, [treeState]);

  const handleCreate = React.useCallback((name: string) => {
    if (!dialogState || (dialogState.type !== 'create-file' && dialogState.type !== 'create-folder')) return;
    const parentPath = dialogState.parentPath;
    const path = marketplaceJoinPath(parentPath, name);
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: dialogState.type === 'create-folder' ? 'directory' : 'file',
      extension: dialogState.type === 'create-file' ? name.split('.').pop() : undefined,
      children: dialogState.type === 'create-folder' ? [] : undefined,
      size: dialogState.type === 'create-file' ? 0 : undefined,
    };

    treeState.addNode(parentPath, node);
    if (node.type === 'file') {
      setContents(prev => ({ ...prev, [path]: '' }));
      setActivePath(path);
      treeState.selectNode(path);
    } else {
      treeState.expandNode(path);
    }
    setDialogState(null);
    onDirty();
  }, [dialogState, onDirty, treeState]);

  const handleRename = React.useCallback((name: string) => {
    if (!dialogState || dialogState.type !== 'rename') return;
    const { node } = dialogState;
    const parentPath = marketplaceParentPath(node.path);
    const nextPath = marketplaceJoinPath(parentPath, name);
    treeState.setNodes(marketplaceRenameNode(treeState.nodes, node.path, nextPath, name));
    setContents(prev => marketplaceRenameContentPaths(prev, node.path, nextPath));
    if (activePath === node.path || activePath.startsWith(`${node.path}/`)) {
      setActivePath(activePath.replace(node.path, nextPath));
    }
    setDialogState(null);
    onDirty();
  }, [activePath, dialogState, onDirty, treeState]);

  const handleDelete = React.useCallback(() => {
    if (!dialogState || dialogState.type !== 'delete') return;
    const { node } = dialogState;
    treeState.removeNode(node.path);
    setContents(prev => marketplaceDeleteContentPaths(prev, [node.path]));
    if (activePath === node.path || activePath.startsWith(`${node.path}/`)) {
      setActivePath('');
    }
    setDialogState(null);
    onDirty();
  }, [activePath, dialogState, onDirty, treeState]);

  const handleBatchDelete = React.useCallback(() => {
    const paths = Array.from(treeState.selectedIds);
    paths.forEach(path => treeState.removeNode(path));
    setContents(prev => marketplaceDeleteContentPaths(prev, paths));
    if (paths.some(path => activePath === path || activePath.startsWith(`${path}/`))) {
      setActivePath('');
    }
    treeState.clearSelection();
    setDialogState(null);
    onDirty();
  }, [activePath, onDirty, treeState]);

  const handleSaveFile = React.useCallback(async (content: string) => {
    if (!activeNode) return;
    setContents(prev => ({ ...prev, [activeNode.path]: content }));
    onDirty();
  }, [activeNode, onDirty]);

  const contextMenuItems = useFileTreeContextMenu({
    node: treeState.contextMenu?.node ?? null,
    enableMultiSelect: true,
    selectedCount: treeState.selectedIds.size,
    selectedIds: treeState.selectedIds,
    hasClipboard: Boolean(clipboardItem),
    features: {
      upload: true,
      createFile: true,
      createFolder: true,
      copy: true,
      copyPath: true,
      paste: true,
      rename: true,
      delete: true,
      refresh: true,
    },
    callbacks: {
      onUpload: treeState.closeContextMenu,
      onCreateFile: () => {
        const node = treeState.contextMenu?.node;
        setDialogState({ type: 'create-file', parentPath: node?.type === 'directory' ? node.path : marketplaceParentPath(node?.path ?? '') });
      },
      onCreateFolder: () => {
        const node = treeState.contextMenu?.node;
        setDialogState({ type: 'create-folder', parentPath: node?.type === 'directory' ? node.path : marketplaceParentPath(node?.path ?? '') });
      },
      onCopy: node => setClipboardItem(node),
      onCopyPath: path => void navigator.clipboard.writeText(path),
      onPaste: () => {
        if (!clipboardItem || !treeState.contextMenu) return;
        const target = treeState.contextMenu.node;
        const parentPath = target.type === 'directory' ? target.path : marketplaceParentPath(target.path);
        const pasted = marketplaceCloneNodeForParent(clipboardItem, parentPath, treeState.flatNodes);
        treeState.addNode(parentPath, pasted.node);
        setContents(prev => ({ ...prev, ...marketplaceRemapContentPaths(prev, clipboardItem.path, pasted.node.path) }));
        onDirty();
      },
      onRename: node => setDialogState({ type: 'rename', node }),
      onDelete: node => setDialogState({ type: 'delete', node }),
      onBatchDelete: () => {
        const node = treeState.contextMenu?.node;
        if (node) setDialogState({ type: 'batch-delete', node });
      },
      onRefresh: treeState.closeContextMenu,
      onClose: treeState.closeContextMenu,
    },
    t,
  });

  const headerActions = (
    <>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        title={t('marketplace.editor.fileManager.sidebar.refresh')}
        aria-label={t('marketplace.editor.fileManager.sidebar.refresh')}
      >
        <RefreshCw className="h-4 w-4" />
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        title={t('marketplace.editor.fileManager.sidebar.upload')}
        aria-label={t('marketplace.editor.fileManager.sidebar.upload')}
      >
        <Upload className="h-4 w-4" />
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            title={t('marketplace.editor.fileManager.actions.create.trigger')}
            aria-label={t('marketplace.editor.fileManager.actions.create.trigger')}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setDialogState({ type: 'create-file', parentPath: null })} className="text-xs">
            <Plus className="mr-2 h-4 w-4" />
            {t('marketplace.editor.fileManager.sidebar.createFile')}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setDialogState({ type: 'create-folder', parentPath: null })} className="text-xs">
            <FolderPlus className="mr-2 h-4 w-4" />
            {t('marketplace.editor.fileManager.sidebar.createFolder')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );

  return (
    <div className="flex h-full overflow-hidden border-x border-b bg-background">
      <div className="w-80">
        <MarketplaceSectionSidebarShell
          title={t('marketplace.editor.fileManager.skills.title')}
          icon={<Wand2 className="h-4 w-4" />}
          actions={headerActions}
          searchValue={treeState.searchQuery}
          onSearchChange={treeState.setSearchQuery}
          onSearchClear={treeState.clearSearch}
          searchPlaceholder={t('marketplace.editor.fileManager.search.placeholder')}
          body={(
            <FileTreePanel
              state={treeState}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={handleNodeDoubleClick}
              onContextMenu={handleContextMenu}
              onDragStart={node => setDraggingPath(node.path)}
              onDragEnd={() => {
                setDraggingPath(null);
                setDragOverPath(null);
              }}
              onDragOver={(node, event) => {
                event.preventDefault();
                if (node.type === 'directory') {
                  setDragOverPath(node.path);
                }
              }}
              onDragLeave={() => setDragOverPath(null)}
              onDrop={(node, event) => {
                event.preventDefault();
                setDragOverPath(null);
                setDraggingPath(null);
              }}
              onCreateFile={() => setDialogState({ type: 'create-file', parentPath: null })}
              onCreateFolder={() => setDialogState({ type: 'create-folder', parentPath: null })}
              onUpload={() => undefined}
              onRefresh={() => undefined}
              onBatchDelete={() => {
                const node = treeState.selectedNodes[0];
                if (node) setDialogState({ type: 'batch-delete', node });
              }}
              enableSearch={false}
              enableToolbar={false}
              enableMultiSelectBar
              enableDragDrop
              draggingPath={draggingPath}
              dragOverPath={dragOverPath}
              className="flex-1"
            />
          )}
        />

        <FileTreeContextMenu
          contextMenu={treeState.contextMenu}
          items={contextMenuItems}
          onClose={treeState.closeContextMenu}
        />
        </div>

      <div className="min-w-0 flex-1 overflow-hidden">
        {!activeNode ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t('marketplace.editor.fileManager.viewer.noFile')}
          </div>
        ) : (
          <FileEditor
            fileName={activeNode.name}
            filePath={activeNode.path}
            fileContent={contents[activeNode.path] ?? ''}
            onSave={handleSaveFile}
            onContentChange={(content) => {
              setContents(prev => ({ ...prev, [activeNode.path]: content }));
              onDirty();
            }}
            isLoading={false}
            isSaving={false}
          />
        )}
      </div>

      <FileCreateDialog
        open={dialogState?.type === 'create-file'}
        type="file"
        onClose={() => setDialogState(null)}
        onConfirm={handleCreate}
      />
      <FileCreateDialog
        open={dialogState?.type === 'create-folder'}
        type="folder"
        onClose={() => setDialogState(null)}
        onConfirm={handleCreate}
      />
      <FileRenameDialog
        open={dialogState?.type === 'rename'}
        currentName={dialogState?.type === 'rename' ? dialogState.node.name : ''}
        onClose={() => setDialogState(null)}
        onConfirm={handleRename}
      />
      <FileDeleteDialog
        open={dialogState?.type === 'delete'}
        fileName={dialogState?.type === 'delete' ? dialogState.node.name : ''}
        fileType={dialogState?.type === 'delete' ? dialogState.node.type : 'file'}
        onClose={() => setDialogState(null)}
        onConfirm={handleDelete}
      />
      <BatchDeleteDialog
        open={dialogState?.type === 'batch-delete'}
        files={treeState.selectedNodes.map(node => ({ name: node.name, path: node.path, type: node.type }))}
        onClose={() => setDialogState(null)}
        onConfirm={handleBatchDelete}
      />
    </div>
  );
};

type MarketplaceResourceFormat = 'markdown' | 'toml';
type MarketplaceMarkdownEditorTab = 'agents' | 'commands' | 'outputStyle' | 'policies';

interface MarketplaceMarkdownEditorViewerProps {
  tab: MarketplaceMarkdownEditorTab;
  icon: React.ComponentType<{ className?: string }>;
  items: MarketplaceEditorResourceItem[];
  format?: MarketplaceResourceFormat;
  commitVersion: number;
  discardVersion: number;
  onDirty: () => void;
}

const MarketplaceMarkdownEditorViewer: React.FC<MarketplaceMarkdownEditorViewerProps> = ({
  tab,
  icon: Icon,
  items,
  format = 'markdown',
  commitVersion,
  discardVersion,
  onDirty,
}) => {
  const { t } = useI18n();
  const [baseItems, setBaseItems] = React.useState(items);
  const [localItems, setLocalItems] = React.useState(items);
  const [selectedId, setSelectedId] = React.useState(items[0]?.id ?? null);
  const [search, setSearch] = React.useState('');
  const [renameItem, setRenameItem] = React.useState<MarketplaceEditorResourceItem | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [drafts, setDrafts] = React.useState<Record<string, string>>(
    () => Object.fromEntries(items.map(item => [item.id, item.content])),
  );
  const didMountRef = React.useRef(false);

  React.useEffect(() => {
    setBaseItems(items);
    setLocalItems(items);
    setDrafts(Object.fromEntries(items.map(item => [item.id, item.content])));
    setSelectedId(items[0]?.id ?? null);
  }, [items]);

  React.useEffect(() => {
    if (!didMountRef.current) return;
    setBaseItems(localItems.map(item => ({
      ...item,
      content: drafts[item.id] ?? item.content,
    })));
    setLocalItems(prev => prev.map(item => ({
      ...item,
      content: drafts[item.id] ?? item.content,
    })));
  }, [commitVersion]);

  React.useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    setLocalItems(baseItems);
    setDrafts(Object.fromEntries(baseItems.map(item => [item.id, item.content])));
    setSelectedId(prev => (prev && baseItems.some(item => item.id === prev) ? prev : baseItems[0]?.id ?? null));
  }, [discardVersion]);

  const dirtyItemIds = React.useMemo(() => {
    const baseById = new Map(baseItems.map(item => [item.id, item]));
    return new Set(localItems.filter(item => {
      const baseItem = baseById.get(item.id);
      if (!baseItem) return true;
      return baseItem.path !== item.path || baseItem.content !== (drafts[item.id] ?? item.content);
    }).map(item => item.id));
  }, [baseItems, drafts, localItems]);

  const filteredItems = React.useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return localItems;
    return localItems.filter(item => (
      getMarketplaceItemFileName(item).toLowerCase().includes(query) ||
      marketplaceEditorItemDescription(item, t).toLowerCase().includes(query) ||
      (drafts[item.id] ?? item.content).toLowerCase().includes(query)
    ));
  }, [drafts, localItems, search, t]);

  React.useEffect(() => {
    if (filteredItems.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filteredItems.some(item => item.id === selectedId)) {
      setSelectedId(filteredItems[0].id);
    }
  }, [filteredItems, selectedId]);

  const selectedItem = filteredItems.find(item => item.id === selectedId) ?? null;
  const currentIndex = selectedItem ? filteredItems.findIndex(item => item.id === selectedItem.id) : -1;
  const canNavigatePrevious = currentIndex > 0;
  const canNavigateNext = currentIndex >= 0 && currentIndex < filteredItems.length - 1;
  const selectedContent = selectedItem ? (drafts[selectedItem.id] ?? selectedItem.content) : '';
  const isSelectedDirty = selectedItem ? dirtyItemIds.has(selectedItem.id) : false;

  const handleCopy = async () => {
    if (!selectedItem) return;
    await navigator.clipboard.writeText(selectedContent);
  };

  const handleDownload = () => {
    if (!selectedItem) return;
    const blob = new Blob([selectedContent], { type: format === 'toml' ? 'application/toml' : 'text/markdown' });
    downloadBlob(blob, getMarketplaceItemFileName(selectedItem));
  };

  const handleCreate = (value: MarketplaceMarkdownCreateDialogValue) => {
    const id = `local-${Math.random().toString(36).slice(2, 10)}`;
    const nextItem: MarketplaceEditorResourceItem = {
      id,
      titleKey: 'marketplace.editor.documentViewer.create.defaultTitle',
      descriptionKey: 'marketplace.editor.documentViewer.create.defaultDescription',
      title: value.path,
      description: value.path,
      path: value.path,
      content: value.content,
      badge: format === 'toml' ? 'toml' : 'md',
    };
    setLocalItems(prev => [...prev, nextItem]);
    setDrafts(prev => ({ ...prev, [id]: value.content }));
    setSelectedId(id);
    setCreateDialogOpen(false);
    onDirty();
  };

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-80 flex-shrink-0">
        <MarketplaceSectionSidebarShell
          title={t(`marketplace.editor.documentViewer.${tab}.title`)}
          icon={<Icon className="h-4 w-4" />}
          actions={(
            <>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                title={t('marketplace.editor.documentViewer.actions.refresh')}
                aria-label={t('marketplace.editor.documentViewer.actions.refresh')}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                title={t('marketplace.editor.documentViewer.actions.add')}
                aria-label={t('marketplace.editor.documentViewer.actions.add')}
                onClick={() => setCreateDialogOpen(true)}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </>
          )}
          searchValue={search}
          onSearchChange={setSearch}
          onSearchClear={() => setSearch('')}
          searchPlaceholder={t('marketplace.editor.documentViewer.search.placeholder')}
          body={(
            <div className="h-full space-y-2 overflow-y-auto p-3">
              {filteredItems.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  {t('marketplace.editor.documentViewer.empty.filtered')}
                </div>
              ) : (
                filteredItems.map(item => {
                  const isActive = selectedItem?.id === item.id;
                  const content = drafts[item.id] ?? item.content;
                  const isItemDirty = dirtyItemIds.has(item.id);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      className={cn(
                        'w-full rounded-lg border px-3 py-3 text-left transition-colors',
                        isActive
                          ? 'border-primary/60 bg-primary/10 shadow-sm'
                          : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40',
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">
                            {isItemDirty ? (
                              <span
                                className="mr-1.5 inline-block h-2 w-2 rounded-full bg-amber-500 align-middle"
                                aria-label={t('marketplace.editor.documentViewer.unsavedFile')}
                              />
                            ) : null}
                            {getMarketplaceItemFileName(item)}
                          </div>
                          <div className="truncate text-xs text-muted-foreground">
                            {marketplaceEditorItemDescription(item, t)}
                          </div>
                        </div>
                        <div className="text-right text-[11px] text-muted-foreground">
                          {t('common.markdownFileViewer.units.bytes', { count: content.length })}
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          )}
        />
      </div>

      <main className="flex-1 bg-background">
        {selectedItem ? (
          <div className="flex h-full flex-col">
            <div className="sticky top-0 z-10 bg-background">
              <div className="border-b border-border bg-background p-4">
                <div className="flex items-center justify-between">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Icon className="h-5 w-5 shrink-0 text-primary" />
                      <h3 className="truncate font-semibold text-foreground">
                        {getMarketplaceItemFileName(selectedItem)}
                      </h3>
                    </div>
                    <p className="truncate text-sm text-muted-foreground">
                      {marketplaceEditorItemDescription(selectedItem, t)}
                    </p>
                    {isSelectedDirty ? (
                      <Badge variant="outline" className="border-amber-500/40 bg-amber-50 text-amber-700">
                        {t('marketplace.editor.documentViewer.unsavedFile')}
                      </Badge>
                    ) : null}
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedId(filteredItems[currentIndex - 1].id)}
                      disabled={!canNavigatePrevious}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedId(filteredItems[currentIndex + 1].id)}
                      disabled={!canNavigateNext}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
                      <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                      {t('marketplace.editor.documentViewer.actions.delete')}
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setRenameItem(selectedItem)}>
                          <Edit className="mr-2 h-3 w-3" />
                          {t('marketplace.editor.common.rename.action')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => void handleCopy()}>
                          <Copy className="mr-2 h-3 w-3" />
                          {t('marketplace.editor.documentViewer.actions.copy')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={handleDownload}>
                          <Download className="mr-2 h-3 w-3" />
                          {t('marketplace.editor.documentViewer.actions.download')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>

              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-hidden">
              {format === 'toml' ? (
                <div className="flex h-full flex-col">
                  <CodeTextEditor
                    fileName={selectedItem.path}
                    content={selectedContent}
                    originalContent={selectedItem.content}
                    onContentChange={(value) => {
                      setDrafts(prev => ({ ...prev, [selectedItem.id]: value }));
                      onDirty();
                    }}
                    onModifiedChange={() => undefined}
                  />
                  <div className="border-t border-border px-3 py-2 font-mono text-xs text-muted-foreground">
                    {selectedItem.path}
                  </div>
                </div>
              ) : (
                <MarkdownEditor
                  value={selectedContent}
                  onChange={(value) => {
                    setDrafts(prev => ({ ...prev, [selectedItem.id]: value }));
                    onDirty();
                  }}
                  placeholder={t('marketplace.editor.documentViewer.editor.placeholder')}
                  className="h-full min-h-0 rounded-none border-0"
                  textareaClassName="min-h-[calc(100vh-18rem)] font-mono text-sm"
                  statusMessage={(
                    <span className="font-mono text-xs text-muted-foreground">
                      {selectedItem.path}
                    </span>
                  )}
                />
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <Icon className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{t(`marketplace.editor.documentViewer.${tab}.empty`)}</p>
          </div>
        )}
      </main>
      <MarketplaceRenameDialog
        open={Boolean(renameItem)}
        initialPath={renameItem?.path ?? ''}
        onOpenChange={(open) => {
          if (!open) setRenameItem(null);
        }}
        onSubmit={(nextPath) => {
          if (!renameItem) return;
          setLocalItems(prev => prev.map(item => (
            item.id === renameItem.id ? { ...item, path: nextPath } : item
          )));
          setRenameItem(null);
          onDirty();
        }}
      />
      <MarketplaceMarkdownCreateDialog
        open={createDialogOpen}
        tab={tab}
        icon={Icon}
        format={format}
        onOpenChange={setCreateDialogOpen}
        onSubmit={handleCreate}
      />
    </div>
  );
};

interface MarketplaceMarkdownCreateDialogValue {
  path: string;
  content: string;
}

interface MarketplaceMarkdownCreateDialogProps {
  open: boolean;
  tab: MarketplaceMarkdownEditorTab;
  icon: React.ComponentType<{ className?: string }>;
  format: MarketplaceResourceFormat;
  onOpenChange: (open: boolean) => void;
  onSubmit: (value: MarketplaceMarkdownCreateDialogValue) => void;
}

const marketplaceDefaultResourcePath = (tab: MarketplaceMarkdownEditorTab, format: MarketplaceResourceFormat): string => {
  switch (tab) {
    case 'agents':
      return 'agents/new-subagent.md';
    case 'commands':
      return format === 'toml' ? 'commands/new-command.toml' : 'commands/new-command.md';
    case 'outputStyle':
      return 'output-styles/new-output-style.md';
    case 'policies':
      return 'policies/new-policy.toml';
  }
};

const marketplaceResourceExtension = (format: MarketplaceResourceFormat): string => (
  format === 'toml' ? '.toml' : '.md'
);

const MarketplaceMarkdownCreateDialog: React.FC<MarketplaceMarkdownCreateDialogProps> = ({
  open,
  tab,
  icon: Icon,
  format,
  onOpenChange,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [path, setPath] = React.useState(marketplaceDefaultResourcePath(tab, format));
  const [content, setContent] = React.useState('');
  const [errors, setErrors] = React.useState<{ path?: string; content?: string }>({});

  React.useEffect(() => {
    if (!open) return;
    setPath(marketplaceDefaultResourcePath(tab, format));
    setContent('');
    setErrors({});
  }, [format, open, tab]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const nextErrors: { path?: string; content?: string } = {};
    if (!path.trim()) {
      nextErrors.path = t('marketplace.editor.documentViewer.create.validation.pathRequired');
    }
    if (!content.trim()) {
      nextErrors.content = t('marketplace.editor.documentViewer.create.validation.contentRequired');
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    onSubmit({
      path: path.trim().endsWith(marketplaceResourceExtension(format))
        ? path.trim()
        : `${path.trim()}${marketplaceResourceExtension(format)}`,
      content,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" />
            {t('marketplace.editor.documentViewer.create.title', {
              resource: t(`marketplace.editor.documentViewer.${tab}.title`),
            })}
          </DialogTitle>
          <DialogDescription>
            {t('marketplace.editor.documentViewer.create.description', {
              format: t(`marketplace.editor.documentViewer.formats.${format}`),
            })}
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={handleSubmit}>
          <div className="flex flex-1 flex-col overflow-hidden px-6 pb-6 pt-4">
            <div className="mb-4 flex-shrink-0 space-y-2">
              <Label htmlFor={`marketplace-${tab}-create-path`}>
                {t('marketplace.editor.documentViewer.create.fields.path.label')}
              </Label>
              <Input
                id={`marketplace-${tab}-create-path`}
                value={path}
                onChange={event => setPath(event.target.value)}
                placeholder={t('marketplace.editor.documentViewer.create.fields.path.placeholder')}
                className="font-mono text-sm"
              />
              {errors.path ? <p className="text-xs text-destructive">{errors.path}</p> : null}
              <p className="text-xs text-muted-foreground">
                {t('marketplace.editor.documentViewer.create.fields.path.helper', {
                  extension: marketplaceResourceExtension(format),
                })}
              </p>
            </div>

            <div className="flex min-h-0 flex-1 flex-col">
              <Label className="mb-2">
                {t('marketplace.editor.documentViewer.create.fields.content.label')}
              </Label>
              <div className="min-h-0 flex-1 overflow-hidden rounded-lg border">
                {format === 'toml' ? (
                  <CodeTextEditor
                    fileName={path}
                    content={content}
                    originalContent=""
                    onContentChange={setContent}
                    onModifiedChange={() => undefined}
                  />
                ) : (
                  <MarkdownEditor
                    value={content}
                    onChange={value => setContent(value ?? '')}
                    placeholder={t('marketplace.editor.documentViewer.editor.placeholder')}
                    className="h-full"
                    textareaClassName="min-h-[calc(85vh-18rem)] font-mono text-sm"
                  />
                )}
              </div>
              {errors.content ? <p className="mt-2 text-xs text-destructive">{errors.content}</p> : null}
            </div>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('marketplace.common.actions.cancel')}
            </Button>
            <Button type="submit">
              {t('marketplace.editor.documentViewer.create.actions.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

interface MarketplaceRenameDialogProps {
  open: boolean;
  initialPath: string;
  onOpenChange: (open: boolean) => void;
  onSubmit: (path: string) => void;
}

const MarketplaceRenameDialog: React.FC<MarketplaceRenameDialogProps> = ({
  open,
  initialPath,
  onOpenChange,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [path, setPath] = React.useState(initialPath);

  React.useEffect(() => {
    if (open) {
      setPath(initialPath);
    }
  }, [initialPath, open]);

  const trimmedPath = path.trim();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('marketplace.editor.common.rename.title')}</DialogTitle>
          <DialogDescription>
            {t('marketplace.editor.common.rename.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            {t('marketplace.editor.common.rename.pathLabel')}
          </label>
          <Input
            value={path}
            onChange={event => setPath(event.target.value)}
            placeholder={t('marketplace.editor.common.rename.pathPlaceholder')}
            className="font-mono text-sm"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('marketplace.common.actions.cancel')}
          </Button>
          <Button disabled={!trimmedPath} onClick={() => onSubmit(trimmedPath)}>
            {t('marketplace.common.actions.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

interface MarketplacePackageFileManagerProps {
  packageRoot: string;
  initialNodes: FileTreeNode[];
  onDirty: () => void;
  onPackageFilesChange: (files: MarketplacePackageFile[]) => void;
}

type MarketplaceFileDialogState =
  | { type: 'create-file' | 'create-folder'; parentPath: string | null }
  | { type: 'rename' | 'delete' | 'batch-delete'; node: FileTreeNode }
  | null;

const MarketplacePackageFileManager: React.FC<MarketplacePackageFileManagerProps> = ({
  packageRoot,
  initialNodes,
  onDirty,
  onPackageFilesChange,
}) => {
  const { t } = useI18n();
  const packageRootPath = `/${packageRoot}`;
  const initialSelectedPath = React.useMemo(() => marketplaceFindFirstFilePath(initialNodes), [initialNodes]);
  const initialExpandedIds = React.useMemo(() => marketplaceDirectoryPaths(initialNodes), [initialNodes]);
  const treeState = useFileTreeState({
    initialNodes,
    initialExpandedIds,
    initialSelectedId: initialSelectedPath,
    enableMultiSelect: true,
  });
  const hasPackageRootNode = React.useMemo(
    () => treeState.flatNodes.some(node => node.path === packageRootPath && node.type === 'directory'),
    [packageRootPath, treeState.flatNodes],
  );
  const packageRootParentPath = hasPackageRootNode ? packageRootPath : null;
  const [dialogState, setDialogState] = React.useState<MarketplaceFileDialogState>(null);
  const [activePath, setActivePath] = React.useState(initialSelectedPath ?? '');
  const [draggingPath, setDraggingPath] = React.useState<string | null>(null);
  const [dragOverPath, setDragOverPath] = React.useState<string | null>(null);
  const [clipboardItem, setClipboardItem] = React.useState<FileTreeNode | null>(null);
  const [contents, setContents] = React.useState<Record<string, string>>(
    () => marketplaceFileContentsFromTree(initialNodes),
  );

  React.useEffect(() => {
    onPackageFilesChange(marketplacePackageFilesFromTree(treeState.nodes, packageRootPath, contents));
  }, [contents, onPackageFilesChange, packageRootPath, treeState.nodes]);

  const activeNode = React.useMemo(
    () => treeState.flatNodes.find(node => node.path === activePath && node.type === 'file') ?? null,
    [activePath, treeState.flatNodes],
  );

  React.useEffect(() => {
    if (activeNode) return;
    const nextFile = treeState.flatNodes.find(node => node.type === 'file');
    setActivePath(nextFile?.path ?? '');
  }, [activeNode, treeState.flatNodes]);

  const handleNodeClick = React.useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    treeState.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file' && modifier === 'none') {
      setActivePath(node.path);
    }
  }, [treeState]);

  const handleNodeDoubleClick = React.useCallback((node: FileTreeNode) => {
    if (node.type === 'file') {
      setActivePath(node.path);
    } else {
      treeState.toggleNode(node.path);
    }
  }, [treeState]);

  const handleContextMenu = React.useCallback((node: FileTreeNode, event: React.MouseEvent) => {
    treeState.openContextMenu(event.clientX, event.clientY, node);
  }, [treeState]);

  const handleCreate = React.useCallback((name: string) => {
    if (!dialogState || (dialogState.type !== 'create-file' && dialogState.type !== 'create-folder')) return;
    const parentPath = dialogState.parentPath ?? packageRootParentPath;
    const fileParentPath = parentPath ?? packageRootPath;
    const path = marketplaceJoinPath(fileParentPath, name);
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: dialogState.type === 'create-folder' ? 'directory' : 'file',
      extension: dialogState.type === 'create-file' ? name.split('.').pop() : undefined,
      children: dialogState.type === 'create-folder' ? [] : undefined,
      size: dialogState.type === 'create-file' ? 0 : undefined,
    };

    treeState.addNode(parentPath, node);
    if (node.type === 'file') {
      setContents(prev => ({ ...prev, [path]: '' }));
      setActivePath(path);
      treeState.selectNode(path);
    } else {
      treeState.expandNode(path);
    }
    setDialogState(null);
    onDirty();
  }, [dialogState, onDirty, packageRootParentPath, packageRootPath, treeState]);

  const handleRename = React.useCallback((name: string) => {
    if (!dialogState || dialogState.type !== 'rename') return;
    const { node } = dialogState;
    if (node.path === packageRootPath) {
      setDialogState(null);
      return;
    }
    const parentPath = marketplaceParentPath(node.path);
    const nextPath = marketplaceJoinPath(parentPath, name);
    const renamedNodes = marketplaceRenameNode(treeState.nodes, node.path, nextPath, name);
    treeState.setNodes(renamedNodes);
    setContents(prev => marketplaceRenameContentPaths(prev, node.path, nextPath));
    if (activePath === node.path || activePath.startsWith(`${node.path}/`)) {
      setActivePath(activePath.replace(node.path, nextPath));
    }
    setDialogState(null);
    onDirty();
  }, [activePath, dialogState, onDirty, packageRootPath, treeState]);

  const handleDelete = React.useCallback(() => {
    if (!dialogState || dialogState.type !== 'delete') return;
    const { node } = dialogState;
    if (node.path === packageRootPath) {
      setDialogState(null);
      return;
    }
    treeState.removeNode(node.path);
    setContents(prev => marketplaceDeleteContentPaths(prev, [node.path]));
    if (activePath === node.path || activePath.startsWith(`${node.path}/`)) {
      setActivePath('');
    }
    setDialogState(null);
    onDirty();
  }, [activePath, dialogState, onDirty, packageRootPath, treeState]);

  const handleBatchDelete = React.useCallback(() => {
    const paths = Array.from(treeState.selectedIds).filter(path => path !== packageRootPath);
    if (!paths.length) {
      setDialogState(null);
      return;
    }
    paths.forEach(path => treeState.removeNode(path));
    setContents(prev => marketplaceDeleteContentPaths(prev, paths));
    if (paths.some(path => activePath === path || activePath.startsWith(`${path}/`))) {
      setActivePath('');
    }
    treeState.clearSelection();
    setDialogState(null);
    onDirty();
  }, [activePath, onDirty, packageRootPath, treeState]);

  const handleSaveFile = React.useCallback(async (content: string) => {
    if (!activeNode) return;
    if (isMarketplaceBinaryFile(activeNode)) return;
    setContents(prev => ({ ...prev, [activeNode.path]: content }));
    onDirty();
  }, [activeNode, onDirty]);

  const handleUploadBinaryAsset = React.useCallback(() => {
    const assetsPath = `${packageRootPath}/assets`;
    const uploadPath = `${assetsPath}/uploaded-image.png`;
    const uploadNode: FileTreeNode = {
      id: uploadPath,
      name: 'uploaded-image.png',
      path: uploadPath,
      type: 'file',
      extension: 'png',
      scope: packageRoot.includes('/extensions/') ? 'extension' : 'plugin',
      size: 68,
      metadata: {
        binary: true,
        mimeType: 'image/png',
        previewDataUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
      },
    };
    const hasAssetsDirectory = treeState.flatNodes.some(node => node.path === assetsPath && node.type === 'directory');
    if (!hasAssetsDirectory) {
      treeState.addNode(packageRootParentPath, {
        id: assetsPath,
        name: 'assets',
        path: assetsPath,
        type: 'directory',
        scope: packageRoot.includes('/extensions/') ? 'extension' : 'plugin',
        children: [],
      });
    }
    if (!treeState.flatNodes.some(node => node.path === uploadPath)) {
      treeState.addNode(assetsPath, uploadNode);
    }
    treeState.expandNode(assetsPath);
    treeState.selectNode(uploadPath);
    setActivePath(uploadPath);
    onDirty();
  }, [onDirty, packageRoot, packageRootParentPath, packageRootPath, treeState]);

  const handleDownloadActiveFile = React.useCallback(() => {
    if (!activeNode) return;
    const binaryLabel = t('marketplace.editor.fileManager.viewer.binaryDownloadContent', { name: activeNode.name });
    const content = isMarketplaceBinaryFile(activeNode) ? binaryLabel : (contents[activeNode.path] ?? '');
    const blob = new Blob([content], { type: getStringField(activeNode.metadata?.mimeType, 'application/octet-stream') });
    downloadBlob(blob, activeNode.name);
  }, [activeNode, contents, t]);

  const contextMenuItems = useFileTreeContextMenu({
    node: treeState.contextMenu?.node ?? null,
    enableMultiSelect: true,
    selectedCount: treeState.selectedIds.size,
    selectedIds: treeState.selectedIds,
    hasClipboard: Boolean(clipboardItem),
    features: {
      upload: true,
      createFile: true,
      createFolder: true,
      copy: true,
      copyPath: true,
      paste: true,
      rename: true,
      delete: true,
      refresh: true,
    },
    callbacks: {
      onUpload: () => {
        treeState.closeContextMenu();
        handleUploadBinaryAsset();
      },
      onCreateFile: () => {
        const node = treeState.contextMenu?.node;
        setDialogState({ type: 'create-file', parentPath: node?.type === 'directory' ? node.path : marketplaceParentPath(node?.path ?? '') ?? packageRootParentPath });
      },
      onCreateFolder: () => {
        const node = treeState.contextMenu?.node;
        setDialogState({ type: 'create-folder', parentPath: node?.type === 'directory' ? node.path : marketplaceParentPath(node?.path ?? '') ?? packageRootParentPath });
      },
      onCopy: node => setClipboardItem(node),
      onCopyPath: path => void navigator.clipboard.writeText(path),
      onPaste: () => {
        if (!clipboardItem || !treeState.contextMenu) return;
        const target = treeState.contextMenu.node;
        const parentPath = target.type === 'directory' ? target.path : marketplaceParentPath(target.path);
        const pasted = marketplaceCloneNodeForParent(clipboardItem, parentPath, treeState.flatNodes);
        treeState.addNode(parentPath, pasted.node);
        setContents(prev => ({ ...prev, ...marketplaceRemapContentPaths(prev, clipboardItem.path, pasted.node.path) }));
        onDirty();
      },
      onRename: node => {
        if (node.path !== packageRootPath) setDialogState({ type: 'rename', node });
      },
      onDelete: node => {
        if (node.path !== packageRootPath) setDialogState({ type: 'delete', node });
      },
      onBatchDelete: () => {
        const node = treeState.contextMenu?.node;
        if (node) setDialogState({ type: 'batch-delete', node });
      },
      onRefresh: treeState.closeContextMenu,
      onClose: treeState.closeContextMenu,
    },
    t,
  });

  const headerActions = (
    <>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        title={t('marketplace.editor.fileManager.sidebar.refresh')}
        aria-label={t('marketplace.editor.fileManager.sidebar.refresh')}
      >
        <RefreshCw className="h-4 w-4" />
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        title={t('marketplace.editor.fileManager.sidebar.upload')}
        aria-label={t('marketplace.editor.fileManager.sidebar.upload')}
        onClick={handleUploadBinaryAsset}
      >
        <Upload className="h-4 w-4" />
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            title={t('marketplace.editor.fileManager.actions.create.trigger')}
            aria-label={t('marketplace.editor.fileManager.actions.create.trigger')}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setDialogState({ type: 'create-file', parentPath: packageRootParentPath })} className="text-xs">
            <Plus className="mr-2 h-4 w-4" />
            {t('marketplace.editor.fileManager.sidebar.createFile')}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setDialogState({ type: 'create-folder', parentPath: packageRootParentPath })} className="text-xs">
            <FolderPlus className="mr-2 h-4 w-4" />
            {t('marketplace.editor.fileManager.sidebar.createFolder')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );

  return (
    <div className="flex h-full overflow-hidden border-x border-b bg-background">
      <div className="w-80">
        <MarketplaceSectionSidebarShell
          title={t('marketplace.editor.fileManager.packageFiles.title')}
          icon={<FileArchive className="h-4 w-4" />}
          actions={headerActions}
          searchValue={treeState.searchQuery}
          onSearchChange={treeState.setSearchQuery}
          onSearchClear={treeState.clearSearch}
          searchPlaceholder={t('marketplace.editor.fileManager.search.placeholder')}
          body={(
            <div className="flex h-full min-h-0 flex-col">
              <div className="border-b border-border bg-muted/20 px-3 py-2">
                <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  {t('marketplace.editor.fileManager.packageFiles.rootLabel')}
                </div>
                <div className="mt-1 truncate font-mono text-xs text-foreground" title={packageRoot}>
                  {packageRoot}
                </div>
              </div>
              <FileTreePanel
                state={treeState}
                onNodeClick={handleNodeClick}
                onNodeDoubleClick={handleNodeDoubleClick}
                onContextMenu={handleContextMenu}
                onDragStart={node => setDraggingPath(node.path)}
                onDragEnd={() => {
                  setDraggingPath(null);
                  setDragOverPath(null);
                }}
                onDragOver={(node, event) => {
                  event.preventDefault();
                  if (node.type === 'directory') {
                    setDragOverPath(node.path);
                  }
                }}
                onDragLeave={() => setDragOverPath(null)}
                onDrop={(node, event) => {
                  event.preventDefault();
                  setDragOverPath(null);
                  setDraggingPath(null);
                }}
                onCreateFile={() => setDialogState({ type: 'create-file', parentPath: packageRootParentPath })}
                onCreateFolder={() => setDialogState({ type: 'create-folder', parentPath: packageRootParentPath })}
                onUpload={handleUploadBinaryAsset}
                onRefresh={() => undefined}
                onBatchDelete={() => {
                  const node = treeState.selectedNodes.find(selectedNode => selectedNode.path !== packageRootPath);
                  if (node) setDialogState({ type: 'batch-delete', node });
                }}
                enableSearch={false}
                enableToolbar={false}
                enableMultiSelectBar
                enableDragDrop
                draggingPath={draggingPath}
                dragOverPath={dragOverPath}
                className="flex-1"
              />
            </div>
          )}
        />

        <FileTreeContextMenu
          contextMenu={treeState.contextMenu}
          items={contextMenuItems}
          onClose={treeState.closeContextMenu}
        />
      </div>

      <div className="min-w-0 flex-1 overflow-hidden">
        {!activeNode ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t('marketplace.editor.fileManager.viewer.noFile')}
          </div>
        ) : isMarketplaceBinaryFile(activeNode) ? (
          <MarketplaceBinaryFilePreview
            node={activeNode}
            canPreview={isMarketplacePreviewableBinaryFile(activeNode)}
            onDownload={handleDownloadActiveFile}
            onDelete={() => setDialogState({ type: 'delete', node: activeNode })}
          />
        ) : (
          <FileEditor
            fileName={activeNode.name}
            filePath={activeNode.path}
            fileContent={contents[activeNode.path] ?? ''}
            onSave={handleSaveFile}
            onContentChange={(content) => setContents(prev => ({ ...prev, [activeNode.path]: content }))}
            isLoading={false}
            isSaving={false}
          />
        )}
      </div>

      <FileCreateDialog
        open={dialogState?.type === 'create-file'}
        type="file"
        onClose={() => setDialogState(null)}
        onConfirm={handleCreate}
      />
      <FileCreateDialog
        open={dialogState?.type === 'create-folder'}
        type="folder"
        onClose={() => setDialogState(null)}
        onConfirm={handleCreate}
      />
      <FileRenameDialog
        open={dialogState?.type === 'rename'}
        currentName={dialogState?.type === 'rename' ? dialogState.node.name : ''}
        onClose={() => setDialogState(null)}
        onConfirm={handleRename}
      />
      <FileDeleteDialog
        open={dialogState?.type === 'delete'}
        fileName={dialogState?.type === 'delete' ? dialogState.node.name : ''}
        fileType={dialogState?.type === 'delete' ? dialogState.node.type : 'file'}
        onClose={() => setDialogState(null)}
        onConfirm={handleDelete}
      />
      <BatchDeleteDialog
        open={dialogState?.type === 'batch-delete'}
        files={treeState.selectedNodes.map(node => ({ name: node.name, path: node.path, type: node.type }))}
        onClose={() => setDialogState(null)}
        onConfirm={handleBatchDelete}
      />
    </div>
  );
};

interface MarketplaceBinaryFilePreviewProps {
  node: FileTreeNode;
  canPreview: boolean;
  onDownload: () => void;
  onDelete: () => void;
}

const MarketplaceBinaryFilePreview: React.FC<MarketplaceBinaryFilePreviewProps> = ({
  node,
  canPreview,
  onDownload,
  onDelete,
}) => {
  const { t } = useI18n();
  const previewDataUrl = typeof node.metadata?.previewDataUrl === 'string' ? node.metadata.previewDataUrl : '';
  const mimeType = getStringField(node.metadata?.mimeType, t('marketplace.common.unknown'));

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-foreground">{node.name}</div>
          <div className="mt-0.5 truncate font-mono text-xs text-muted-foreground">{node.path}</div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8 px-2 text-xs" onClick={onDownload}>
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.editor.fileManager.viewer.download')}
          </Button>
          <Button variant="outline" size="sm" className="h-8 px-2 text-xs text-destructive" onClick={onDelete}>
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.editor.fileManager.viewer.delete')}
          </Button>
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-xl space-y-4 rounded-md border border-border bg-muted/20 p-5 text-center">
          {canPreview ? (
            <div className="mx-auto flex aspect-video max-h-80 items-center justify-center overflow-hidden rounded-md border border-border bg-background">
              <img
                src={previewDataUrl}
                alt={t('marketplace.editor.fileManager.viewer.previewAlt', { name: node.name })}
                className="max-h-full max-w-full object-contain"
              />
            </div>
          ) : (
            <div className="mx-auto flex h-40 items-center justify-center rounded-md border border-dashed border-border bg-background px-4 text-sm text-muted-foreground">
              {t('marketplace.editor.fileManager.viewer.previewUnavailable')}
            </div>
          )}
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fileManager.viewer.binaryTitle')}
            </div>
            <p className="text-sm text-muted-foreground">
              {t('marketplace.editor.fileManager.viewer.binaryDescription', { mimeType })}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

interface MarketplaceEditorFeatureSectionProps {
  provider: MarketplaceProvider;
  tab: Exclude<MarketplaceEditorTab, 'basic' | 'agentsMd'>;
  icon: React.ComponentType<{ className?: string }>;
  items: MarketplaceEditorResourceItem[];
  onDirty?: () => void;
  onItemsChange?: (items: MarketplaceEditorResourceItem[]) => void;
}

const MarketplaceEditorFeatureSection: React.FC<MarketplaceEditorFeatureSectionProps> = ({ provider, tab, icon: Icon, items: initialItems, onDirty, onItemsChange }) => {
  const { t } = useI18n();
  const [items, setItems] = React.useState(initialItems);

  React.useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);
  const [mcpDialogOpen, setMcpDialogOpen] = React.useState(false);
  const [hookDialogOpen, setHookDialogOpen] = React.useState(false);
  const emptyMcpServer: MarketplaceMcpServerDialogValue = {
    name: '',
    description: '',
    transport: 'stdio',
    command: '',
    args: [],
    url: '',
    env: [],
    headers: [],
  };
  const emptyHook: MarketplaceHookDialogValue = {
    name: '',
    event: provider === 'gemini' ? 'BeforeTool' : 'PreToolUse',
    matchers: [
      {
        matcher: '*',
        sequential: provider === 'gemini',
        hooks: [{ type: 'command', command: '', timeout: provider === 'gemini' ? 60000 : 120 }],
      },
    ],
  };
  const handleAddClick = () => {
    if (tab === 'mcp') {
      setMcpDialogOpen(true);
      return;
    }
    if (tab === 'hooks') {
      setHookDialogOpen(true);
    }
  };
  const addMcpServer = (value: MarketplaceMcpServerDialogValue) => {
    const id = `local-${Math.random().toString(36).slice(2, 10)}`;
    const commandText = [value.command, ...value.args].filter(Boolean).join(' ');
    const nextItems = [
      ...items,
      {
        id,
        titleKey: 'marketplace.editor.mcp.dialog.create.defaultTitle',
        descriptionKey: 'marketplace.editor.mcp.dialog.create.defaultDescription',
        title: value.name,
        description: value.description,
        path: `mcp/${value.name || id}.json`,
        content: marketplaceMcpServerContentFromValue(value),
        badge: value.transport,
        code: commandText,
        meta: [
          { labelKey: 'marketplace.editor.featureMeta.labels.transport', value: value.transport },
          ...(value.env[0]?.key ? [{ labelKey: 'marketplace.editor.featureMeta.labels.env', value: value.env[0].key }] : []),
        ],
      },
    ];
    setItems(nextItems);
    onItemsChange?.(nextItems);
    setMcpDialogOpen(false);
    onDirty?.();
  };
  const addHook = (value: MarketplaceHookDialogValue) => {
    const id = `local-${Math.random().toString(36).slice(2, 10)}`;
    const firstMatcher = value.matchers[0];
    const firstAction = firstMatcher?.hooks[0];
    setItems(prev => [
      ...prev,
      {
        id,
        titleKey: 'marketplace.editor.hooks.dialog.create.defaultTitle',
        descriptionKey: 'marketplace.editor.hooks.dialog.create.defaultDescription',
        title: value.name || value.event,
        description: value.event,
        path: `hooks/${value.name || id}.json`,
        content: JSON.stringify(value, null, 2),
        badge: value.event,
        code: firstAction?.command ?? '',
        meta: [
          { labelKey: 'marketplace.editor.featureMeta.labels.type', value: firstAction?.type ?? 'command' },
          { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: firstMatcher?.matcher ?? '*' },
          { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: formatMarketplaceHookTimeout(provider, firstAction?.timeout) },
          ...(firstMatcher?.sequential ? [{ labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: t('marketplace.common.labels.enabled') }] : []),
        ],
      },
    ]);
    setHookDialogOpen(false);
    onDirty?.();
  };

  return (
    <>
      <SettingsWorkflowShell
        title={t(`marketplace.editor.tabs.${tab}`)}
        icon={Icon}
        headerActions={(
          <SettingsWorkflowActionButton onClick={handleAddClick}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            {t('marketplace.editor.featureSections.actions.add')}
          </SettingsWorkflowActionButton>
        )}
        summary={<SettingsWorkflowCountBadge label={t('marketplace.editor.featureSections.count', { count: items.length })} />}
        singleHeader
        hasItems={items.length > 0}
        emptyIcon={<Icon className="h-6 w-6 text-muted-foreground" />}
        emptyTitle={t(`marketplace.editor.featureSections.${tab}.emptyTitle`)}
        emptyDescription={t(`marketplace.editor.featureSections.${tab}.emptyDescription`)}
        emptyActions={(
          <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAddClick}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            {t('marketplace.editor.featureSections.actions.add')}
          </Button>
        )}
        contentClassName="space-y-4 p-4"
      >
        {items.map(item => {
          if (tab === 'mcp') {
            return (
              <MarketplaceMcpServerCard
                key={item.id}
                item={item}
                onDirty={onDirty}
                onChange={(nextItem) => {
                  const nextItems = items.map(current => (current.id === nextItem.id ? nextItem : current));
                  setItems(nextItems);
                  onItemsChange?.(nextItems);
                }}
              />
            );
          }
          if (tab === 'hooks') {
            return <MarketplaceHookCard key={item.id} provider={provider} item={item} onDirty={onDirty} />;
          }
          return <MarketplaceEditorResourceItemCard key={item.id} item={item} icon={Icon} />;
        })}
      </SettingsWorkflowShell>
      {tab === 'mcp' ? (
        <MarketplaceMcpServerDialog
          open={mcpDialogOpen}
          mode="create"
          value={emptyMcpServer}
          onOpenChange={setMcpDialogOpen}
          onSave={addMcpServer}
        />
      ) : null}
      {tab === 'hooks' ? (
        <MarketplaceHookDialog
          open={hookDialogOpen}
          mode="create"
          value={emptyHook}
          provider={provider}
          onOpenChange={setHookDialogOpen}
          onSave={addHook}
        />
      ) : null}
    </>
  );
};

interface MarketplaceMcpServerCardProps {
  item: MarketplaceEditorResourceItem;
  onDirty?: () => void;
  onChange: (item: MarketplaceEditorResourceItem) => void;
}

const MarketplaceMcpServerCard: React.FC<MarketplaceMcpServerCardProps> = ({ item, onDirty, onChange }) => {
  const { t } = useI18n();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [server, setServer] = React.useState(() => marketplaceMcpServerValueFromItem(item, t));
  const envKeys = server.env.map(row => row.key.trim()).filter(Boolean).join(', ');

  return (
    <>
      <div className="rounded-lg border border-border bg-background p-4 transition-shadow hover:shadow-sm">
        <div className="mb-3 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Database className="h-5 w-5 text-primary" />
            </div>
            <div>
              <div className="mb-1 flex items-center gap-2">
                <h3 className="font-semibold text-foreground">{server.name}</h3>
                <Badge variant="outline" className="border-blue-200 bg-blue-50 text-xs text-blue-700">
                  {server.transport.toUpperCase()}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">{server.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" type="button" onClick={() => setDialogOpen(true)}>
              <Edit className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" type="button">
              <Trash2 className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" type="button">
              <Copy className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t('marketplace.editor.mcp.card.sections.command')}
            </h4>
            <div className="rounded-md bg-muted/50 p-3">
              <code className="break-all font-mono text-sm text-foreground">{server.command}</code>
            </div>
          </div>

          {server.args.length > 0 ? (
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t('marketplace.editor.mcp.card.sections.arguments')}
              </h4>
              <div className="rounded-md bg-muted/50 p-3">
                <code className="break-all font-mono text-sm text-foreground">{server.args.join(' ')}</code>
              </div>
            </div>
          ) : null}

          {envKeys ? (
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t('marketplace.editor.mcp.card.sections.environment')}
              </h4>
              <div className="rounded-md bg-muted/50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <code className="font-mono text-sm text-foreground">{envKeys}</code>
                  <span className="text-xs text-muted-foreground">••••••••</span>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <MarketplaceMcpServerDialog
        open={dialogOpen}
        value={server}
        onOpenChange={setDialogOpen}
        onSave={(value) => {
          setServer(value);
          onChange(marketplaceMcpResourceItemFromValue(item, value));
          setDialogOpen(false);
          onDirty?.();
        }}
      />
    </>
  );
};

interface MarketplaceHookCardProps {
  provider: MarketplaceProvider;
  item: MarketplaceEditorResourceItem;
  onDirty?: () => void;
}

const MarketplaceHookCard: React.FC<MarketplaceHookCardProps> = ({ provider, item, onDirty }) => {
  const { t } = useI18n();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const parsedTimeout = Number(item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.timeout')?.value.replace(/[^0-9]/g, '') ?? (provider === 'gemini' ? 60000 : 120));
  const [hook, setHook] = React.useState({
    name: marketplaceEditorItemTitle(item, t),
    event: item.badge ?? (provider === 'gemini' ? 'BeforeTool' : 'PreToolUse'),
    matchers: [
      {
        matcher: item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.matcher')?.value ?? '*',
        sequential: provider === 'gemini',
        hooks: [{
          type: (item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.type')?.value ?? 'command') as HookMatcher['hooks'][number]['type'],
          command: item.code ?? '',
          timeout: parsedTimeout,
        }],
      },
    ] satisfies HookMatcher[],
  });
  const primaryMatcher = hook.matchers[0];
  const primaryAction = primaryMatcher?.hooks[0];
  const timeoutLabel = formatMarketplaceHookTimeout(provider, primaryAction?.timeout);

  return (
    <>
      <div className="relative rounded-lg border border-border bg-background p-6">
        <div className="flex items-start">
          <div className="min-w-0 flex-1">
            <div className="mb-3">
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold text-foreground">{hook.name}</h3>
                <Badge variant="outline" className="text-xs">
                  {hook.event}
                </Badge>
              </div>
            </div>

            <div className="mb-4">
              <div className="mb-3 flex items-center gap-2">
                <Terminal className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium text-muted-foreground">
                  {t('marketplace.editor.hooks.card.matchersTitle')}
                </span>
              </div>
              <div className="rounded-lg bg-muted/50 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {t('marketplace.editor.hooks.card.matcherLabel')}
                    </span>
                    <code className="rounded bg-muted px-1 text-xs">{primaryMatcher?.matcher ?? '*'}</code>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {t('marketplace.editor.hooks.card.actionsCount', { count: 1 })}
                  </span>
                </div>
                <div className="mb-1 rounded bg-muted px-2 py-1 text-xs">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge variant="outline" className="px-1 py-0 text-xs">
                      {t(`marketplace.editor.hooks.dialog.executions.types.${primaryAction?.type ?? 'command'}.label`)}
                    </Badge>
                    {primaryAction?.timeout ? <span className="text-muted-foreground">{timeoutLabel}</span> : null}
                    {primaryMatcher?.sequential ? (
                      <span className="text-muted-foreground">
                        {t('marketplace.editor.hooks.card.sequential')}
                      </span>
                    ) : null}
                  </div>
                  <p className="truncate font-mono text-muted-foreground">
                    {primaryAction?.command ?? ''}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex gap-4 rounded bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <span>{t('marketplace.editor.hooks.card.summary.matchers', { count: 1 })}</span>
              <span>{t('marketplace.editor.hooks.card.summary.commands', { count: 1 })}</span>
            </div>
          </div>
        </div>

        <div className="absolute right-4 top-4 flex items-center gap-2">
          <button type="button" className="rounded-md p-2 transition-colors hover:bg-muted" onClick={() => setDialogOpen(true)}>
            <Edit className="h-4 w-4 text-muted-foreground" />
          </button>
          <button type="button" className="rounded-md p-2 transition-colors hover:bg-muted">
            <Trash2 className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      <MarketplaceHookDialog
        open={dialogOpen}
        value={hook}
        provider={provider}
        onOpenChange={setDialogOpen}
        onSave={(value) => {
          setHook(value);
          setDialogOpen(false);
          onDirty?.();
        }}
      />
    </>
  );
};

interface MarketplaceMcpServerDialogValue {
  name: string;
  description: string;
  transport: MCPTransport;
  command: string;
  args: string[];
  url: string;
  env: MCPKeyValueRow[];
  headers: MCPKeyValueRow[];
}

interface MarketplaceMcpServerDialogProps {
  open: boolean;
  mode?: 'create' | 'edit';
  value: MarketplaceMcpServerDialogValue;
  onOpenChange: (open: boolean) => void;
  onSave: (value: MarketplaceMcpServerDialogValue) => void;
}

const MarketplaceMcpServerDialog: React.FC<MarketplaceMcpServerDialogProps> = ({
  open,
  mode = 'edit',
  value,
  onOpenChange,
  onSave,
}) => {
  const { t } = useI18n();
  const [draft, setDraft] = React.useState(value);
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setDraft(value);
      setSubmitError(null);
      setSubmitting(false);
    }
  }, [open, value]);

  const handleChange = <TField extends keyof MarketplaceMcpServerDialogValue>(
    field: TField,
    nextValue: MarketplaceMcpServerDialogValue[TField],
  ) => {
    setSubmitError(null);
    setDraft(prev => ({ ...prev, [field]: nextValue }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);

    if (!draft.name.trim()) {
      setSubmitError(t('marketplace.editor.mcp.dialog.validation.nameRequired'));
      return;
    }
    if (!draft.description.trim()) {
      setSubmitError(t('marketplace.editor.mcp.dialog.validation.descriptionRequired'));
      return;
    }
    if (draft.transport === 'stdio' && !draft.command.trim()) {
      setSubmitError(t('marketplace.editor.mcp.dialog.validation.commandRequired'));
      return;
    }
    if ((draft.transport === 'http' || draft.transport === 'sse') && !draft.url.trim()) {
      setSubmitError(t('marketplace.editor.mcp.dialog.validation.urlRequired'));
      return;
    }

    setSubmitting(true);
    onSave({
      ...draft,
      name: draft.name.trim(),
      description: draft.description.trim(),
      command: draft.command.trim(),
      args: draft.args.map(arg => arg.trim()).filter(Boolean),
      url: draft.url.trim(),
      env: createMCPKeyValueRows(toMCPKeyValueRecord(draft.env)),
      headers: createMCPKeyValueRows(toMCPKeyValueRecord(draft.headers)),
    });
    setSubmitting(false);
  };

  const transportOptions = (['stdio', 'sse', 'http'] as MCPTransport[]).map(transport => ({
    value: transport,
    title: t(`marketplace.editor.mcp.dialog.transport.options.${transport}.label`),
    description: t(`marketplace.editor.mcp.dialog.transport.options.${transport}.description`),
  }));

  const transportFieldLabels: MCPTransportFieldsLabels = {
    commandLabel: t('marketplace.editor.mcp.dialog.fields.command.label'),
    commandPlaceholder: t('marketplace.editor.mcp.dialog.fields.command.placeholder'),
    argsLabel: t('marketplace.editor.mcp.dialog.fields.args.label'),
    argsAdd: t('marketplace.editor.mcp.dialog.fields.args.add'),
    argsEmpty: t('marketplace.editor.mcp.dialog.fields.args.empty'),
    argsPlaceholder: index => t('marketplace.editor.mcp.dialog.fields.args.placeholder', { index }),
    urlLabel: t('marketplace.editor.mcp.dialog.fields.url.label'),
    urlPlaceholder: t(
      draft.transport === 'sse'
        ? 'marketplace.editor.mcp.dialog.fields.url.placeholderSse'
        : 'marketplace.editor.mcp.dialog.fields.url.placeholderHttp',
    ),
    urlHint: t(
      draft.transport === 'sse'
        ? 'marketplace.editor.mcp.dialog.fields.url.hintSse'
        : 'marketplace.editor.mcp.dialog.fields.url.hintHttp',
    ),
    headersLabel: t('marketplace.editor.mcp.dialog.fields.headers.label'),
    headersAdd: t('marketplace.editor.mcp.dialog.fields.headers.add'),
    headersKeyPlaceholder: t('marketplace.editor.mcp.dialog.fields.headers.keyPlaceholder'),
    headersValuePlaceholder: t('marketplace.editor.mcp.dialog.fields.headers.valuePlaceholder'),
    headersEmpty: t('marketplace.editor.mcp.dialog.fields.headers.empty'),
    headersHint: t('marketplace.editor.mcp.dialog.fields.headers.hint'),
    envLabel: t('marketplace.editor.mcp.dialog.fields.env.label'),
    envAdd: t('marketplace.editor.mcp.dialog.fields.env.add'),
    envKeyPlaceholder: t('marketplace.editor.mcp.dialog.fields.env.keyPlaceholder'),
    envValuePlaceholder: t('marketplace.editor.mcp.dialog.fields.env.valuePlaceholder'),
    envEmpty: t('marketplace.editor.mcp.dialog.fields.env.empty'),
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-2xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-primary" />
            {t(mode === 'create' ? 'marketplace.editor.mcp.dialog.titleCreate' : 'marketplace.editor.mcp.dialog.title')}
          </DialogTitle>
          <DialogDescription>
            {t(mode === 'create' ? 'marketplace.editor.mcp.dialog.descriptionCreate' : 'marketplace.editor.mcp.dialog.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="marketplace-mcp-name">{t('marketplace.editor.mcp.dialog.fields.name.label')}</Label>
                <Input
                  id="marketplace-mcp-name"
                  value={draft.name}
                  onChange={event => handleChange('name', event.target.value)}
                  placeholder={t('marketplace.editor.mcp.dialog.fields.name.placeholder')}
                  className="font-medium"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>{t('marketplace.editor.mcp.dialog.transport.label')}</Label>
                <Select value={draft.transport} onValueChange={(transport: MCPTransport) => handleChange('transport', transport)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {transportOptions.map(option => (
                      <SelectItem key={option.value} value={option.value}>
                        <div>
                          <div className="font-medium">{option.title}</div>
                          <div className="text-xs text-muted-foreground">{option.description}</div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="marketplace-mcp-description">{t('marketplace.editor.mcp.dialog.fields.description.label')}</Label>
              <Input
                id="marketplace-mcp-description"
                value={draft.description}
                onChange={event => handleChange('description', event.target.value)}
                placeholder={t('marketplace.editor.mcp.dialog.fields.description.placeholder')}
              />
            </div>

            <MCPTransportFieldsEditor
              transport={draft.transport}
              command={draft.command}
              args={draft.args}
              url={draft.url}
              env={draft.env}
              headers={draft.headers}
              submitting={submitting}
              labels={transportFieldLabels}
              onCommandChange={command => handleChange('command', command)}
              onArgsChange={args => handleChange('args', args)}
              onUrlChange={url => handleChange('url', url)}
              onEnvChange={env => handleChange('env', env)}
              onHeadersChange={headers => handleChange('headers', headers)}
            />
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <div className="flex w-full flex-col gap-3">
            {submitError ? (
              <div className="w-full">
                <p className="text-sm text-destructive">{submitError}</p>
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
                {t('marketplace.common.actions.cancel')}
              </Button>
              <Button type="submit" onClick={handleSubmit} disabled={submitting}>
                {submitting ? <LoadingSpinner size="sm" className="mr-2" /> : null}
                {t('marketplace.editor.mcp.dialog.actions.save')}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

interface MarketplaceHookDialogValue {
  name: string;
  event: string;
  matchers: HookMatcher[];
}

interface MarketplaceHookDialogProps {
  open: boolean;
  mode?: 'create' | 'edit';
  provider: MarketplaceProvider;
  value: MarketplaceHookDialogValue;
  onOpenChange: (open: boolean) => void;
  onSave: (value: MarketplaceHookDialogValue) => void;
}

const MarketplaceHookDialog: React.FC<MarketplaceHookDialogProps> = ({
  open,
  mode = 'edit',
  provider,
  value,
  onOpenChange,
  onSave,
}) => {
  const { t } = useI18n();
  const [draft, setDraft] = React.useState(value);

  React.useEffect(() => {
    if (open) {
      setDraft(value);
    }
  }, [open, value]);

  const eventOptions = React.useMemo(() => getMarketplaceHookEvents(provider).map(event => ({
    value: event,
    label: t(`marketplace.editor.hooks.events.${event}.label`),
    description: t(`marketplace.editor.hooks.events.${event}.description`),
  })), [provider, t]);

  const matcherLabels: HookMatcherActionsLabels = {
    matcherSectionTitle: t('marketplace.editor.hooks.dialog.matchers.title'),
    matcherAdd: t('marketplace.editor.hooks.dialog.matchers.add'),
    matcherPatternLabel: t('marketplace.editor.hooks.dialog.matchers.patternLabel'),
    matcherPatternPlaceholder: t('marketplace.editor.hooks.dialog.matchers.patternPlaceholder'),
    matcherPatternHelp: [
      t(`marketplace.editor.hooks.dialog.matchers.patternHelp.${provider}.overview`),
      `- ${t(`marketplace.editor.hooks.dialog.matchers.patternHelp.${provider}.literal`)}`,
      `- ${t(`marketplace.editor.hooks.dialog.matchers.patternHelp.${provider}.regex`)}`,
      `- ${t(`marketplace.editor.hooks.dialog.matchers.patternHelp.${provider}.wildcard`)}`,
    ],
    matcherSequentialLabel: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.matchers.sequentialLabel') : undefined,
    matcherSequentialHelp: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.matchers.sequentialHelp') : undefined,
    matcherRemove: t('marketplace.common.actions.remove'),
    executionSectionTitle: t('marketplace.editor.hooks.dialog.executions.title'),
    executionAdd: t('marketplace.editor.hooks.dialog.executions.add'),
    executionNameLabel: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.nameLabel') : undefined,
    executionNamePlaceholder: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.namePlaceholder') : undefined,
    executionNameHelp: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.nameHelp') : undefined,
    executionTimeoutLabel: t(`marketplace.editor.hooks.dialog.executions.timeoutLabel.${provider}`),
    executionTimeoutPlaceholder: provider === 'gemini' ? '60000' : '120',
    executionTimeoutHelp: t(`marketplace.editor.hooks.dialog.executions.timeoutHelp.${provider}`),
    executionTimeoutMax: provider === 'gemini' ? 600000 : 3600,
    executionConditionLabel: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.conditionLabel') : undefined,
    executionConditionPlaceholder: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.conditionPlaceholder') : undefined,
    executionConditionHelp: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.conditionHelp') : undefined,
    executionDescriptionLabel: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.descriptionLabel') : undefined,
    executionDescriptionPlaceholder: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.descriptionPlaceholder') : undefined,
    executionDescriptionHelp: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.descriptionHelp') : undefined,
    executionCommandLabel: t(`marketplace.editor.hooks.dialog.executions.commandLabel.${provider}`),
    executionCommandPlaceholder: t(`marketplace.editor.hooks.dialog.executions.commandPlaceholder.${provider}`),
    executionCommandHelp: t(`marketplace.editor.hooks.dialog.executions.commandHelp.${provider}`),
    executionStatusMessageLabel: provider === 'codex' || provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.statusMessageLabel') : undefined,
    executionStatusMessagePlaceholder: provider === 'codex' || provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.statusMessagePlaceholder') : undefined,
    executionStatusMessageHelp: provider === 'codex' || provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.statusMessageHelp') : undefined,
    executionAsyncLabel: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.asyncLabel') : undefined,
    executionAsyncRewakeLabel: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.asyncRewakeLabel') : undefined,
    executionShellLabel: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.shellLabel') : undefined,
    executionShellPlaceholder: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.shellPlaceholder') : undefined,
    executionShellOptions: provider === 'claude-code' ? [
      { value: 'bash', label: t('marketplace.editor.hooks.dialog.executions.shellOptions.bash') },
      { value: 'powershell', label: t('marketplace.editor.hooks.dialog.executions.shellOptions.powershell') },
    ] : undefined,
    executionRemove: t('marketplace.editor.hooks.dialog.executions.remove'),
  };

  const hasValidHooks = draft.matchers.every(matcher => (
    matcher.hooks.some(hookAction => hookAction.command?.trim())
  ));

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!hasValidHooks) return;

    onSave({
      ...draft,
      matchers: draft.matchers
        .map(matcher => ({
          matcher: matcher.matcher.trim() || '*',
          sequential: provider === 'gemini' ? Boolean(matcher.sequential) : undefined,
          hooks: matcher.hooks
            .filter(hookAction => hookAction.command?.trim())
            .map(hookAction => ({
              ...hookAction,
              type: 'command' as const,
              command: hookAction.command?.trim() ?? '',
              name: hookAction.name?.trim() || undefined,
              description: hookAction.description?.trim() || undefined,
              statusMessage: hookAction.statusMessage?.trim() || undefined,
              if: hookAction.if?.trim() || undefined,
              shell: provider === 'claude-code' ? (hookAction.shell ?? 'bash') : undefined,
              async: provider === 'claude-code' ? Boolean(hookAction.async) : undefined,
              asyncRewake: provider === 'claude-code' ? Boolean(hookAction.asyncRewake) : undefined,
              timeout: hookAction.timeout,
            })),
        }))
        .filter(matcher => matcher.hooks.length > 0),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-primary" />
            {t(mode === 'create' ? 'marketplace.editor.hooks.dialog.titleCreate' : 'marketplace.editor.hooks.dialog.title')}
          </DialogTitle>
          <DialogDescription>
            {t(`marketplace.editor.hooks.dialog.description.${provider}`)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            {provider === 'codex' ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                {t('marketplace.editor.hooks.dialog.codexFeatureFlag')}
              </div>
            ) : null}

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="marketplace-hook-name">{t('marketplace.editor.hooks.dialog.fields.name.label')}</Label>
                <Input
                  id="marketplace-hook-name"
                  value={draft.name}
                  onChange={event => setDraft(prev => ({ ...prev, name: event.target.value }))}
                  placeholder={t('marketplace.editor.hooks.dialog.fields.name.placeholder')}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('marketplace.editor.hooks.dialog.fields.event.label')}</Label>
                <Select value={draft.event} onValueChange={event => setDraft(prev => ({ ...prev, event }))}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('marketplace.editor.hooks.dialog.fields.event.placeholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {eventOptions.map(option => (
                      <SelectItem key={option.value} value={option.value}>
                        <div>
                          <div className="font-medium">{option.label}</div>
                          <div className="text-xs text-muted-foreground">{option.description}</div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {!hasValidHooks ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <WarningIcon />
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-amber-800">
                          {t('marketplace.editor.hooks.dialog.validation.commandRequired')}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            <HookMatcherActionsEditor
              matchers={draft.matchers}
              labels={matcherLabels}
              matcherCardClassName="bg-background"
              commandClassName="font-mono text-sm"
              onChange={matchers => setDraft(prev => ({ ...prev, matchers }))}
            />
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('marketplace.common.actions.cancel')}
          </Button>
          <Button type="submit" onClick={handleSubmit} disabled={!hasValidHooks}>
            {t('marketplace.editor.hooks.dialog.actions.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const getMarketplaceHookEvents = (provider: MarketplaceProvider): string[] => {
  if (provider === 'codex') {
    return [
      'SessionStart',
      'PreToolUse',
      'PostToolUse',
      'PermissionRequest',
      'UserPromptSubmit',
      'Stop',
    ];
  }
  if (provider === 'gemini') {
    return [
      'BeforeTool',
      'AfterTool',
      'BeforeAgent',
      'AfterAgent',
      'BeforeModel',
      'SessionStart',
      'PreCompress',
    ];
  }
  return [
    'PreToolUse',
    'PostToolUse',
    'UserPromptSubmit',
    'Notification',
    'Stop',
    'SubagentStop',
    'PreCompact',
    'SessionStart',
    'SessionEnd',
  ];
};

const formatMarketplaceHookTimeout = (provider: MarketplaceProvider, timeout?: number): string => (
  provider === 'gemini' ? `${timeout ?? 60000}ms` : `${timeout ?? 120}s`
);

interface MarketplaceEditorResourceItemCardProps {
  item: MarketplaceEditorResourceItem;
  icon: React.ComponentType<{ className?: string }>;
}

const MarketplaceEditorResourceItemCard: React.FC<MarketplaceEditorResourceItemCardProps> = ({ item, icon: Icon }) => {
  const { t } = useI18n();

  return (
    <div className="rounded-lg border border-border bg-background p-4 transition-shadow hover:shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <Icon className="h-5 w-5 text-primary" />
          </div>
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-foreground">{marketplaceEditorItemTitle(item, t)}</h3>
              {item.badge ? (
                <Badge variant="outline" className="text-xs">
                  {item.badge}
                </Badge>
              ) : null}
            </div>
            <p className="text-sm text-muted-foreground">{marketplaceEditorItemDescription(item, t)}</p>
            <div className="font-mono text-xs text-muted-foreground">{item.path}</div>
          </div>
        </div>
      </div>

      {item.code ? (
        <div className="mt-4 rounded-md bg-muted/50 p-3">
          <code className="break-all font-mono text-sm text-foreground">{item.code}</code>
        </div>
      ) : null}

      {item.meta?.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {item.meta.map(meta => (
            <Badge key={`${item.id}-${meta.labelKey}`} variant="secondary" className="text-[11px]">
              {t(meta.labelKey)}: {meta.value}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const getMarketplaceItemFileName = (item: MarketplaceEditorResourceItem): string => (
  item.path.split('/').pop() || item.id
);

const marketplaceJoinPath = (parentPath: string | null, name: string): string => (
  parentPath ? `${parentPath.replace(/\/$/, '')}/${name}` : `/${name}`
);

const marketplaceParentPath = (path: string): string | null => {
  const normalized = path.replace(/\/$/, '');
  const index = normalized.lastIndexOf('/');
  if (index <= 0) return null;
  return normalized.slice(0, index);
};

const marketplaceFileContentsFromTree = (nodes: FileTreeNode[]): Record<string, string> => {
  const contents: Record<string, string> = {};
  const walk = (items: FileTreeNode[]) => {
    items.forEach(node => {
      if (node.type === 'file') {
        contents[node.path] = typeof node.metadata?.content === 'string' ? node.metadata.content : '';
      }
      if (node.children) {
        walk(node.children);
      }
    });
  };
  walk(nodes);
  return contents;
};

const marketplaceFeatureItemsToFileTree = (
  items: MarketplaceEditorResourceItem[],
  basePath: string,
): FileTreeNode[] => {
  const roots: FileTreeNode[] = [];
  const directories = new Map<string, FileTreeNode>();

  const ensureDirectory = (path: string, name: string, parent: FileTreeNode[] | undefined) => {
    const existing = directories.get(path);
    if (existing) return existing;
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: 'directory',
      children: [],
    };
    directories.set(path, node);
    (parent ?? roots).push(node);
    return node;
  };

  items.forEach(item => {
    const relativePath = item.path.replace(new RegExp(`^${basePath}/?`), '');
    const parts = relativePath.split('/').filter(Boolean);
    let parentChildren = roots;
    let currentPath = '';

    parts.slice(0, -1).forEach(part => {
      currentPath = marketplaceJoinPath(currentPath || null, part);
      const directory = ensureDirectory(currentPath, part, parentChildren);
      parentChildren = directory.children ?? [];
    });

    const fileName = parts.at(-1) ?? getMarketplaceItemFileName(item);
    const filePath = marketplaceJoinPath(currentPath || null, fileName);
    parentChildren.push({
      id: filePath,
      name: fileName,
      path: filePath,
      type: 'file',
      extension: fileName.split('.').pop(),
      size: item.content.length,
      metadata: { content: item.content },
    });
  });

  return roots;
};

const marketplacePackageFilesToFileTree = (
  files: MarketplacePackageFile[],
  rootPath: string,
  scope: 'plugin' | 'extension',
): FileTreeNode[] => {
  const packageName = rootPath.split('/').at(-1) ?? rootPath;
  const root: FileTreeNode = {
    id: rootPath,
    name: packageName,
    path: rootPath,
    type: 'directory',
    scope,
    children: [],
  };
  const directories = new Map<string, FileTreeNode>([[rootPath, root]]);

  const ensureDirectory = (path: string, name: string, parentChildren: FileTreeNode[]) => {
    const existing = directories.get(path);
    if (existing) return existing;
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: 'directory',
      scope,
      children: [],
    };
    directories.set(path, node);
    parentChildren.push(node);
    return node;
  };

  files.forEach(file => {
    const parts = file.path.split('/').filter(Boolean);
    if (parts.length === 0) return;

    let currentPath = rootPath;
    let parentChildren = root.children ?? [];

    parts.slice(0, -1).forEach(part => {
      currentPath = marketplaceJoinPath(currentPath, part);
      const directory = ensureDirectory(currentPath, part, parentChildren);
      parentChildren = directory.children ?? [];
    });

    const fileName = parts.at(-1);
    if (!fileName) return;
    const path = marketplaceJoinPath(currentPath, fileName);
    parentChildren.push({
      id: path,
      name: fileName,
      path,
      type: 'file',
      extension: fileName.split('.').pop(),
      scope,
      size: file.size,
      metadata: {
        content: file.content,
        binary: file.binary,
        mimeType: file.mimeType,
      },
    });
  });

  return root.children ?? [];
};

const marketplacePackageFilesFromTree = (
  nodes: FileTreeNode[],
  packageRootPath: string,
  contents: Record<string, string>,
): MarketplacePackageFile[] => {
  const files: MarketplacePackageFile[] = [];
  const rootPrefix = `${packageRootPath.replace(/\/$/, '')}/`;

  const walk = (items: FileTreeNode[]) => {
    items.forEach(node => {
      if (node.type === 'file') {
        const relativePath = node.path.startsWith(rootPrefix)
          ? node.path.slice(rootPrefix.length)
          : node.path.replace(/^\//, '');
        files.push({
          path: relativePath,
          content: contents[node.path] ?? getStringField(node.metadata?.content, ''),
          binary: Boolean(node.metadata?.binary),
          mimeType: getStringField(node.metadata?.mimeType) || undefined,
          size: typeof node.size === 'number' ? node.size : (contents[node.path] ?? '').length,
        });
      }
      if (node.children) {
        walk(node.children);
      }
    });
  };

  walk(nodes);
  return files;
};

const marketplaceDirectoryPaths = (nodes: FileTreeNode[]): string[] => {
  return getAllDirectoryNodes(nodes).map(node => node.path);
};

const marketplaceFindFirstFilePath = (nodes: FileTreeNode[]): string | undefined => {
  for (const node of nodes) {
    if (node.type === 'file') return node.path;
    const childPath = node.children ? marketplaceFindFirstFilePath(node.children) : undefined;
    if (childPath) return childPath;
  }
  return undefined;
};

const marketplaceRenameNode = (
  nodes: FileTreeNode[],
  oldPath: string,
  nextPath: string,
  nextName: string,
): FileTreeNode[] => (
  nodes.map(node => {
    if (node.path === oldPath || node.path.startsWith(`${oldPath}/`)) {
      const renamedPath = node.path.replace(oldPath, nextPath);
      return {
        ...node,
        id: renamedPath,
        path: renamedPath,
        name: node.path === oldPath ? nextName : node.name,
        children: node.children ? marketplaceRenameNode(node.children, oldPath, nextPath, nextName) : undefined,
      };
    }
    return {
      ...node,
      children: node.children ? marketplaceRenameNode(node.children, oldPath, nextPath, nextName) : undefined,
    };
  })
);

const marketplaceRenameContentPaths = (
  contents: Record<string, string>,
  oldPath: string,
  nextPath: string,
): Record<string, string> => (
  Object.fromEntries(Object.entries(contents).map(([path, content]) => [
    path === oldPath || path.startsWith(`${oldPath}/`) ? path.replace(oldPath, nextPath) : path,
    content,
  ]))
);

const marketplaceDeleteContentPaths = (
  contents: Record<string, string>,
  paths: string[],
): Record<string, string> => (
  Object.fromEntries(Object.entries(contents).filter(([path]) => (
    !paths.some(deletedPath => path === deletedPath || path.startsWith(`${deletedPath}/`))
  )))
);

const marketplaceCloneNodeForParent = (
  node: FileTreeNode,
  parentPath: string | null,
  existingNodes: FileTreeNode[],
): { node: FileTreeNode } => {
  const existingPaths = new Set(existingNodes.map(item => item.path));
  let name = node.name;
  let path = marketplaceJoinPath(parentPath, name);
  let copyIndex = 1;
  while (existingPaths.has(path)) {
    const parts = node.name.split('.');
    if (parts.length > 1 && node.type === 'file') {
      const extension = parts.pop();
      name = `${parts.join('.')}-${copyIndex}.${extension}`;
    } else {
      name = `${node.name}-${copyIndex}`;
    }
    path = marketplaceJoinPath(parentPath, name);
    copyIndex += 1;
  }

  const cloneChildren = (children?: FileTreeNode[], sourceParentPath = node.path, targetParentPath = path): FileTreeNode[] | undefined => (
    children?.map(child => {
      const childPath = child.path.replace(sourceParentPath, targetParentPath);
      return {
        ...child,
        id: childPath,
        path: childPath,
        children: cloneChildren(child.children, sourceParentPath, targetParentPath),
      };
    })
  );

  return {
    node: {
      ...node,
      id: path,
      path,
      name,
      children: cloneChildren(node.children),
    },
  };
};

const marketplaceRemapContentPaths = (
  contents: Record<string, string>,
  oldPath: string,
  nextPath: string,
): Record<string, string> => (
  Object.fromEntries(Object.entries(contents)
    .filter(([path]) => path === oldPath || path.startsWith(`${oldPath}/`))
    .map(([path, content]) => [path.replace(oldPath, nextPath), content]))
);

export default MarketplaceEditorView;
