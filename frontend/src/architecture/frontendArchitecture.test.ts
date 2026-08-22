import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

const SOURCE_ROOT = path.resolve(__dirname, '..');
const APP_ROOT = path.join(SOURCE_ROOT, 'app');
const FEATURES_ROOT = path.join(SOURCE_ROOT, 'features');
const PAGES_ROOT = path.join(SOURCE_ROOT, 'pages');
const SHARED_ROOT = path.join(SOURCE_ROOT, 'shared');
const SHARED_COMPONENTS_ROOT = path.join(SHARED_ROOT, 'components');
const SHARED_SHELL_ROOT = path.join(SHARED_COMPONENTS_ROOT, 'shell');
const PRODUCT_SHELL_ENTRY = path.join(SHARED_SHELL_ROOT, 'ProductShell.tsx');
const SHELL_LAYOUT_STORAGE_ENTRY = path.join(SHARED_ROOT, 'storage', 'shellLayoutStorage.ts');
const WORKSPACE_ROOT = path.join(FEATURES_ROOT, 'workspace');
const WORKSPACE_FEATURES_ROOT = path.join(WORKSPACE_ROOT, 'features');
const WORKSPACE_REALTIME_ROOT = path.join(WORKSPACE_ROOT, 'realtime');
const WORKSPACE_SHELL_SURFACE_MODEL = path.join(
  WORKSPACE_ROOT,
  'layout',
  'workspaceShellSurfaceModel.ts',
);
const AI_CHAT_ROOT = path.join(FEATURES_ROOT, 'ai-chat');
const KNOWLEDGE_BASE_ROOT = path.join(FEATURES_ROOT, 'knowledge-base');
const MARKETPLACE_ROOT = path.join(FEATURES_ROOT, 'marketplace');
const USER_MANAGEMENT_ROOT = path.join(FEATURES_ROOT, 'user-management');
const MARKETPLACE_FEATURES_ROOT = path.join(MARKETPLACE_ROOT, 'features');
const MARKETPLACE_DETAIL_ROOT = path.join(
  MARKETPLACE_FEATURES_ROOT,
  'marketplace-detail',
);
const MARKETPLACE_EDITOR_ROOT = path.join(
  MARKETPLACE_FEATURES_ROOT,
  'marketplace-editor',
);
const FILE_WORKBENCH_ROOT = path.join(SHARED_COMPONENTS_ROOT, 'file-workbench');
const FILE_WORKBENCH_ENTRY = path.join(FILE_WORKBENCH_ROOT, 'index.ts');
const FILE_WORKBENCH_VIEWER_ENTRY = path.join(FILE_WORKBENCH_ROOT, 'viewer-entry.ts');
const FILE_WORKBENCH_VIEWER_ROOT = path.join(FILE_WORKBENCH_ROOT, 'viewer');
const RESOURCE_WORKFLOW_ROOT = path.join(SHARED_COMPONENTS_ROOT, 'resource-workflow');
const DOCUMENT_RESOURCE_ROOT = path.join(SHARED_COMPONENTS_ROOT, 'document-resource');
const DOCUMENT_RESOURCE_MODEL_ROOT = path.join(DOCUMENT_RESOURCE_ROOT, 'model');
const DOCUMENT_RESOURCE_CONTRACT = path.join(
  DOCUMENT_RESOURCE_MODEL_ROOT,
  'documentResourceTypes.ts',
);
const DOCUMENT_RESOURCE_PARSER = path.join(DOCUMENT_RESOURCE_ROOT, 'resourceEnvelope.ts');
const HOOK_WORKFLOW_ROOT = path.join(SHARED_COMPONENTS_ROOT, 'hook-workflow');
const HOOK_WORKFLOW_MODEL_ROOT = path.join(HOOK_WORKFLOW_ROOT, 'model');
const MARKDOWN_SYNTAX_HIGHLIGHTER = path.join(
  SHARED_COMPONENTS_ROOT,
  'markdown/markdownSyntaxHighlighter.tsx',
);

const APPROVED_PUBLIC_SHARED_PACKAGE_NAMES = [
  'document-resource',
  'document-workflow',
  'file-workbench',
  'hook-workflow',
  'mcp-workflow',
  'resource-workflow',
  'settings-workflow',
  'shell',
  'prompt-invocation-picker',
  'split-pane',
  'version-control',
] as const;
const PUBLIC_SHARED_PACKAGE_NAMES = new Set<string>(
  APPROVED_PUBLIC_SHARED_PACKAGE_NAMES,
);

const MARKDOWN_LAZY_MODULE_SPECIFIERS = [
  'react-syntax-highlighter',
  'react-syntax-highlighter/dist/esm/styles/prism',
] as const;

interface Dependency {
  sourceFile: string;
  targetPath: string | null;
  moduleSpecifier: string;
  syntax:
    | 'dynamic import'
    | 'export'
    | 'export type'
    | 'import'
    | 'import type'
    | 'require';
}

interface DependencyGraph {
  sourceRoot: string;
  sourceFiles: string[];
  dependencies: Dependency[];
  runtimeAdjacency: Map<string, Set<string>>;
}

const collectTypeScriptFiles = (directory: string): string[] =>
  fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return collectTypeScriptFiles(absolutePath);
    }

    return entry.isFile() && /\.(?:ts|tsx)$/.test(entry.name)
      ? [absolutePath]
      : [];
  });

const isTestSourceFile = (filePath: string): boolean =>
  path
    .relative(SOURCE_ROOT, filePath)
    .split(path.sep)
    .includes('__tests__') ||
  /\.(?:test|spec)\.(?:ts|tsx)$/.test(path.basename(filePath));

const isPathWithin = (candidate: string, directory: string): boolean => {
  const relativePath = path.relative(directory, candidate);
  return (
    relativePath === '' ||
    (!relativePath.startsWith(`..${path.sep}`) &&
      relativePath !== '..' &&
      !path.isAbsolute(relativePath))
  );
};

const stripTypeScriptExtension = (filePath: string): string =>
  filePath.replace(/\.(?:d\.)?(?:ts|tsx)$/, '');

const getTopLevelFeatureName = (
  filePath: string,
  featuresRoot: string,
): string | null => {
  if (!isPathWithin(filePath, featuresRoot)) {
    return null;
  }

  const [featureName] = path.relative(featuresRoot, filePath).split(path.sep);
  return featureName || null;
};

const isTopLevelFeaturePublicTarget = (
  targetPath: string,
  featuresRoot: string,
): boolean => {
  const featureName = getTopLevelFeatureName(targetPath, featuresRoot);
  return Boolean(
    featureName &&
      stripTypeScriptExtension(targetPath) ===
        path.join(featuresRoot, featureName, 'public'),
  );
};

const findExternalFeaturePublicApiOffenders = (
  candidateDependencies: readonly Dependency[],
  featuresRoot: string,
): Dependency[] =>
  candidateDependencies.filter((dependency) => {
    if (dependency.targetPath === null) {
      return false;
    }

    const sourceFeatureName = getTopLevelFeatureName(
      dependency.sourceFile,
      featuresRoot,
    );
    const targetFeatureName = getTopLevelFeatureName(
      dependency.targetPath,
      featuresRoot,
    );
    return Boolean(
      targetFeatureName &&
        sourceFeatureName !== targetFeatureName &&
        !isTopLevelFeaturePublicTarget(dependency.targetPath, featuresRoot),
    );
  });

const findFeatureAppDependencyOffenders = (
  candidateDependencies: readonly Dependency[],
  featuresRoot: string,
  appRoot: string,
): Dependency[] =>
  candidateDependencies.filter(
    (dependency) =>
      isPathWithin(dependency.sourceFile, featuresRoot) &&
      dependency.targetPath !== null &&
      isPathWithin(dependency.targetPath, appRoot),
  );

