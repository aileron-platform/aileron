import type { MarketplaceFeatureContentItem, MarketplacePackageDetail, MarketplacePackageFile, MarketplaceProvider } from '@/shared/types/marketplace';

import { type MarketplaceEditorResourceItem, type MarketplaceMarkdownEditorTab } from './marketplaceEditorResourceItems';
import { stringifyMarketplaceJson } from './marketplaceEditorRequiredDraft';

export type MarketplaceEditorFeatureTab = 'skills' | 'agents' | 'commands' | 'mcp' | 'hooks' | 'outputStyle' | 'policies' | 'files';

export type MarketplaceEditorFeatureItems = Record<MarketplaceEditorFeatureTab, MarketplaceEditorResourceItem[]>;

export const emptyMarketplaceFeatureItems = (): MarketplaceEditorFeatureItems => ({
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

export const marketplacePackageFileFromResourceItem = (item: MarketplaceEditorResourceItem): MarketplacePackageFile => {
  const extension = item.path.split('.').pop()?.toLowerCase() ?? '';
  const mimeType = extension === 'json'
    ? 'application/json'
    : extension === 'toml'
      ? 'application/toml'
      : 'text/markdown';

  return {
    path: item.path,
    content: item.content,
    binary: false,
    mimeType,
    size: item.content.length,
  };
};

export const marketplaceApplyResourceItemsToPackageFiles = (
  files: MarketplacePackageFile[],
  items: MarketplaceEditorResourceItem[],
  managedPrefixes: string[],
): MarketplacePackageFile[] => {
  const itemPaths = new Set(items.map(item => item.path));
  const nextFiles = files.filter(file => (
    !itemPaths.has(file.path) &&
    !managedPrefixes.some(prefix => file.path === prefix.slice(0, -1) || file.path.startsWith(prefix))
  ));

  return [
    ...nextFiles,
    ...items.map(marketplacePackageFileFromResourceItem),
  ].sort((first, second) => first.path.localeCompare(second.path));
};

export const marketplaceMarkdownManagedPrefixes: Record<MarketplaceMarkdownEditorTab, string[]> = {
  agents: ['agents/'],
  commands: ['commands/'],
  outputStyle: ['output-styles/'],
  policies: ['policies/'],
};

export const marketplaceApplyPackageFiles = (
  files: MarketplacePackageFile[],
  packageFiles: MarketplacePackageFile[],
  managedPrefixes: string[],
): MarketplacePackageFile[] => {
  const packageFilePaths = new Set(packageFiles.map(file => file.path));
  const nextFiles = files.filter(file => (
    !packageFilePaths.has(file.path) &&
    !managedPrefixes.some(prefix => file.path === prefix.slice(0, -1) || file.path.startsWith(prefix))
  ));

  return [
    ...nextFiles,
    ...packageFiles,
  ].sort((first, second) => first.path.localeCompare(second.path));
};

export const marketplaceTextPackageFile = (path: string, content: string, mimeType = 'text/markdown'): MarketplacePackageFile => ({
  path,
  content,
  binary: false,
  mimeType,
  size: content.length,
});

export const marketplaceFeatureItemsFromDetail = (detail: MarketplacePackageDetail | null): MarketplaceEditorFeatureItems | null => {
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

export const getMarketplaceScaffoldFeatureItems = (provider: MarketplaceProvider): MarketplaceEditorFeatureItems => providerScaffoldFeatureItems[provider];

