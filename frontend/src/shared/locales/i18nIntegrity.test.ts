import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import en from './en';
import zhTW from './zh-TW';

type LocaleTree = Record<string, unknown>;

const currentFile = fileURLToPath(import.meta.url);
const srcRoot = path.resolve(path.dirname(currentFile), '../..');
const localeRoot = path.resolve(srcRoot, 'shared/locales');
const hanRegex = /[\u3400-\u9fff]/;

const flattenKeys = (tree: LocaleTree, prefix = ''): string[] =>
  Object.entries(tree).flatMap(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenKeys(value as LocaleTree, nextKey);
    }
    return [nextKey];
  });

const flattenValues = (tree: LocaleTree, prefix = ''): Array<{ key: string; value: string }> =>
  Object.entries(tree).flatMap(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenValues(value as LocaleTree, nextKey);
    }
    return typeof value === 'string' ? [{ key: nextKey, value }] : [];
  });

const listSourceFiles = (root: string): string[] => {
  const entries = fs.readdirSync(root, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const entryPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      return listSourceFiles(entryPath);
    }
    return /\.(ts|tsx|js|jsx)$/.test(entry.name) ? [entryPath] : [];
  });
};

const getByKey = (tree: LocaleTree, key: string): unknown =>
  key.split('.').reduce<unknown>((cursor, part) => {
    if (!cursor || typeof cursor !== 'object') {
      return undefined;
    }
    return (cursor as LocaleTree)[part];
  }, tree);