const listTopLevelFeatureDirectories = (featuresRoot: string): string[] =>
  fs.readdirSync(featuresRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(featuresRoot, entry.name))
    .sort();

const listNestedFeatureRoots = (
  topLevelFeatureDirectories: readonly string[],
): string[] =>
  topLevelFeatureDirectories
    .map((directory) => path.join(directory, 'features'))
    .filter((directory) => fs.existsSync(directory));

const findFeatureEntryConventionOffenders = (
  candidateSourceFiles: readonly string[],
  topLevelFeatureDirectories: readonly string[],
  featuresRoot: string,
): string[] => {
  const normalizedSourceFiles = new Set(
    candidateSourceFiles.map((sourceFile) => path.normalize(sourceFile)),
  );
  const expectedPublicEntries = new Set(
    topLevelFeatureDirectories.map((directory) =>
      path.normalize(path.join(directory, 'public.ts')),
    ),
  );
  const missingPublicEntries = [...expectedPublicEntries].filter(
    (publicEntry) => !normalizedSourceFiles.has(publicEntry),
  );
  const rootFiles = candidateSourceFiles.filter(
    (sourceFile) => path.dirname(sourceFile) === path.normalize(featuresRoot),
  );
  const misplacedEntries = candidateSourceFiles.filter((sourceFile) => {
    if (
      !topLevelFeatureDirectories.some((directory) =>
        isPathWithin(sourceFile, directory),
      )
    ) {
      return false;
    }

    const basename = path.basename(sourceFile);
    return (
      /^index\.tsx?$/.test(basename) ||
      (/^public\.tsx?$/.test(basename) &&
        !expectedPublicEntries.has(path.normalize(sourceFile)))
    );
  });

  return [...missingPublicEntries, ...rootFiles, ...misplacedEntries].sort();
};

const findNestedFeatureSiblingOffenders = (
  candidateDependencies: readonly Dependency[],
  nestedFeatureRoots: readonly string[],
): Dependency[] =>
  candidateDependencies.filter((dependency) => {
    if (dependency.targetPath === null) {
      return false;
    }

    return nestedFeatureRoots.some((nestedFeaturesRoot) => {
      const sourceFeature = getTopLevelFeatureName(
        dependency.sourceFile,
        nestedFeaturesRoot,
      );
      const targetFeature = getTopLevelFeatureName(
        dependency.targetPath,
        nestedFeaturesRoot,
      );
      return Boolean(
        sourceFeature &&
          targetFeature &&
          sourceFeature !== targetFeature,
      );
    });
  });

const isKebabCaseFeatureDirectoryName = (directoryName: string): boolean =>
  /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(directoryName);

const collectDirectFeatureDirectories = (directory: string): string[] => {
  const childDirectories = fs
    .readdirSync(directory, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(directory, entry.name));

  return [
    ...(path.basename(directory) === 'features' ? childDirectories : []),
    ...childDirectories.flatMap(collectDirectFeatureDirectories),
  ];
};

const findInvalidFeatureDirectoryNames = (
  featureDirectories: readonly string[],
): string[] =>
  featureDirectories.filter(
    (directory) =>
      !isKebabCaseFeatureDirectoryName(path.basename(directory)),
  );

const findHyphenatedFeatureProductionFiles = (
  candidateSourceFiles: readonly string[],
  featuresRoot: string,
): string[] =>
  candidateSourceFiles.filter(
    (sourceFile) =>
      isPathWithin(sourceFile, featuresRoot) &&
      path.basename(stripTypeScriptExtension(sourceFile)).includes('-'),
  );

const GENERIC_FEATURE_ROOT_FILE_NAMES = new Set([
  'constants.ts',
  'constants.tsx',
  'types.ts',
  'types.tsx',
  'utils.ts',
  'utils.tsx',
]);

const findGenericFeatureRootFiles = (
  candidateSourceFiles: readonly string[],
  featureRoot: string,
): string[] =>
  candidateSourceFiles.filter(
    (sourceFile) =>
      path.dirname(sourceFile) === featureRoot &&
      GENERIC_FEATURE_ROOT_FILE_NAMES.has(path.basename(sourceFile)),
  );

const getLocalModuleBasePath = (
  sourceFile: string,
  moduleSpecifier: string,
  sourceRoot: string,
): string | null => {
  if (moduleSpecifier.startsWith('@/')) {
    return path.resolve(sourceRoot, moduleSpecifier.slice(2));
  }

  if (moduleSpecifier.startsWith('src/')) {
    return path.resolve(sourceRoot, moduleSpecifier.slice(4));
  }

  if (moduleSpecifier.startsWith('.')) {
    return path.resolve(path.dirname(sourceFile), moduleSpecifier);
  }

  return null;
};

const resolveDependencyFilePath = (
  sourceFile: string,
  moduleSpecifier: string,
  sourceRoot: string,
  availableFiles: ReadonlySet<string>,
): string | null => {
  const basePath = getLocalModuleBasePath(
    sourceFile,
    moduleSpecifier,
    sourceRoot,
  );
  if (basePath === null) {
    return null;
  }

  const candidates = [
    basePath,
    `${basePath}.ts`,
    `${basePath}.tsx`,
    path.join(basePath, 'index.ts'),
    path.join(basePath, 'index.tsx'),
  ];
  return (
    candidates.find((candidate) => availableFiles.has(path.normalize(candidate))) ??
    basePath
  );
};

const getStringArgument = (node: ts.CallExpression): string | null => {
  const [argument] = node.arguments;
  return argument && ts.isStringLiteralLike(argument) ? argument.text : null;
};

const isTypeOnlyImportDeclaration = (
  node: ts.ImportDeclaration,
): boolean => {
  const importClause = node.importClause;
  if (!importClause) {
    return false;
  }
  if (importClause.isTypeOnly) {
    return true;
  }
  if (importClause.name) {
    return false;
  }

  const namedBindings = importClause.namedBindings;
  return Boolean(
    namedBindings &&
      ts.isNamedImports(namedBindings) &&
      namedBindings.elements.length > 0 &&
      namedBindings.elements.every((element) => element.isTypeOnly),
  );
};

const isTypeOnlyExportDeclaration = (
  node: ts.ExportDeclaration,
): boolean =>
  node.isTypeOnly ||
  Boolean(
    node.exportClause &&
      ts.isNamedExports(node.exportClause) &&
      node.exportClause.elements.length > 0 &&
      node.exportClause.elements.every((element) => element.isTypeOnly),
  );

