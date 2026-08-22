import { access, readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const docsSiteDirectory = path.resolve(scriptDirectory, '..');
const repositoryDirectory = path.resolve(docsSiteDirectory, '..');
const localeRoots = new Map([
  ['zh-Hant', path.join(docsSiteDirectory, 'docs')],
  [
    'en',
    path.join(
      docsSiteDirectory,
      'i18n',
      'en',
      'docusaurus-plugin-content-docs',
      'current',
    ),
  ],
]);

async function listDocuments(root, directory = root) {
  const entries = await readdir(directory, { withFileTypes: true });
  const documents = [];

  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      documents.push(...await listDocuments(root, entryPath));
    } else if (/\.mdx?$/.test(entry.name)) {
      documents.push(path.relative(root, entryPath));
    }
  }

  return documents.sort();
}

function frontMatter(source, documentName) {
  const lines = source.split(/\r?\n/);
  if (lines[0] !== '---') {
    throw new Error(`${documentName} does not start with front matter.`);
  }

  const endIndex = lines.indexOf('---', 1);
  if (endIndex === -1) {
    throw new Error(`${documentName} has unterminated front matter.`);
  }

  const keys = lines
    .slice(1, endIndex)
    .map((line) => line.match(/^([A-Za-z0-9_-]+):/)?.[1])
    .filter(Boolean)
    .sort();

  if (!keys.includes('title')) {
    throw new Error(`${documentName} has no front matter title.`);
  }
  if (keys.includes('sidebar_position')) {
    throw new Error(
      `${documentName} declares sidebar_position even though sidebars.ts owns ordering.`,
    );
  }

  return keys;
}

