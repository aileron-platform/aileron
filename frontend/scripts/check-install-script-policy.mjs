import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import test from 'node:test';

const EXPECTED_NPM_VERSION = '12.0.1';
const EXPECTED_POLICY = {
  '@swc/core@1.15.2': true,
  'esbuild@0.25.0': true,
};
const NPM_COMMAND_TIMEOUT_MS = 30_000;

function readJson(path) {
  return JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
}

function runNpm(arguments_, cwd, extraEnvironment = {}) {
  return spawnSync('npm', arguments_, {
    cwd,
    encoding: 'utf8',
    env: {...process.env, ...extraEnvironment},
    killSignal: 'SIGKILL',
    maxBuffer: 1024 * 1024,
    timeout: NPM_COMMAND_TIMEOUT_MS,
  });
}

test('the tracked npm policy approves only the reviewed install scripts', () => {
  const packageJson = readJson('../package.json');
  const packageLock = readJson('../package-lock.json');

  assert.equal(packageJson.packageManager, `npm@${EXPECTED_NPM_VERSION}`);
  assert.deepEqual(packageJson.allowScripts, EXPECTED_POLICY);
  assert.equal(
    readFileSync(new URL('../.npmrc', import.meta.url), 'utf8'),
    'strict-allow-scripts=true\n',
  );

  const requiredInstallScripts = Object.entries(packageLock.packages)
    .filter(([, metadata]) => metadata.hasInstallScript && !metadata.optional)
    .map(([packagePath, metadata]) => {
      const packageName = packagePath.slice(packagePath.lastIndexOf('node_modules/') + 13);
      return `${packageName}@${metadata.version}`;
    })
    .sort();

  assert.deepEqual(requiredInstallScripts, Object.keys(EXPECTED_POLICY).sort());
});

test('the tracked frontend build toolchain uses the reviewed security patch floor', () => {
  const packageJson = readJson('../package.json');
  const packageLock = readJson('../package-lock.json');

  assert.equal(packageJson.dependencies.esbuild, '0.25.0');
  assert.equal(packageJson.devDependencies.vite, '6.4.3');
  assert.equal(packageLock.packages['node_modules/esbuild'].version, '0.25.0');
  assert.equal(packageLock.packages['node_modules/vite'].version, '6.4.3');
});

test('all frontend Docker build paths enforce the same npm policy before install', () => {
  for (const dockerfileName of [
    'Dockerfile',
    'Dockerfile.dev',
    'Dockerfile.playwright',
  ]) {
    const dockerfile = readFileSync(
      new URL(`../${dockerfileName}`, import.meta.url),
      'utf8',
    );
    assert.match(dockerfile, /ARG NPM_VERSION=12\.0\.1/);
    assert.match(
      dockerfile,
      /test "\$\(npm --version\)" = "\$\{NPM_VERSION\}"/,
    );
    assert.match(
      dockerfile,
      /test "\$\(node -p "require\('\.\/package\.json'\)\.packageManager"\)" = "npm@\$\{NPM_VERSION\}"/,
    );
    assert.ok(
      dockerfile.indexOf('.npmrc') < dockerfile.indexOf('npm ci'),
      `${dockerfileName} must copy .npmrc before npm ci`,
    );
  }
});

test('the container unit-test gate uses bounded workers and a hard timeout', () => {
  const packageJson = readJson('../package.json');
  const compose = readFileSync(
    new URL('../docker-compose.test.yml', import.meta.url),
    'utf8',
  );

  assert.equal(
    packageJson.scripts['test:run'],
    'vitest run --config vite.config.test.ts --pool=forks --maxWorkers=4',
  );
  assert.match(
    compose,
    /timeout -s TERM -k 10 900 npm run test:run/,
  );
});

test('strict npm policy rejects an unreviewed install script', () => {
  const npmVersion = spawnSync('npm', ['--version'], {
    encoding: 'utf8',
    timeout: NPM_COMMAND_TIMEOUT_MS,
  });
  assert.equal(npmVersion.error, undefined);
  assert.equal(npmVersion.status, 0, npmVersion.stderr);
  assert.equal(npmVersion.stdout.trim(), EXPECTED_NPM_VERSION);

  const fixtureRoot = mkdtempSync(join(tmpdir(), 'aileron-npm-policy-'));
  const dependencyRoot = join(fixtureRoot, 'unreviewed-install-script');
  const sentinelPath = join(fixtureRoot, 'install-script-ran');

  try {
    writeFileSync(
      join(fixtureRoot, 'package.json'),
      `${JSON.stringify(
        {
          name: 'aileron-install-script-policy-fixture',
          version: '1.0.0',
          private: true,
          dependencies: {
            'unreviewed-install-script': 'file:./unreviewed-install-script',
          },
        },
        null,
        2,
      )}\n`,
    );
    writeFileSync(join(fixtureRoot, '.npmrc'), 'strict-allow-scripts=true\n');
    mkdirSync(dependencyRoot);
    writeFileSync(
      join(dependencyRoot, 'package.json'),
      `${JSON.stringify(
        {
          name: 'unreviewed-install-script',
          version: '1.0.0',
          scripts: {postinstall: 'node postinstall.cjs'},
        },
        null,
        2,
      )}\n`,
    );
    writeFileSync(
      join(dependencyRoot, 'postinstall.cjs'),
      "require('node:fs').writeFileSync(process.env.POLICY_SENTINEL, 'ran');\n",
    );

    const lockResult = runNpm(
      [
        'install',
        '--package-lock-only',
        '--ignore-scripts',
        '--offline',
        '--no-audit',
        '--no-fund',
      ],
      fixtureRoot,
    );
    assert.equal(lockResult.error, undefined);
    assert.equal(lockResult.status, 0, lockResult.stderr || lockResult.stdout);

    const installResult = runNpm(
      ['ci', '--offline', '--no-audit', '--no-fund'],
      fixtureRoot,
      {POLICY_SENTINEL: sentinelPath},
    );
    assert.equal(
      installResult.error,
      undefined,
      `npm policy fixture exceeded ${NPM_COMMAND_TIMEOUT_MS}ms`,
    );
    assert.notEqual(installResult.status, 0, 'unreviewed script must fail npm ci');
    assert.match(
      `${installResult.stdout}\n${installResult.stderr}`,
      /install scripts|EALLOWSCRIPTS/i,
    );
    assert.throws(() => readFileSync(sentinelPath), {code: 'ENOENT'});
  } finally {
    rmSync(fixtureRoot, {force: true, recursive: true});
  }
});