const collectDependenciesFromSource = (
  sourceFilePath: string,
  sourceText: string,
  sourceRoot: string,
  availableFiles: ReadonlySet<string>,
): Dependency[] => {
  const sourceFile = ts.createSourceFile(
    sourceFilePath,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    sourceFilePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const dependencies: Dependency[] = [];

  const addDependency = (
    moduleSpecifier: string,
    syntax: Dependency['syntax'],
  ): void => {
    dependencies.push({
      sourceFile: sourceFilePath,
      targetPath: resolveDependencyFilePath(
        sourceFilePath,
        moduleSpecifier,
        sourceRoot,
        availableFiles,
      ),
      moduleSpecifier,
      syntax,
    });
  };

  const visit = (node: ts.Node): void => {
    if (
      ts.isImportDeclaration(node) &&
      ts.isStringLiteralLike(node.moduleSpecifier)
    ) {
      addDependency(
        node.moduleSpecifier.text,
        isTypeOnlyImportDeclaration(node) ? 'import type' : 'import',
      );
    } else if (
      ts.isExportDeclaration(node) &&
      node.moduleSpecifier &&
      ts.isStringLiteralLike(node.moduleSpecifier)
    ) {
      addDependency(
        node.moduleSpecifier.text,
        isTypeOnlyExportDeclaration(node) ? 'export type' : 'export',
      );
    } else if (ts.isImportEqualsDeclaration(node)) {
      const moduleReference = node.moduleReference;
      if (
        ts.isExternalModuleReference(moduleReference) &&
        moduleReference.expression &&
        ts.isStringLiteralLike(moduleReference.expression)
      ) {
        addDependency(
          moduleReference.expression.text,
          node.isTypeOnly ? 'import type' : 'import',
        );
      }
    } else if (
      ts.isImportTypeNode(node) &&
      ts.isLiteralTypeNode(node.argument) &&
      ts.isStringLiteralLike(node.argument.literal)
    ) {
      addDependency(node.argument.literal.text, 'import type');
    } else if (ts.isCallExpression(node)) {
      if (node.expression.kind === ts.SyntaxKind.ImportKeyword) {
        const moduleSpecifier = getStringArgument(node);
        if (moduleSpecifier) {
          addDependency(moduleSpecifier, 'dynamic import');
        }
      } else if (
        ts.isIdentifier(node.expression) &&
        node.expression.text === 'require'
      ) {
        const moduleSpecifier = getStringArgument(node);
        if (moduleSpecifier) {
          addDependency(moduleSpecifier, 'require');
        }
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(sourceFile);
  return dependencies;
};

const collectDependencies = (
  sourceFilePath: string,
  sourceRoot: string,
  availableFiles: ReadonlySet<string>,
): Dependency[] =>
  collectDependenciesFromSource(
    sourceFilePath,
    fs.readFileSync(sourceFilePath, 'utf8'),
    sourceRoot,
    availableFiles,
  );

const isRuntimeDependency = ({ syntax }: Dependency): boolean =>
  syntax !== 'import type' && syntax !== 'export type';

const buildRuntimeFileAdjacency = (
  sourceFiles: readonly string[],
  dependencies: readonly Dependency[],
): Map<string, Set<string>> => {
  const sourceFileSet = new Set(sourceFiles);
  const adjacency = new Map(
    sourceFiles.map((sourceFile) => [sourceFile, new Set<string>()]),
  );

  dependencies.forEach((dependency) => {
    if (
      isRuntimeDependency(dependency) &&
      dependency.targetPath !== null &&
      sourceFileSet.has(dependency.targetPath)
    ) {
      adjacency
        .get(dependency.sourceFile)
        ?.add(dependency.targetPath);
    }
  });

  return adjacency;
};

const createVirtualDependencyGraph = (
  modules: Record<string, string>,
): DependencyGraph => {
  const sourceRoot = path.resolve('/virtual/frontend/src');
  const sourceFiles = Object.keys(modules).map((relativePath) =>
    path.join(sourceRoot, relativePath),
  );
  const availableFiles = new Set(sourceFiles);
  const dependencies = Object.entries(modules).flatMap(
    ([relativePath, sourceText]) =>
      collectDependenciesFromSource(
        path.join(sourceRoot, relativePath),
        sourceText,
        sourceRoot,
        availableFiles,
      ),
  );

  return {
    sourceRoot,
    sourceFiles,
    dependencies,
    runtimeAdjacency: buildRuntimeFileAdjacency(sourceFiles, dependencies),
  };
};

const sourceFiles = collectTypeScriptFiles(SOURCE_ROOT);
const sourceFileSet = new Set(sourceFiles);
const dependencies = sourceFiles.flatMap((sourceFile) =>
  collectDependencies(sourceFile, SOURCE_ROOT, sourceFileSet),
);
const productionSourceFiles = sourceFiles.filter(
  (sourceFile) => !isTestSourceFile(sourceFile),
);
const productionSourceFileSet = new Set(productionSourceFiles);
const productionDependencies = dependencies.filter(({ sourceFile }) =>
  productionSourceFileSet.has(sourceFile),
);
const productionRuntimeAdjacency = buildRuntimeFileAdjacency(
  productionSourceFiles,
  productionDependencies,
);

const getSharedPackageName = (
  filePath: string,
  sharedComponentsRoot: string,
): string | null => {
  if (!isPathWithin(filePath, sharedComponentsRoot)) {
    return null;
  }

  const [packageName] = path
    .relative(sharedComponentsRoot, filePath)
    .split(path.sep);
  return packageName || null;
};

const getPublicSharedPackageName = (
  targetPath: string | null,
  sharedComponentsRoot: string,
): string | null => {
  if (targetPath === null) {
    return null;
  }

  const packageName = getSharedPackageName(
    targetPath,
    sharedComponentsRoot,
  );
  return packageName && PUBLIC_SHARED_PACKAGE_NAMES.has(packageName)
    ? packageName
    : null;
};

const listSharedComponentPackageEntries = (
  sharedComponentsRoot: string,
): string[] =>
  fs.readdirSync(sharedComponentsRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .filter((entry) =>
      ['index.ts', 'index.tsx'].some((entryFile) =>
        fs.existsSync(path.join(sharedComponentsRoot, entry.name, entryFile)),
      ),
    )
    .map((entry) => entry.name)
    .sort();

const isAllowedSharedPublicEntry = (
  moduleSpecifier: string,
  packageName: string,
): boolean =>
  moduleSpecifier === `@/shared/components/${packageName}` ||
  (packageName === 'file-workbench' &&
    moduleSpecifier === '@/shared/components/file-workbench/viewer-entry');

const findExternalSharedPackageEntryOffenders = (
  candidateDependencies: readonly Dependency[],
  sharedComponentsRoot: string,
): Dependency[] =>
  candidateDependencies.filter((dependency) => {
    const packageName = getPublicSharedPackageName(
      dependency.targetPath,
      sharedComponentsRoot,
    );
    if (!packageName) {
      return false;
    }

    const packageRoot = path.join(sharedComponentsRoot, packageName);
    return (
      !isPathWithin(dependency.sourceFile, packageRoot) &&
      !isAllowedSharedPublicEntry(dependency.moduleSpecifier, packageName)
    );
  });

const findSharedPackageInternalAliasOffenders = (
  candidateDependencies: readonly Dependency[],
  sharedComponentsRoot: string,
): Dependency[] =>
  candidateDependencies.filter((dependency) => {
    const packageName = getPublicSharedPackageName(
      dependency.targetPath,
      sharedComponentsRoot,
    );
    if (!packageName) {
      return false;
    }

    const packageRoot = path.join(sharedComponentsRoot, packageName);
    return (
      isPathWithin(dependency.sourceFile, packageRoot) &&
      !dependency.moduleSpecifier.startsWith('.')
    );
  });

const findReachableFiles = (
  entryFile: string,
  adjacency: ReadonlyMap<string, ReadonlySet<string>>,
): Set<string> => {
  const reachableFiles = new Set<string>();
  const pendingFiles = [...(adjacency.get(entryFile) ?? [])];

  while (pendingFiles.length > 0) {
    const currentFile = pendingFiles.pop();
    if (!currentFile || reachableFiles.has(currentFile)) {
      continue;
    }

    reachableFiles.add(currentFile);
    pendingFiles.push(...(adjacency.get(currentFile) ?? []));
  }

  return reachableFiles;
};

const findViewerExposureOffenders = (
  candidateDependencies: readonly Dependency[],
  viewerRoot: string,
  viewerEntry: string,
): Dependency[] =>
  candidateDependencies.filter(
    (dependency) =>
      isRuntimeDependency(dependency) &&
      dependency.targetPath !== null &&
      isPathWithin(dependency.targetPath, viewerRoot) &&
      !isPathWithin(dependency.sourceFile, viewerRoot) &&
      dependency.sourceFile !== viewerEntry,
  );

const buildFirstLevelSharedPackageAdjacency = (
  candidateSourceFiles: readonly string[],
  candidateDependencies: readonly Dependency[],
  sharedComponentsRoot: string,
): Map<string, Set<string>> => {
  const sourceFileSet = new Set(candidateSourceFiles);
  const packageNames = new Set(
    candidateSourceFiles
      .map((sourceFile) =>
        getSharedPackageName(sourceFile, sharedComponentsRoot),
      )
      .filter((packageName): packageName is string => Boolean(packageName)),
  );
  const adjacency = new Map(
    [...packageNames].map((packageName) => [
      packageName,
      new Set<string>(),
    ]),
  );

  candidateDependencies.forEach((dependency) => {
    if (
      !isRuntimeDependency(dependency) ||
      dependency.targetPath === null ||
      !sourceFileSet.has(dependency.targetPath)
    ) {
      return;
    }

    const sourcePackage = getSharedPackageName(
      dependency.sourceFile,
      sharedComponentsRoot,
    );
    const targetPackage = getSharedPackageName(
      dependency.targetPath,
      sharedComponentsRoot,
    );
    if (
      sourcePackage &&
      targetPackage &&
      sourcePackage !== targetPackage
    ) {
      adjacency.get(sourcePackage)?.add(targetPackage);
    }
  });

  return adjacency;
};

const findDirectedCycles = (
  adjacency: ReadonlyMap<string, ReadonlySet<string>>,
): string[][] => {
  const visited = new Set<string>();
  const active = new Set<string>();
  const stack: string[] = [];
  const cycles: string[][] = [];

  const visit = (node: string): void => {
    visited.add(node);
    active.add(node);
    stack.push(node);

    [...(adjacency.get(node) ?? [])].sort().forEach((target) => {
      if (!visited.has(target)) {
        visit(target);
        return;
      }
      if (!active.has(target)) {
        return;
      }

      const cycleStart = stack.lastIndexOf(target);
      cycles.push([...stack.slice(cycleStart), target]);
    });

    stack.pop();
    active.delete(node);
  };

  [...adjacency.keys()].sort().forEach((node) => {
    if (!visited.has(node)) {
      visit(node);
    }
  });

  return cycles;
};

const findDocumentResourceDirectionOffenders = (
  candidateDependencies: readonly Dependency[],
  documentResourceRoot: string,
  modelRoot: string,
  contractFile: string,
  parserFile: string,
): Dependency[] =>
  candidateDependencies.filter((dependency) => {
    if (
      dependency.targetPath === null ||
      !isPathWithin(dependency.targetPath, documentResourceRoot)
    ) {
      return false;
    }

    if (
      isPathWithin(dependency.sourceFile, modelRoot) &&
      !isPathWithin(dependency.targetPath, modelRoot)
    ) {
      return true;
    }

    return (
      dependency.sourceFile === parserFile &&
      dependency.targetPath !== contractFile
    );
  });

const findHookWorkflowModelDirectionOffenders = (
  candidateDependencies: readonly Dependency[],
  hookWorkflowRoot: string,
  modelRoot: string,
): Dependency[] =>
  candidateDependencies.filter(
    (dependency) =>
      isPathWithin(dependency.sourceFile, modelRoot) &&
      dependency.targetPath !== null &&
      isPathWithin(dependency.targetPath, hookWorkflowRoot) &&
      !isPathWithin(dependency.targetPath, modelRoot),
  );

const inspectMarkdownLazyLoading = (
  candidateDependencies: readonly Dependency[],
  sourceFile: string,
): {
  invalidRuntimeDependencies: Dependency[];
  missingDynamicImports: string[];
} => {
  const relevantDependencies = candidateDependencies.filter(
    (dependency) =>
      dependency.sourceFile === sourceFile &&
      MARKDOWN_LAZY_MODULE_SPECIFIERS.some(
        (moduleSpecifier) =>
          dependency.moduleSpecifier === moduleSpecifier,
      ),
  );

  return {
    invalidRuntimeDependencies: relevantDependencies.filter(
      (dependency) =>
        isRuntimeDependency(dependency) &&
        dependency.syntax !== 'dynamic import',
    ),
    missingDynamicImports: MARKDOWN_LAZY_MODULE_SPECIFIERS.filter(
      (moduleSpecifier) =>
        !relevantDependencies.some(
          (dependency) =>
            dependency.moduleSpecifier === moduleSpecifier &&
            dependency.syntax === 'dynamic import',
        ),
    ),
  };
};

const formatDependencies = (
  offenders: readonly Dependency[],
  sourceRoot = SOURCE_ROOT,
): string[] =>
  offenders.map(
    ({ sourceFile, moduleSpecifier, syntax }) =>
      `${path.relative(sourceRoot, sourceFile)}: ${syntax} "${moduleSpecifier}"`,
  );

const findDependencyOffenders = (
  predicate: (dependency: Dependency) => boolean,
): string[] => formatDependencies(dependencies.filter(predicate));

const findProductShellImportOffenders = (): string[] => {
  const allowedImporters = new Set([
    path.join(FEATURES_ROOT, 'workspace', 'layout', 'WorkspaceShellAdapter.tsx'),
    path.join(FEATURES_ROOT, 'knowledge-base', 'components', 'KnowledgeBaseShellAdapter.tsx'),
    path.join(FEATURES_ROOT, 'marketplace', 'components', 'MarketplaceShellAdapter.tsx'),
    path.join(FEATURES_ROOT, 'user-management', 'components', 'UserManagementShell.tsx'),
    path.join(FEATURES_ROOT, 'platform-resources', 'PlatformResourcesModule.tsx'),
  ]);

  const directOffenders = formatDependencies(
    productionDependencies.filter(
      (dependency) => dependency.targetPath === PRODUCT_SHELL_ENTRY
        && dependency.sourceFile !== path.join(SHARED_SHELL_ROOT, 'index.ts')
        && !allowedImporters.has(dependency.sourceFile),
    ),
  );
  const barrelOffenders = productionSourceFiles
    .filter((sourceFile) => !allowedImporters.has(sourceFile))
    .filter((sourceFile) => {
      const sourceText = fs.readFileSync(sourceFile, 'utf8');
      return /import\s+\{[^}]*\bProductShell\b[^}]*\}\s+from\s+['"]@\/shared\/components\/shell['"]/.test(sourceText);
    })
    .map((sourceFile) => `${path.relative(SOURCE_ROOT, sourceFile)}: import "ProductShell" from "@/shared/components/shell"`);

  return [...directOffenders, ...barrelOffenders];
};

const findShellLayoutStorageImportOffenders = (): string[] => {
  const allowedImporters = new Set([
    path.join(FEATURES_ROOT, 'workspace', 'storage', 'workspaceShellLayoutStorage.ts'),
    path.join(FEATURES_ROOT, 'user-management', 'storage', 'userManagementShellLayoutStorage.ts'),
  ]);

  return formatDependencies(
    productionDependencies.filter(
      (dependency) => dependency.targetPath === SHELL_LAYOUT_STORAGE_ENTRY
        && !allowedImporters.has(dependency.sourceFile),
    ),
  );
};

const findWorkspaceSurfaceModelSharedShellDependencies = (): string[] => formatDependencies(
  productionDependencies.filter(
    (dependency) => dependency.sourceFile === WORKSPACE_SHELL_SURFACE_MODEL
      && dependency.targetPath !== null
      && isPathWithin(dependency.targetPath, SHARED_SHELL_ROOT),
  ),
);

describe('frontend architecture boundaries', () => {
  it('restricts ProductShell imports to the explicit shell adapters', () => {
    expect(findProductShellImportOffenders()).toEqual([]);
  });

  it('keeps workspace surface decisions below the ProductShell composition boundary', () => {
    expect(findWorkspaceSurfaceModelSharedShellDependencies()).toEqual([]);
  });

  it('keeps the raw shell layout storage helper behind workspace and user-management storage modules', () => {
    expect(findShellLayoutStorageImportOffenders()).toEqual([]);
  });

  it('keeps external consumers on target feature public APIs', () => {
    const offenders = findExternalFeaturePublicApiOffenders(
      productionDependencies,
      FEATURES_ROOT,
    );

    expect(formatDependencies(offenders)).toEqual([]);
  });

  it('keeps direct child feature directories kebab-case', () => {
    const offenders = findInvalidFeatureDirectoryNames(
      collectDirectFeatureDirectories(FEATURES_ROOT),
    )
      .map((directory) => path.relative(SOURCE_ROOT, directory))
      .sort();

    expect(offenders).toEqual([]);
  });

  it('keeps production feature file basenames free of hyphens', () => {
    const offenders = findHyphenatedFeatureProductionFiles(
      productionSourceFiles,
      FEATURES_ROOT,
    )
      .map((sourceFile) => path.relative(SOURCE_ROOT, sourceFile))
      .sort();

    expect(offenders).toEqual([]);
  });

  it('keeps features independent from app', () => {
    const offenders = findFeatureAppDependencyOffenders(
      productionDependencies,
      FEATURES_ROOT,
      APP_ROOT,
    );

    expect(formatDependencies(offenders)).toEqual([]);
  });

  it('keeps feature public APIs at roots without index barrels', () => {
    const topLevelFeatureDirectories =
      listTopLevelFeatureDirectories(FEATURES_ROOT);
    const offenders = findFeatureEntryConventionOffenders(
      productionSourceFiles,
      topLevelFeatureDirectories,
      FEATURES_ROOT,
    ).map((sourceFile) => path.relative(SOURCE_ROOT, sourceFile));

    expect(offenders).toEqual([]);
  });

  it('keeps nested features private from sibling features', () => {
    const topLevelFeatureDirectories =
      listTopLevelFeatureDirectories(FEATURES_ROOT);
    const offenders = findNestedFeatureSiblingOffenders(
      productionDependencies,
      listNestedFeatureRoots(topLevelFeatureDirectories),
    );

    expect(formatDependencies(offenders)).toEqual([]);
  });

  it('keeps ai-chat independent from workspace', () => {
    const offenders = findDependencyOffenders(
      ({ sourceFile, targetPath }) =>
        isPathWithin(sourceFile, AI_CHAT_ROOT) &&
        targetPath !== null &&
        isPathWithin(targetPath, WORKSPACE_ROOT),
    );

    expect(offenders).toEqual([]);
  });

  it('keeps ai-chat root ownership explicit and its route entry named as a page', () => {
    const genericRootFiles = findGenericFeatureRootFiles(
      productionSourceFiles,
      AI_CHAT_ROOT,
    ).map((sourceFile) => path.relative(SOURCE_ROOT, sourceFile));

    expect(genericRootFiles).toEqual([]);
    expect(fs.existsSync(path.join(AI_CHAT_ROOT, 'AiChatPage.tsx'))).toBe(true);
    expect(fs.existsSync(path.join(AI_CHAT_ROOT, 'AiChatHomeFeature.tsx'))).toBe(false);
  });

  it('keeps ai-chat pure models outside component folders', () => {
    expect(fs.existsSync(path.join(AI_CHAT_ROOT, 'components/threadErrorNoticeModel.ts'))).toBe(false);
    expect(fs.existsSync(path.join(AI_CHAT_ROOT, 'components/messages/questionForm.ts'))).toBe(false);
    expect(fs.existsSync(path.join(AI_CHAT_ROOT, 'model/threadErrorNoticeModel.ts'))).toBe(true);
    expect(fs.existsSync(path.join(AI_CHAT_ROOT, 'model/questionFormModel.ts'))).toBe(true);
  });

  it('keeps knowledge-base adapters and models outside component folders and version control shared', () => {
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'components/file-workbench/knowledgeBaseFileTreeDataAdapter.ts'))).toBe(false);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'components/file-workbench/knowledgeBaseFileWorkbenchAdapter.ts'))).toBe(false);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'components/knowledgeBaseShellModel.ts'))).toBe(false);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'components/knowledgeBaseVersionControlRefresh.ts'))).toBe(false);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'adapters/file-workbench/knowledgeBaseFileTreeDataAdapter.ts'))).toBe(true);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'adapters/file-workbench/knowledgeBaseFileWorkbenchAdapter.ts'))).toBe(true);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'model/knowledgeBaseFileModel.ts'))).toBe(true);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'model/knowledgeBaseShellModel.ts'))).toBe(true);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'api/knowledgeBaseVersionControlSnapshot.ts'))).toBe(false);
    expect(fs.existsSync(path.join(SHARED_ROOT, 'version-control/versionControlSession.ts'))).toBe(true);
    expect(fs.existsSync(path.join(SHARED_ROOT, 'version-control/versionControlSessionCore.ts'))).toBe(true);
    expect(fs.existsSync(path.join(SHARED_ROOT, 'version-control/versionControlChangesCapability.ts'))).toBe(true);
    expect(fs.existsSync(path.join(SHARED_ROOT, 'version-control/versionControlHistoryCapability.ts'))).toBe(true);
    expect(fs.existsSync(path.join(SHARED_ROOT, 'version-control/versionControlRemoteCapability.ts'))).toBe(true);
    expect(fs.existsSync(path.join(SHARED_ROOT, 'version-control/createVersionControlQueries.ts'))).toBe(false);
    expect(fs.existsSync(path.join(SHARED_ROOT, 'version-control/keys.ts'))).toBe(false);
    expect(fs.existsSync(path.join(SHARED_ROOT, 'version-control/fetcher.ts'))).toBe(false);
  });

  it('names the knowledge-base workspaces route component after its visible feature', () => {
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'components/KnowledgeBaseAttachmentsTab.tsx'))).toBe(false);
    expect(fs.existsSync(path.join(KNOWLEDGE_BASE_ROOT, 'components/KnowledgeBaseWorkspacesTab.tsx'))).toBe(true);
  });

  it('names Marketplace route-visible components as pages', () => {
    const routeComponentPaths = [
      ['marketplace-center', 'MarketplaceCenter'],
      ['marketplace-detail', 'MarketplaceDetail'],
      ['marketplace-editor', 'MarketplaceEditor'],
      ['marketplace-settings', 'MarketplaceSettings'],
    ] as const;

    routeComponentPaths.forEach(([featureName, componentName]) => {
      const featureRoot = path.join(MARKETPLACE_ROOT, 'features', featureName);
      expect(fs.existsSync(path.join(featureRoot, `${componentName}Page.tsx`))).toBe(true);
      expect(fs.existsSync(path.join(featureRoot, `${componentName}View.tsx`))).toBe(false);
    });
  });

  it('keeps User Management root ownership explicit and its route entry named as a page', () => {
    const genericRootFiles = findGenericFeatureRootFiles(
      productionSourceFiles,
      USER_MANAGEMENT_ROOT,
    ).map((sourceFile) => path.relative(SOURCE_ROOT, sourceFile));

    expect(genericRootFiles).toEqual([]);
    expect(fs.existsSync(path.join(USER_MANAGEMENT_ROOT, 'UserManagementPage.tsx'))).toBe(true);
    expect(fs.existsSync(path.join(USER_MANAGEMENT_ROOT, 'UserManagementView.tsx'))).toBe(false);
    expect(
      fs.existsSync(
        path.join(
          USER_MANAGEMENT_ROOT,
          'model/userManagementUserModel.ts',
        ),
      ),
    ).toBe(true);
    expect(
      fs.existsSync(
        path.join(
          USER_MANAGEMENT_ROOT,
          'storage/userManagementShellLayoutStorage.ts',
        ),
      ),
    ).toBe(true);
    expect(
      fs.existsSync(
        path.join(
          USER_MANAGEMENT_ROOT,
          'utils/userManagementShellLayoutStorage.ts',
        ),
      ),
    ).toBe(false);
  });

  it('keeps Marketplace root ownership explicit', () => {
    expect(fs.existsSync(path.join(MARKETPLACE_ROOT, 'constants.ts'))).toBe(false);
  });

  it('keeps Marketplace private feature ownership explicit', () => {
    const detailComponentsRoot = path.join(
      MARKETPLACE_DETAIL_ROOT,
      'components',
    );
    const detailComponentNames = [
      'MarketplaceDetailActionDialogs',
      'MarketplaceDetailContentPanels',
      'MarketplaceDetailFilesSection',
      'MarketplaceDetailTopTabs',
      'MarketplaceInfoGridRow',
      'MarketplacePackageDetailHeader',
    ] as const;

    detailComponentNames.forEach((componentName) => {
      expect(
        fs.existsSync(path.join(detailComponentsRoot, `${componentName}.tsx`)),
      ).toBe(true);
    });
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_DETAIL_ROOT,
          'model/marketplaceDetailHookModel.ts',
        ),
      ),
    ).toBe(true);
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_DETAIL_ROOT,
          'model/marketplaceDetailNavigationModel.ts',
        ),
      ),
    ).toBe(true);
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_DETAIL_ROOT,
          'adapters/marketplaceReadonlyViewerAdapter.ts',
        ),
      ),
    ).toBe(true);
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_EDITOR_ROOT,
          'components/MarketplaceEditorHeader.tsx',
        ),
      ),
    ).toBe(true);
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_EDITOR_ROOT,
          'marketplaceFileResourceModel.ts',
        ),
      ),
    ).toBe(true);
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_EDITOR_ROOT,
          'marketplaceHookModel.ts',
        ),
      ),
    ).toBe(true);

    [
      'MarketplaceDetailActionDialogs',
      'MarketplaceDetailContentPanels',
      'MarketplaceDetailFeatureContentSection',
      'MarketplaceFilesSection',
      'MarketplaceDetailTopTabs',
      'MarketplaceInfoGridRow',
      'MarketplacePackageDetailHeader',
      'MarketplacePackageHeader',
    ].forEach((componentName) => {
      expect(
        fs.existsSync(
          path.join(MARKETPLACE_ROOT, 'components', `${componentName}.tsx`),
        ),
      ).toBe(false);
    });
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_ROOT,
          'components/marketplaceDetailHookModel.ts',
        ),
      ),
    ).toBe(false);
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_ROOT,
          'file-management/adapters/marketplaceViewerAdapters.ts',
        ),
      ),
    ).toBe(false);
    expect(
      fs.existsSync(
        path.join(
          MARKETPLACE_ROOT,
          'components/MarketplaceInstallOutput.tsx',
        ),
      ),
    ).toBe(true);
  });

  it('keeps Marketplace production runtime files acyclic', () => {
    const marketplaceSourceFiles = productionSourceFiles.filter((sourceFile) =>
      isPathWithin(sourceFile, MARKETPLACE_ROOT),
    );
    const adjacency = buildRuntimeFileAdjacency(
      marketplaceSourceFiles,
      productionDependencies,
    );
    const cycles = findDirectedCycles(adjacency).map((cycle) =>
      cycle
        .map((filePath) => path.relative(SOURCE_ROOT, filePath))
        .join(' -> '),
    );

    expect(cycles).toEqual([]);
  });

  it('keeps shared independent from app and features', () => {
    const offenders = findDependencyOffenders(
      ({ sourceFile, targetPath }) =>
        isPathWithin(sourceFile, SHARED_ROOT) &&
        targetPath !== null &&
        (isPathWithin(targetPath, APP_ROOT) ||
          isPathWithin(targetPath, FEATURES_ROOT)),
    );

    expect(offenders).toEqual([]);
  });

  it('keeps shared independent from pages', () => {
    const offenders = findDependencyOffenders(
      ({ sourceFile, targetPath }) =>
        isPathWithin(sourceFile, SHARED_ROOT) &&
        targetPath !== null &&
        isPathWithin(targetPath, PAGES_ROOT),
    );

    expect(offenders).toEqual([]);
  });

  it('keeps workspace realtime independent from nested features', () => {
    const offenders = findDependencyOffenders(
      ({ sourceFile, targetPath }) =>
        isPathWithin(sourceFile, WORKSPACE_REALTIME_ROOT) &&
        targetPath !== null &&
        isPathWithin(targetPath, WORKSPACE_FEATURES_ROOT),
    );

    expect(offenders).toEqual([]);
  });
});