const listStaticMarketplaceKeys = (): string[] => {
  const marketplaceRoot = path.resolve(srcRoot, 'features/marketplace');
  const keyPatterns = [
    /\bt\(\s*['`]([^'`$]*marketplace\.[^'`]*)['`]/g,
    /(?:titleKey|descriptionKey|emptyTitle|emptyDescription|labelKey):\s*['`]([^'`$]*marketplace\.[^'`]*)['`]/g,
  ];
  const keys = new Set<string>();

  for (const filePath of listSourceFiles(marketplaceRoot)) {
    const source = fs.readFileSync(filePath, 'utf8');
    for (const pattern of keyPatterns) {
      let match: RegExpExecArray | null;
      while ((match = pattern.exec(source))) {
        if (!match[1].includes('${')) {
          keys.add(match[1]);
        }
      }
    }
  }

  return [...keys].sort();
};

// i18next resolves `key` from the `key_one` / `key_other` plural forms when a
// count is supplied, so treat either shape as a resolvable translation.
const resolvesInLocale = (tree: LocaleTree, key: string): boolean => (
  typeof getByKey(tree, key) === 'string'
  || (typeof getByKey(tree, `${key}_one`) === 'string'
    && typeof getByKey(tree, `${key}_other`) === 'string')
);

const listStaticTranslationCallKeys = (): string[] => {
  const callPattern = /\bt\(\s*'([a-zA-Z][\w.]*\.[\w.]+)'/g;
  const keys = new Set<string>();

  const candidatePaths = listSourceFiles(srcRoot)
    .filter((filePath) => !/\.(test|spec)\.(ts|tsx)$/.test(filePath))
    .filter((filePath) => !filePath.startsWith(localeRoot));

  for (const filePath of candidatePaths) {
    const source = fs.readFileSync(filePath, 'utf8');
    let match: RegExpExecArray | null;
    while ((match = callPattern.exec(source))) {
      keys.add(match[1]);
    }
  }

  return [...keys].sort();
};

describe('i18n integrity', () => {
  it('keeps English and Traditional Chinese locale keys aligned', () => {
    expect(flattenKeys(zhTW).sort()).toEqual(flattenKeys(en).sort());
  });

  it('includes shared document workflow labels in both languages', () => {
    expect(en.shared.documentWorkflow.metadata.fileName.label).toBeTruthy();
    expect(zhTW.shared.documentWorkflow.metadata.fileName.label).toBeTruthy();
    expect(en.shared.documentWorkflow.detail.unsavedGuard).toBeTruthy();
    expect(zhTW.shared.documentWorkflow.detail.unsavedGuard).toBeTruthy();
  });

  it('keeps English locale values free of Traditional Chinese fallback text', () => {
    const valuesWithHan = flattenValues(en).filter(({ value }) => hanRegex.test(value));

    expect(valuesWithHan).toEqual([]);
  });

  it('resolves static Marketplace translation keys in both languages', () => {
    const missing = listStaticMarketplaceKeys().filter((key) => (
      getByKey(en, key) === undefined || getByKey(zhTW, key) === undefined
    ));

    expect(missing).toEqual([]);
  });

  it('resolves every statically referenced translation key in both languages', () => {
    const missing = listStaticTranslationCallKeys().filter((key) => (
      !resolvesInLocale(en, key) || !resolvesInLocale(zhTW, key)
    ));

    expect(missing).toEqual([]);
  });

  it('localizes every Marketplace install resource type in both languages', () => {
    const resourceTypes = [
      'instructions',
      'skill',
      'subagent',
      'agent',
      'command',
      'slashCommand',
      'output-style',
      'prompt',
      'rule',
      'mcp',
      'hook',
      'lsp',
      'app',
      'dependency-payload',
    ];
    const keys = resourceTypes.map(
      resourceType => `marketplace.install.resourceTypes.${resourceType}`,
    );

    expect(keys.filter(key => getByKey(en, key) === undefined)).toEqual([]);
    expect(keys.filter(key => getByKey(zhTW, key) === undefined)).toEqual([]);
    const translatedResourceTypes = resourceTypes.filter(
      resourceType => resourceType !== 'slashCommand',
    );
    expect(translatedResourceTypes.map(
      resourceType => `marketplace.install.resourceTypes.${resourceType}`,
    ).filter(key => (
      typeof getByKey(zhTW, key) !== 'string'
      || !hanRegex.test(getByKey(zhTW, key) as string)
    ))).toEqual([]);
  });

  it('localizes every Codex plugin policy and hook trust state', () => {
    const keys = [
      ...['inherit', 'auto', 'prompt', 'writes', 'approve'].map(
        mode => `workspace.agentSettings.common.mcp.pluginPolicy.approvalModes.${mode}`,
      ),
      ...['trusted', 'untrusted', 'modified', 'mixed'].map(
        state => `workspace.agentSettings.common.hooks.pluginTrust.states.${state}`,
      ),
      ...['active', 'inactive'].flatMap((state) => [
        `workspace.agentSettings.common.mcp.pluginPolicy.effective.${state}`,
        `workspace.agentSettings.common.hooks.pluginTrust.effective.${state}`,
      ]),
      ...[
        'revisionConflict',
        'notFound',
        'scopeNotSupported',
        'provenanceMissing',
        'invalidMcpPolicy',
        'invalidHookTrust',
        'hookTrustNotSupported',
        'unknown',
      ].map(
        error => `workspace.agentSettings.pluginResources.controlErrors.${error}`,
      ),
    ];

    expect(keys.filter(key => getByKey(en, key) === undefined)).toEqual([]);
    expect(keys.filter(key => getByKey(zhTW, key) === undefined)).toEqual([]);
    expect(keys.filter(key => (
      typeof getByKey(zhTW, key) !== 'string'
      || !hanRegex.test(getByKey(zhTW, key) as string)
    ))).toEqual([]);
  });

  it('resolves dynamic Workspace file chooser preset keys in both languages', () => {
    const presetKeys = [
      'markdown',
      'testMarkdown',
      'typescript',
      'react',
      'javascript',
      'json',
      'css',
      'all',
    ];
    const keys = presetKeys.flatMap((preset) => [
      `workspace.chat.dialogs.fileChooser.filterPresets.${preset}.label`,
      `workspace.chat.dialogs.fileChooser.filterPresets.${preset}.description`,
    ]);
    const missing = keys.filter((key) => (
      getByKey(en, key) === undefined || getByKey(zhTW, key) === undefined
    ));

    expect(missing).toEqual([]);
  });

  it('resolves AI Chat thread error notice translation keys in both languages', () => {
    const keys = [
      'aiChat.error.agentFailed.title',
      'aiChat.error.agentFailed.description',
      'aiChat.error.promptTooLong.title',
      'aiChat.error.promptTooLong.description',
      'aiChat.error.invalidToolSelection.title',
      'aiChat.error.invalidToolSelection.description',
      'aiChat.error.unknown.title',
      'aiChat.error.unknown.description',
      'aiChat.error.details.show',
      'aiChat.error.details.hide',
      'aiChat.error.retry',
    ];

    const missing = keys.filter((key) => (
      getByKey(en, key) === undefined || getByKey(zhTW, key) === undefined
    ));

    expect(missing).toEqual([]);
  });

  it('resolves workspace knowledge base states and stable error codes in both languages', () => {
    const attachmentStatuses = ['active', 'pending', 'pending_removal'];
    const pendingAttachmentStatuses = ['pending', 'pending_removal'];
    const mountStatuses = ['ready', 'syncing', 'degraded'];
    const accessStatuses = ['ready', 'recycling'];
    const errorCodes = [
      'KB_MOUNT_ALIAS_INVALID',
      'KB_MOUNT_SOURCE_INVALID',
      'WORKSPACE_ACCESS_DENIED',
      'KB_ACCESS_DENIED',
      'KB_PERMISSION_DENIED',
      'WORKSPACE_RUNTIME_ACTION_FORBIDDEN',
      'WORKSPACE_NOT_FOUND',
      'KB_NOT_FOUND',
      'KB_ATTACHMENT_NOT_FOUND',
      'KB_ALREADY_ATTACHED',
      'KB_MOUNT_ALIAS_CONFLICT',
      'WORKSPACE_KB_MOUNT_SYNC_IN_PROGRESS',
      'WORKSPACE_KB_MOUNT_SYNC_NOT_RETRYABLE',
      'WORKSPACE_KB_MOUNT_RECONCILE_FAILED',
      'WORKSPACE_KB_MOUNT_JOB_INVALID',
      'WORKSPACE_KB_MOUNT_SNAPSHOT_INVALID',
      'WORKSPACE_KB_MOUNT_STATE_INVALID',
      'WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED',
      'WORKSPACE_LIFECYCLE_FAILED',
      'unknown',
    ];
    const keys = [
      ...attachmentStatuses.flatMap((status) => [
        `knowledgeBase.attachments.status.${status}`,
        `workspace.workspaceSettings.knowledgeBases.attachmentStatus.${status}`,
      ]),
      ...pendingAttachmentStatuses.map((status) => (
        `workspace.workspaceSettings.knowledgeBases.attachmentStatusDescription.${status}`
      )),
      ...mountStatuses.map((status) => (
        `workspace.workspaceSettings.knowledgeBases.mounted.mount.status.${status}`
      )),
      ...accessStatuses.map((status) => (
        `workspace.workspaceSettings.knowledgeBases.mounted.access.status.${status}`
      )),
      ...errorCodes.map((errorCode) => (
        `workspace.workspaceSettings.knowledgeBases.errors.${errorCode}`
      )),
    ];
    const missing = keys.filter((key) => (
      getByKey(en, key) === undefined || getByKey(zhTW, key) === undefined
    ));

    expect(missing).toEqual([]);
  });

  it('uses explicit Agent Resume labels without the legacy session key', () => {
    expect(getByKey(en, 'aiChat.init.agentResume')).toBe('Agent Resume ID');
    expect(getByKey(zhTW, 'aiChat.init.agentResume')).toBe('Agent \u63a5\u7e8c ID');
    expect(getByKey(en, 'aiChat.init.session')).toBeUndefined();
    expect(getByKey(zhTW, 'aiChat.init.session')).toBeUndefined();
  });

  it('keeps Chinese text isolated to Traditional Chinese locale files', async () => {
    const candidatePaths = listSourceFiles(srcRoot)
      .filter((filePath) => !filePath.startsWith(path.join(localeRoot, 'zh-TW')));
    const sourceFiles = await Promise.all(candidatePaths.map(async (filePath) => ({
      filePath,
      source: await fs.promises.readFile(filePath, 'utf8'),
    })));
    const filesWithHan = sourceFiles
      .filter(({ source }) => hanRegex.test(source))
      .map(({ filePath }) => path.relative(srcRoot, filePath));

    expect(filesWithHan).toEqual([]);
  });
});
