import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtempSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {dirname, join} from 'node:path';
import {createRequire} from 'node:module';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const EXPECTED_PACKAGE_NAME = 'image-size-safe';
const EXPECTED_PACKAGE_VERSION = '2.0.3';
const EXPECTED_PACKAGE_INTEGRITY =
  'sha512-M8prcBmr9nsXwZMC4RzuOM7qvkwvQO1fN+PRxC+D8mc4pMBj2/l0e/kF7s8y3GB10O9zMSUgHHU66Y8tigWIfw==';
const LOCK_PACKAGE_PATH =
  'node_modules/@docusaurus/mdx-loader/node_modules/image-size';
const PROBE_TIMEOUT_MS = 2_000;

const require = createRequire(import.meta.url);
const mdxLoaderRequire = createRequire(require.resolve('@docusaurus/mdx-loader'));
const imageSizeModule = mdxLoaderRequire('image-size');
const imageSizeFromFileModule = mdxLoaderRequire('image-size/fromFile');

function encodeAscii(value) {
  return Uint8Array.from(Array.from(value, (char) => char.charCodeAt(0)));
}

function uint32BigEndian(value) {
  return Uint8Array.from([
    (value >>> 24) & 0xff,
    (value >>> 16) & 0xff,
    (value >>> 8) & 0xff,
    value & 0xff,
  ]);
}

function concatenate(...parts) {
  const result = new Uint8Array(
    parts.reduce((total, part) => total + part.length, 0),
  );
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

function box(name, payload, size = payload.length + 8) {
  return concatenate(uint32BigEndian(size), encodeAscii(name), payload);
}

function createMaliciousPayload(kind) {
  switch (kind) {
    case 'icns':
      return concatenate(
        encodeAscii('icns'),
        uint32BigEndian(16),
        encodeAscii('ic07'),
        uint32BigEndian(0),
      );
    case 'jxl':
      return concatenate(
        box('JXL ', new Uint8Array(4)),
        box('ftyp', concatenate(encodeAscii('jxl '), new Uint8Array(4))),
        box('jxlp', new Uint8Array(4), 0),
      );
    case 'heif':
      return concatenate(
        box('ftyp', concatenate(encodeAscii('heic'), new Uint8Array(4))),
        box(
          'meta',
          concatenate(
            new Uint8Array(4),
            box('iprp', box('ipco', box('ispe', new Uint8Array(8), 0))),
          ),
        ),
      );
    default:
      throw new TypeError(`Unknown probe kind: ${kind}`);
  }
}

function createPngHeader(width, height) {
  return concatenate(
    Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    uint32BigEndian(13),
    encodeAscii('IHDR'),
    uint32BigEndian(width),
    uint32BigEndian(height),
    Uint8Array.from([8, 6, 0, 0, 0]),
  );
}

function runSecurityProbe(kind) {
  const expectedMessage = {
    icns: 'Invalid ICNS',
    jxl: 'Invalid JXL',
    heif: 'Invalid HEIF',
  }[kind];
  try {
    imageSizeModule.imageSize(createMaliciousPayload(kind));
  } catch (error) {
    if (error instanceof TypeError && error.message === expectedMessage) {
      return;
    }
    throw error;
  }
  throw new Error(`${kind} payload was accepted`);
}

const probeKind = process.argv[2] === '--security-probe' ? process.argv[3] : null;

if (probeKind) {
  runSecurityProbe(probeKind);
} else {
  test('Docusaurus resolves the integrity-pinned compatibility package', () => {
    const lock = JSON.parse(
      readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'),
    );
    const lockPackage = lock.packages[LOCK_PACKAGE_PATH];
    assert.ok(lockPackage, `${LOCK_PACKAGE_PATH} must exist in package-lock.json`);
    assert.equal(lockPackage.name, EXPECTED_PACKAGE_NAME);
    assert.equal(lockPackage.version, EXPECTED_PACKAGE_VERSION);
    assert.equal(lockPackage.integrity, EXPECTED_PACKAGE_INTEGRITY);

    const installedEntry = mdxLoaderRequire.resolve('image-size');
    const installedPackage = JSON.parse(
      readFileSync(join(dirname(dirname(installedEntry)), 'package.json'), 'utf8'),
    );
    assert.equal(installedPackage.name, EXPECTED_PACKAGE_NAME);
    assert.equal(installedPackage.version, EXPECTED_PACKAGE_VERSION);
  });

  test('root and fromFile exports preserve the Docusaurus image-size contract', async () => {
    assert.equal(typeof imageSizeModule.imageSize, 'function');
    assert.equal(typeof imageSizeFromFileModule.imageSizeFromFile, 'function');

    const png = createPngHeader(37, 19);
    assert.deepEqual(imageSizeModule.imageSize(png), {
      height: 19,
      type: 'png',
      width: 37,
    });

    const temporaryDirectory = mkdtempSync(join(tmpdir(), 'aileron-image-size-'));
    const imagePath = join(temporaryDirectory, 'contract.png');
    try {
      writeFileSync(imagePath, png);
      assert.deepEqual(await imageSizeFromFileModule.imageSizeFromFile(imagePath), {
        height: 19,
        type: 'png',
        width: 37,
      });
    } finally {
      rmSync(temporaryDirectory, {force: true, recursive: true});
    }
  });

  for (const kind of ['icns', 'jxl', 'heif']) {
    test(`${kind} zero-size payload fails closed without hanging`, () => {
      const result = spawnSync(
        process.execPath,
        [fileURLToPath(import.meta.url), '--security-probe', kind],
        {
          encoding: 'utf8',
          killSignal: 'SIGKILL',
          maxBuffer: 16 * 1024,
          timeout: PROBE_TIMEOUT_MS,
        },
      );

      assert.equal(
        result.error,
        undefined,
        `${kind} probe exceeded ${PROBE_TIMEOUT_MS}ms: ${result.error?.message}`,
      );
      assert.equal(
        result.status,
        0,
        `${kind} probe did not fail closed: ${result.stderr || result.stdout}`,
      );
    });
  }
}