describe('feature architecture AST rule helpers', () => {
  it('accepts feature boundaries and rejects every dependency syntax that crosses them', () => {
    const allowedGraph = createVirtualDependencyGraph({
      'app/App.ts': `
        import { AlphaPage } from '@/features/alpha/public';
        export const App = AlphaPage;
      `,
      'pages/Lazy.ts': `
        export const loadAlpha = () => import('@/features/alpha/public');
      `,
      'pages/Legacy.ts': `
        export const alpha = require('@/features/alpha/public');
      `,
      'features/alpha/Page.ts': `
        import { betaValue } from '@/features/beta/public';
        import type { BetaContract } from '@/features/beta/public';
        export type AlphaContract = BetaContract;
        export const AlphaPage = betaValue;
      `,
      'features/alpha/public.ts': `
        export { AlphaPage } from './Page';
      `,
      'features/alpha/features/one/internal.ts': `
        import { oneValue } from './model';
        export const value = oneValue;
      `,
      'features/alpha/features/one/model.ts': `
        export const oneValue = 'one';
      `,
      'features/alpha/features/two/internal.ts': `
        export const twoValue = 'two';
      `,
      'features/beta/internal.ts': `
        export interface BetaContract { id: string }
        export const betaValue = 'beta';
      `,
      'features/beta/public.ts': `
        export { betaValue } from './internal';
        export type { BetaContract } from './internal';
      `,
    });
    const forbiddenGraph = createVirtualDependencyGraph({
      'app/internal.ts': `
        export const appValue = 'app';
      `,
      'app/App.ts': `
        import { alphaValue } from '@/features/alpha/internal';
        export const App = alphaValue;
      `,
      'pages/ReExport.ts': `
        export { alphaValue } from '@/features/alpha/internal';
      `,
      'pages/Lazy.ts': `
        export const loadAlpha = () => import('@/features/alpha/internal');
      `,
      'pages/Legacy.ts': `
        export const alpha = require('@/features/alpha/internal');
      `,
      'pages/TypeImport.ts': `
        import type { AlphaContract } from '@/features/alpha/internal';
        export type PageContract = AlphaContract;
      `,
      'pages/TypeReExport.ts': `
        export type { AlphaContract } from '@/features/alpha/internal';
      `,
      'features/alpha/fromApp.ts': `
        export { appValue } from '@/app/internal';
      `,
      'features/index.ts': `
        export const featureRootValue = 'root';
      `,
      'features/alpha/internal.ts': `
        import { betaValue } from '@/features/beta/internal';
        export const alphaValue = betaValue;
      `,
      'features/alpha/features/one/internal.ts': `
        import { twoValue } from '../two/internal';
        export const oneValue = twoValue;
      `,
      'features/alpha/features/one/public.ts': `
        export { oneValue } from './internal';
      `,
      'features/alpha/features/two/internal.ts': `
        export const twoValue = 'two';
      `,
      'features/alpha/index.ts': `
        export { alphaValue } from './internal';
      `,
      'features/beta/internal.ts': `
        export const betaValue = 'beta';
      `,
    });
    const allowedFeaturesRoot = path.join(
      allowedGraph.sourceRoot,
      'features',
    );
    const forbiddenFeaturesRoot = path.join(
      forbiddenGraph.sourceRoot,
      'features',
    );
    const allowedFeatureDirectories = ['alpha', 'beta'].map((featureName) =>
      path.join(allowedFeaturesRoot, featureName),
    );
    const forbiddenFeatureDirectories = ['alpha', 'beta'].map(
      (featureName) => path.join(forbiddenFeaturesRoot, featureName),
    );

    expect(
      findExternalFeaturePublicApiOffenders(
        allowedGraph.dependencies,
        allowedFeaturesRoot,
      ),
    ).toEqual([]);
    expect(
      findFeatureAppDependencyOffenders(
        allowedGraph.dependencies,
        allowedFeaturesRoot,
        path.join(allowedGraph.sourceRoot, 'app'),
      ),
    ).toEqual([]);
    expect(
      findFeatureEntryConventionOffenders(
        allowedGraph.sourceFiles,
        allowedFeatureDirectories,
        allowedFeaturesRoot,
      ),
    ).toEqual([]);
    expect(
      findNestedFeatureSiblingOffenders(allowedGraph.dependencies, [
        path.join(allowedFeaturesRoot, 'alpha/features'),
      ]),
    ).toEqual([]);
    expect(
      findExternalFeaturePublicApiOffenders(
        forbiddenGraph.dependencies,
        forbiddenFeaturesRoot,
      ),
    ).toHaveLength(7);
    expect(
      findFeatureAppDependencyOffenders(
        forbiddenGraph.dependencies,
        forbiddenFeaturesRoot,
        path.join(forbiddenGraph.sourceRoot, 'app'),
      ),
    ).toHaveLength(1);
    expect(
      findFeatureEntryConventionOffenders(
        forbiddenGraph.sourceFiles,
        forbiddenFeatureDirectories,
        forbiddenFeaturesRoot,
      ),
    ).toEqual(
      [
        path.join(forbiddenFeaturesRoot, 'alpha/features/one/public.ts'),
        path.join(forbiddenFeaturesRoot, 'alpha/index.ts'),
        path.join(forbiddenFeaturesRoot, 'alpha/public.ts'),
        path.join(forbiddenFeaturesRoot, 'beta/public.ts'),
        path.join(forbiddenFeaturesRoot, 'index.ts'),
      ].sort(),
    );
    expect(
      findNestedFeatureSiblingOffenders(forbiddenGraph.dependencies, [
        path.join(forbiddenFeaturesRoot, 'alpha/features'),
      ]),
    ).toHaveLength(1);
  });

  it('accepts kebab-case feature directories and rejects hyphenated production files', () => {
    const virtualRoot = path.resolve('/virtual/frontend/src');
    const sourceFiles = [
      path.join(virtualRoot, 'features/ai-chat/AiChatPage.tsx'),
      path.join(
        virtualRoot,
        'features/workspace/features/file-management/file-tree.ts',
      ),
    ];
    const featureDirectories = [
      path.join(virtualRoot, 'features/ai-chat'),
      path.join(
        virtualRoot,
        'features/workspace/features/file-management',
      ),
      path.join(virtualRoot, 'features/UserManagement'),
    ];

    expect(findInvalidFeatureDirectoryNames(featureDirectories)).toEqual([
      path.join(virtualRoot, 'features/UserManagement'),
    ]);
    expect(
      findHyphenatedFeatureProductionFiles(
        sourceFiles,
        path.join(virtualRoot, 'features'),
      ),
    ).toEqual([
      path.join(
        virtualRoot,
        'features/workspace/features/file-management/file-tree.ts',
      ),
    ]);
    expect(
      findGenericFeatureRootFiles(
        [
          path.join(virtualRoot, 'features/ai-chat/types.ts'),
          path.join(virtualRoot, 'features/ai-chat/model/threadModel.ts'),
        ],
        path.join(virtualRoot, 'features/ai-chat'),
      ),
    ).toEqual([path.join(virtualRoot, 'features/ai-chat/types.ts')]);
  });
});