function markdownFacts(source, documentName) {
  const headings = [];
  const internalLinks = new Set();
  const visibleLines = [];
  let fence = null;

  for (const [index, line] of source.split(/\r?\n/).entries()) {
    const fenceMatch = line.match(/^\s*(`{3,}|~{3,})/);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (fence === null) {
        fence = marker[0];
      } else if (marker[0] === fence) {
        fence = null;
      }
      visibleLines.push('');
      continue;
    }
    if (fence !== null) {
      visibleLines.push('');
      continue;
    }
    visibleLines.push(line);

    const headingMatch = line.match(/^(#{1,6})\s+(.+)/);
    if (headingMatch) {
      headings.push({
        level: headingMatch[1].length,
        line: index + 1,
      });
    }

  }

  if (fence !== null) {
    throw new Error(`${documentName} has an unterminated code fence.`);
  }

  const visibleSource = visibleLines.join('\n');
  for (const linkMatch of visibleSource.matchAll(/(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+['"][^)]*['"])?\)/gs)) {
    const target = linkMatch[1];
    if (/^(?:https?:|mailto:|#)/.test(target)) {
      continue;
    }
    internalLinks.add(target.split('#')[0]);
  }

  const h1Count = headings.filter(({ level }) => level === 1).length;
  if (h1Count !== 1) {
    throw new Error(`${documentName} has ${h1Count} level-one headings; expected 1.`);
  }

  for (let index = 1; index < headings.length; index += 1) {
    const previous = headings[index - 1];
    const current = headings[index];
    if (current.level > previous.level + 1) {
      throw new Error(
        `${documentName}:${current.line} jumps from H${previous.level} to H${current.level}.`,
      );
    }
  }

  return {
    headingLevels: headings.map(({ level }) => level),
    internalLinks: [...internalLinks].sort(),
  };
}

function assertEqualList(left, right, description) {
  if (JSON.stringify(left) === JSON.stringify(right)) {
    return;
  }

  const leftOnly = left.filter((value) => !right.includes(value));
  const rightOnly = right.filter((value) => !left.includes(value));
  throw new Error(
    `${description} differs. zh-Hant only: ${leftOnly.join(', ') || 'none'}; en only: ${rightOnly.join(', ') || 'none'}.`,
  );
}

function assertEqualSequence(left, right, description) {
  if (JSON.stringify(left) === JSON.stringify(right)) {
    return;
  }

  const length = Math.max(left.length, right.length);
  const differentIndex = Array.from({ length }, (_, index) => index)
    .find((index) => left[index] !== right[index]);
  throw new Error(
    `${description} differs at index ${differentIndex}: zh-Hant=${left[differentIndex] ?? 'missing'}, en=${right[differentIndex] ?? 'missing'}.`,
  );
}

const documentsByLocale = new Map();
for (const [locale, root] of localeRoots) {
  documentsByLocale.set(locale, await listDocuments(root));
}

const zhHantDocuments = documentsByLocale.get('zh-Hant');
const englishDocuments = documentsByLocale.get('en');
assertEqualList(zhHantDocuments, englishDocuments, 'Localized document paths');

for (const relativePath of zhHantDocuments) {
  const factsByLocale = new Map();
  const frontMatterByLocale = new Map();

  for (const [locale, root] of localeRoots) {
    const documentName = `${locale}:${relativePath}`;
    const source = await readFile(path.join(root, relativePath), 'utf8');
    frontMatterByLocale.set(locale, frontMatter(source, documentName));
    factsByLocale.set(locale, markdownFacts(source, documentName));
  }

  assertEqualList(
    frontMatterByLocale.get('zh-Hant'),
    frontMatterByLocale.get('en'),
    `${relativePath} front matter keys`,
  );
  assertEqualSequence(
    factsByLocale.get('zh-Hant').headingLevels,
    factsByLocale.get('en').headingLevels,
    `${relativePath} heading structure`,
  );
  assertEqualList(
    factsByLocale.get('zh-Hant').internalLinks,
    factsByLocale.get('en').internalLinks,
    `${relativePath} internal link targets`,
  );
}

const documentIds = zhHantDocuments.map((relativePath) => (
  relativePath.replace(/\.mdx?$/, '')
));
const documentIdSet = new Set(documentIds);

const requiredInformationArchitecture = [
  'architecture/overview/index',
  'architecture/frontend/index',
  'architecture/backend/index',
  'architecture/backend/workspace-manager/index',
  'architecture/backend/workspace-runtime/index',
  'features/platform/index',
  'features/workspace/index',
  'features/automation/index',
  'features/marketplace/index',
  'features/knowledge-base/index',
  'features/user-management/index',
];
for (const documentId of requiredInformationArchitecture) {
  if (!documentIdSet.has(documentId)) {
    throw new Error(`Required information-architecture entry is missing: ${documentId}.`);
  }
}

const removedDocumentIds = [
  'architecture/overview',
  'architecture/frontend',
  'architecture/workspace-manager',
  'architecture/workspace-runtime',
  'architecture/backend-domain-modules',
  'architecture/backend-deep-modules',
  'features/automation',
  'features/marketplace',
  'features/user-management-permissions',
  'features/platform-resource-statistics-and-capacity',
];
for (const documentId of removedDocumentIds) {
  if (documentIdSet.has(documentId)) {
    throw new Error(`Removed documentation path still exists: ${documentId}.`);
  }
}
const sidebarSource = await readFile(
  path.join(docsSiteDirectory, 'sidebars.ts'),
  'utf8',
);
const sidebarIdCounts = new Map(documentIds.map((documentId) => [documentId, 0]));
for (const match of sidebarSource.matchAll(/(['"])([^'"\n]+)\1/g)) {
  const value = match[2];
  if (documentIdSet.has(value)) {
    sidebarIdCounts.set(value, sidebarIdCounts.get(value) + 1);
  }
}
const invalidSidebarIds = [...sidebarIdCounts]
  .filter(([, count]) => count !== 1)
  .map(([documentId, count]) => `${documentId} (${count})`);
if (invalidSidebarIds.length > 0) {
  throw new Error(
    `Every document must appear exactly once in sidebars.ts: ${invalidSidebarIds.join(', ')}.`,
  );
}

const sourcePathPattern = /`((?:frontend|workspace-manager|workspace-runtime|workspace-operator|workspace-terminal|packages|contracts|helm)\/[^`\n]*)`/g;
for (const relativePath of zhHantDocuments) {
  const source = await readFile(path.join(localeRoots.get('zh-Hant'), relativePath), 'utf8');
  for (const match of source.matchAll(sourcePathPattern)) {
    const reference = match[1].split('::')[0].replace(/[.,;:]$/, '');
    if (/[*{}]/.test(reference)) {
      continue;
    }
    try {
      await access(path.join(repositoryDirectory, reference));
    } catch {
      throw new Error(`${relativePath} references a missing source path: ${reference}.`);
    }
  }
}

for (const [locale, root] of localeRoots) {
  const source = await readFile(path.join(root, 'installation/kubernetes.md'), 'utf8');
  const externalOidc = source.match(/^- `externalOidc`[：:][\s\S]*?(?=\n\n)/m)?.[0];
  if (!externalOidc) {
    throw new Error(`${locale}:installation/kubernetes.md has no externalOidc Namespace contract.`);
  }
  for (const namespace of [
    'workspace-system',
    'aileron-turn-system',
    'aileron-backend-attestor-system',
    'aileron-identity-system',
  ]) {
    if (!externalOidc.includes(`\`${namespace}\``)) {
      throw new Error(`${locale}:externalOidc contract is missing ${namespace}.`);
    }
  }
  const identityAbsent = locale === 'zh-Hant'
    ? /`aileron-identity-system` 必須不存在/.test(externalOidc)
    : /`aileron-identity-system` must be absent/.test(externalOidc);
  if (!identityAbsent || /前兩個 Namespace|first two Namespaces/.test(externalOidc)) {
    throw new Error(`${locale}:externalOidc Namespace contract is stale.`);
  }
  for (const requiredAcceptanceToken of [
    'kubeconfig.raw',
    'acceptance_bundle.py',
    'acceptance_evidence.py',
    'frontend/e2e/homelab-acceptance.mjs',
    'acceptance_producer.py',
    'oidcWorkspace',
    'workspaceLifecycle',
    '`terminal`',
    '`http`',
    '`websocket`',
    '`browser`',
    '`turn`',
    'opaque Manager session',
    'CSRF',
    '`Origin`',
    'prepare_browser_input.py',
    '--use-break-glass-login',
    '--login-username-file',
    '--login-password-file',
    '/root/aileron-private/acceptance-inputs/<full SHA>/<deployment run ID>/browser-input.json',
    locale === 'zh-Hant' ? 'duplicate JSON key' : 'duplicate object key',
  ]) {
    if (!source.includes(requiredAcceptanceToken)) {
      throw new Error(
        `${locale}:installation/kubernetes.md is missing ${requiredAcceptanceToken}.`,
      );
    }
  }
  if (/acceptance_(?:bundle|evidence)\.py[\s\S]{0,220}--kubeconfig/.test(source)) {
    throw new Error(`${locale}:final acceptance commands expose --kubeconfig.`);
  }
  for (const unsupportedAcceptanceToken of [
    'smoke.sh',
    'smoke_kubeconfig.py',
    'AILERON_API_TOKEN',
  ]) {
    if (source.includes(unsupportedAcceptanceToken)) {
      throw new Error(
        `${locale}:installation/kubernetes.md exposes unsupported ${unsupportedAcceptanceToken}.`,
      );
    }
  }
  const shellBlocks = [...source.matchAll(/```(?:bash|sh)\n([\s\S]*?)```/g)].map(
    (match) => match[1],
  );
  const browserInputCommands = shellBlocks.filter((block) =>
    block.includes('prepare_browser_input.py'),
  );
  if (
    browserInputCommands.length !== 2
    || !browserInputCommands.some((block) => block.includes('--use-break-glass-login'))
    || !browserInputCommands.some(
      (block) => block.includes('--login-username-file')
        && block.includes('--login-password-file'),
    )
  ) {
    throw new Error(`${locale}:browser-input source modes are incomplete.`);
  }
}

for (const [locale, root] of localeRoots) {
  const source = await readFile(path.join(root, 'installation/troubleshooting.md'), 'utf8');
  for (const requiredTurnDiagnosticToken of [
    'docker compose ps turn-readiness-preflight coturn',
    'connectivity-evidence-gateway connectivity-external-agent workspace-manager',
    'docker compose logs --tail=200 turn-readiness-preflight',
    'workspace-browser-connectivity-probe-<workspace-id>',
    '${HOST_TURN_CONFIG_DIR}/turn-reachability-profile.json',
    '${HOST_TURN_SECRETS_DIR}',
    '${TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT:-18083}',
    'TURN_CREDENTIAL_REVISION',
    'browser_connectivity_state',
    'browser_connectivity_reason',
    'browser_connectivity_backend_*',
    'browser_connectivity_frontend_*',
  ]) {
    if (!source.includes(requiredTurnDiagnosticToken)) {
      throw new Error(
        `${locale}:installation/troubleshooting.md is missing ${requiredTurnDiagnosticToken}.`,
      );
    }
  }
}

process.stdout.write(
  `Documentation structure is consistent across ${zhHantDocuments.length} localized pages.\n`,
);
