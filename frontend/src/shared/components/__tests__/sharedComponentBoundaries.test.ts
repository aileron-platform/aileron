import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const repoRoot = process.cwd();
const srcRoot = path.join(repoRoot, 'src');
const sharedComponentsRoot = path.join(srcRoot, 'shared/components');
const featureRoots = [
  path.join(srcRoot, 'app'),
  path.join(srcRoot, 'features'),
  path.join(srcRoot, 'pages'),
];

const sourceExtensions = new Set(['.ts', '.tsx']);
const testPattern = /(?:^|[/.])(?:__tests__|.+\.(?:test|spec)\.[^.]+$)/;

const collectSourceFiles = (root: string): string[] => {
  if (!fs.existsSync(root)) {
    return [];
  }

  const entries = fs.readdirSync(root, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      return collectSourceFiles(fullPath);
    }
    if (!sourceExtensions.has(path.extname(entry.name))) {
      return [];
    }
    return [fullPath];
  });
};

const readFiles = (files: string[]) =>
  files.map((filePath) => ({
    filePath,
    relativePath: path.relative(repoRoot, filePath),
    content: fs.readFileSync(filePath, 'utf8'),
  }));

describe('shared component boundaries', () => {
  it('does not import removed shared component paths', () => {
    const removedPathPattern =
      /@\/shared\/components\/(?:composite|dialogs|slash-commands|command-picker|i18n\/LanguageSelector|layout\/GlobalStatusBar|navigation\/CompactHeader|file-workbench\/services)/;

    const offenders = readFiles(collectSourceFiles(srcRoot))
      .filter(({ content }) => removedPathPattern.test(content))
      .map(({ relativePath }) => relativePath);

    expect(offenders).toEqual([]);
  });

  it('keeps production shared components independent from feature modules', () => {
    const offenders = readFiles(collectSourceFiles(sharedComponentsRoot))
      .filter(({ relativePath }) => !testPattern.test(relativePath))
      .filter(({ content }) => /@\/features\//.test(content))
      .map(({ relativePath }) => relativePath);

    expect(offenders).toEqual([]);
  });

  it('keeps feature code on the public file-workbench barrel', () => {
    const internalFileWorkbenchPattern =
      /@\/shared\/components\/file-workbench\/(?:adapters|hooks|layouts|primitives|services|tree|utils|viewer)/;

    const offenders = readFiles(featureRoots.flatMap(collectSourceFiles))
      .filter(({ relativePath }) => !testPattern.test(relativePath))
      .filter(({ content }) => internalFileWorkbenchPattern.test(content))
      .map(({ relativePath }) => relativePath);

    expect(offenders).toEqual([]);
  });

  it('keeps extracted shared cores free of legacy dialog and union variant contracts', () => {
    const sharedCoreFiles = [
      path.join(sharedComponentsRoot, 'document-workflow'),
      path.join(sharedComponentsRoot, 'hook-workflow'),
      path.join(sharedComponentsRoot, 'mcp-workflow'),
    ].flatMap(collectSourceFiles);

    const forbiddenPattern = /@\/features\/|@\/shared\/components\/dialogs|variant:\s*['"](workspace|template|claude-code)['"]/;
    const offenders = readFiles(sharedCoreFiles)
      .filter(({ relativePath }) => !testPattern.test(relativePath))
      .filter(({ content }) => forbiddenPattern.test(content))
      .map(({ relativePath }) => relativePath);

    expect(offenders).toEqual([]);
  });
});