describe('shared component architecture boundaries', () => {
  it('keeps shared component package entries limited to approved roots', () => {
    expect(listSharedComponentPackageEntries(SHARED_COMPONENTS_ROOT)).toEqual(
      [...APPROVED_PUBLIC_SHARED_PACKAGE_NAMES].sort(),
    );
  });

  it('keeps external consumers on shared package public entries', () => {
    const offenders = findExternalSharedPackageEntryOffenders(
      productionDependencies,
      SHARED_COMPONENTS_ROOT,
    );

    expect(formatDependencies(offenders)).toEqual([]);
  });

  it('keeps shared public packages on relative internal imports', () => {
    const offenders = findSharedPackageInternalAliasOffenders(
      productionDependencies,
      SHARED_COMPONENTS_ROOT,
    );

    expect(formatDependencies(offenders)).toEqual([]);
  });

  it('keeps the lightweight file-workbench entry unable to reach viewer runtime', () => {
    const offenders = [...findReachableFiles(
      FILE_WORKBENCH_ENTRY,
      productionRuntimeAdjacency,
    )]
      .filter((filePath) =>
        isPathWithin(filePath, FILE_WORKBENCH_VIEWER_ROOT),
      )
      .map((filePath) => path.relative(SOURCE_ROOT, filePath))
      .sort();

    expect(offenders).toEqual([]);
  });

  it('exposes file-workbench viewer runtime only through viewer-entry', () => {
    const offenders = findViewerExposureOffenders(
      productionDependencies,
      FILE_WORKBENCH_VIEWER_ROOT,
      FILE_WORKBENCH_VIEWER_ENTRY,
    );

    expect(formatDependencies(offenders)).toEqual([]);
  });

  it('keeps first-level shared component packages runtime-acyclic', () => {
    const adjacency = buildFirstLevelSharedPackageAdjacency(
      productionSourceFiles,
      productionDependencies,
      SHARED_COMPONENTS_ROOT,
    );
    const cycles = findDirectedCycles(adjacency).map((cycle) =>
      cycle.join(' -> '),
    );

    expect(cycles).toEqual([]);
  });

  it('keeps all shared runtime files acyclic', () => {
    const sharedSourceFiles = productionSourceFiles.filter(
      (sourceFile) => isPathWithin(sourceFile, SHARED_ROOT),
    );
    const adjacency = buildRuntimeFileAdjacency(
      sharedSourceFiles,
      productionDependencies,
    );
    const cycles = findDirectedCycles(adjacency).map((cycle) =>
      cycle
        .map((filePath) => path.relative(SOURCE_ROOT, filePath))
        .join(' -> '),
    );

    expect(cycles).toEqual([]);
  });

  it('keeps resource-workflow independent from file-workbench', () => {
    const offenders = productionDependencies.filter(
      ({ sourceFile, targetPath }) =>
        isPathWithin(sourceFile, RESOURCE_WORKFLOW_ROOT) &&
        targetPath !== null &&
        isPathWithin(targetPath, FILE_WORKBENCH_ROOT),
    );

    expect(formatDependencies(offenders)).toEqual([]);
  });

  it('keeps document-resource contract and parser dependencies one-way', () => {
    const offenders = findDocumentResourceDirectionOffenders(
      productionDependencies,
      DOCUMENT_RESOURCE_ROOT,
      DOCUMENT_RESOURCE_MODEL_ROOT,
      DOCUMENT_RESOURCE_CONTRACT,
      DOCUMENT_RESOURCE_PARSER,
    );
    const parserContractDependencies = productionDependencies.filter(
      ({ sourceFile, targetPath }) =>
        sourceFile === DOCUMENT_RESOURCE_PARSER &&
        targetPath === DOCUMENT_RESOURCE_CONTRACT,
    );

    expect(formatDependencies(offenders)).toEqual([]);
    expect(parserContractDependencies).toHaveLength(1);
  });

  it('keeps hook-workflow model independent from component implementations', () => {
    const offenders = findHookWorkflowModelDirectionOffenders(
      productionDependencies,
      HOOK_WORKFLOW_ROOT,
      HOOK_WORKFLOW_MODEL_ROOT,
    );

    expect(formatDependencies(offenders)).toEqual([]);
  });

  it('keeps markdown syntax highlighting behind dynamic imports', () => {
    const { invalidRuntimeDependencies, missingDynamicImports } =
      inspectMarkdownLazyLoading(
        productionDependencies,
        MARKDOWN_SYNTAX_HIGHLIGHTER,
      );

    expect(formatDependencies(invalidRuntimeDependencies)).toEqual([]);
    expect(missingDynamicImports).toEqual([]);
  });
});

describe('shared architecture AST rule helpers', () => {
  it('accepts public entries, isolated viewer runtime, and type-only package edges', () => {
    const graph = createVirtualDependencyGraph({
      'features/consumer.ts': `
        import { parseTree } from '@/shared/components/file-workbench';
        import { Viewer } from '@/shared/components/file-workbench/viewer-entry';
        export const consumer = [parseTree, Viewer];
      `,
      'shared/components/file-workbench/index.ts': `
        export { parseTree } from './model';
        export type { ViewerContract } from './viewer/types';
      `,
      'shared/components/file-workbench/model.ts': `
        import type { ResourceShell } from '@/shared/components/resource-workflow';
        export const parseTree = (value: ResourceShell) => value;
      `,
      'shared/components/file-workbench/viewer-entry.ts': `
        export { Viewer } from './viewer/Viewer';
      `,
      'shared/components/file-workbench/viewer/Viewer.ts': `
        export const Viewer = 'viewer';
      `,
      'shared/components/file-workbench/viewer/types.ts': `
        export interface ViewerContract { id: string }
      `,
      'shared/components/resource-workflow/index.ts': `
        export type { ViewerContract } from '@/shared/components/file-workbench';
        export interface ResourceShell { id: string }
      `,
    });
    const sharedComponentsRoot = path.join(
      graph.sourceRoot,
      'shared/components',
    );
    const fileWorkbenchRoot = path.join(
      sharedComponentsRoot,
      'file-workbench',
    );
    const viewerRoot = path.join(fileWorkbenchRoot, 'viewer');
    const viewerEntry = path.join(fileWorkbenchRoot, 'viewer-entry.ts');
    const lightweightEntry = path.join(fileWorkbenchRoot, 'index.ts');
    const packageAdjacency = buildFirstLevelSharedPackageAdjacency(
      graph.sourceFiles,
      graph.dependencies,
      sharedComponentsRoot,
    );

    expect(
      findExternalSharedPackageEntryOffenders(
        graph.dependencies,
        sharedComponentsRoot,
      ),
    ).toEqual([]);
    expect(
      findSharedPackageInternalAliasOffenders(
        graph.dependencies,
        sharedComponentsRoot,
      ),
    ).toEqual([]);
    expect(
      [...findReachableFiles(lightweightEntry, graph.runtimeAdjacency)].filter(
        (filePath) => isPathWithin(filePath, viewerRoot),
      ),
    ).toEqual([]);
    expect(
      findViewerExposureOffenders(
        graph.dependencies,
        viewerRoot,
        viewerEntry,
      ),
    ).toEqual([]);
    expect(findDirectedCycles(packageAdjacency)).toEqual([]);
  });

  it('rejects deep imports, internal aliases, viewer reachability, and runtime package cycles', () => {
    const graph = createVirtualDependencyGraph({
      'features/consumer.ts': `
        import { internalValue } from '@/shared/components/file-workbench/internal';
        export const consumer = internalValue;
      `,
      'shared/components/file-workbench/index.ts': `
        export { Viewer } from './viewerBridge';
        export const fileValue = 'file';
      `,
      'shared/components/file-workbench/internal.ts': `
        export const internalValue = 'internal';
      `,
      'shared/components/file-workbench/dragPayload.ts': `
        export const dragPayload = 'drag';
      `,
      'shared/components/file-workbench/tree/Node.ts': `
        import { dragPayload } from '@/shared/components/file-workbench/dragPayload';
        export const node = dragPayload;
      `,
      'shared/components/file-workbench/cycle.ts': `
        import { resourceValue } from '@/shared/components/resource-workflow';
        export const cycleValue = resourceValue;
      `,
      'shared/components/file-workbench/viewerBridge.ts': `
        export { Viewer } from './viewer/Viewer';
      `,
      'shared/components/file-workbench/viewer-entry.ts': `
        export { Viewer } from './viewer/Viewer';
      `,
      'shared/components/file-workbench/viewer/Viewer.ts': `
        export const Viewer = 'viewer';
      `,
      'shared/components/resource-workflow/index.ts': `
        import { fileValue } from '@/shared/components/file-workbench';
        export const resourceValue = fileValue;
      `,
    });
    const sharedComponentsRoot = path.join(
      graph.sourceRoot,
      'shared/components',
    );
    const fileWorkbenchRoot = path.join(
      sharedComponentsRoot,
      'file-workbench',
    );
    const viewerRoot = path.join(fileWorkbenchRoot, 'viewer');
    const viewerEntry = path.join(fileWorkbenchRoot, 'viewer-entry.ts');
    const lightweightEntry = path.join(fileWorkbenchRoot, 'index.ts');
    const packageAdjacency = buildFirstLevelSharedPackageAdjacency(
      graph.sourceFiles,
      graph.dependencies,
      sharedComponentsRoot,
    );

    expect(
      findExternalSharedPackageEntryOffenders(
        graph.dependencies,
        sharedComponentsRoot,
      ),
    ).toHaveLength(1);
    expect(
      findSharedPackageInternalAliasOffenders(
        graph.dependencies,
        sharedComponentsRoot,
      ),
    ).toHaveLength(1);
    expect(
      [...findReachableFiles(lightweightEntry, graph.runtimeAdjacency)].some(
        (filePath) => isPathWithin(filePath, viewerRoot),
      ),
    ).toBe(true);
    expect(
      findViewerExposureOffenders(
        graph.dependencies,
        viewerRoot,
        viewerEntry,
      ),
    ).toHaveLength(1);
    expect(findDirectedCycles(packageAdjacency).length).toBeGreaterThan(0);
  });

  it('accepts dynamic markdown imports and rejects static markdown imports', () => {
    const allowedGraph = createVirtualDependencyGraph({
      'shared/components/markdown/markdownSyntaxHighlighter.ts': `
        import type { SyntaxHighlighterProps } from 'react-syntax-highlighter';
        export const load = () => Promise.all([
          import('react-syntax-highlighter'),
          import('react-syntax-highlighter/dist/esm/styles/prism'),
        ]) as Promise<unknown> & { props?: SyntaxHighlighterProps };
      `,
    });
    const forbiddenGraph = createVirtualDependencyGraph({
      'shared/components/markdown/markdownSyntaxHighlighter.ts': `
        import { Prism } from 'react-syntax-highlighter';
        import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
        export const bundle = [Prism, oneDark];
      `,
    });
    const allowedSource = path.join(
      allowedGraph.sourceRoot,
      'shared/components/markdown/markdownSyntaxHighlighter.ts',
    );
    const forbiddenSource = path.join(
      forbiddenGraph.sourceRoot,
      'shared/components/markdown/markdownSyntaxHighlighter.ts',
    );
    const allowedResult = inspectMarkdownLazyLoading(
      allowedGraph.dependencies,
      allowedSource,
    );
    const forbiddenResult = inspectMarkdownLazyLoading(
      forbiddenGraph.dependencies,
      forbiddenSource,
    );

    expect(allowedResult.invalidRuntimeDependencies).toEqual([]);
    expect(allowedResult.missingDynamicImports).toEqual([]);
    expect(forbiddenResult.invalidRuntimeDependencies).toHaveLength(2);
    expect(forbiddenResult.missingDynamicImports).toEqual([
      ...MARKDOWN_LAZY_MODULE_SPECIFIERS,
    ]);
  });
});
