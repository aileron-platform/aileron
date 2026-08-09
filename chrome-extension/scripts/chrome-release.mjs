import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const extensionDirectory = dirname(dirname(fileURLToPath(import.meta.url)));
const outputDirectory = join(extensionDirectory, ".output", "chrome-mv3");
const releaseDirectory = join(extensionDirectory, "release", "chrome-mv3");
const stagingDirectory = join(
  extensionDirectory,
  "release",
  `.chrome-mv3-${process.pid}.tmp`
);
const backupDirectory = join(
  extensionDirectory,
  "release",
  `.chrome-mv3-${process.pid}.backup`
);

function getTrustedOrigins() {
  const rawValue = process.env.WXT_TRUSTED_FRONTEND_ORIGINS;
  if (!rawValue) {
    throw new Error(
      "WXT_TRUSTED_FRONTEND_ORIGINS is required for a Chrome release build"
    );
  }

  return rawValue.split(",").map((entry) => {
    const url = new URL(entry);
    return url.origin;
  });
}

function getExpectedManifestMatches(trustedOrigins) {
  return Array.from(
    new Set(
      trustedOrigins.map((origin) => {
        const url = new URL(origin);
        return `${url.protocol}//${url.hostname}/*`;
      })
    )
  );
}

function assertArtifact(artifactDirectory, trustedOrigins) {
  const manifestPath = join(artifactDirectory, "manifest.json");
  const backgroundPath = join(artifactDirectory, "background.js");
  if (!existsSync(manifestPath) || !existsSync(backgroundPath)) {
    throw new Error(`Chrome artifact is incomplete: ${artifactDirectory}`);
  }

  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const actualMatches = manifest.externally_connectable?.matches;
  const expectedMatches = getExpectedManifestMatches(trustedOrigins);
  if (JSON.stringify(actualMatches) !== JSON.stringify(expectedMatches)) {
    throw new Error(
      `Chrome artifact externally_connectable mismatch: expected ${JSON.stringify(expectedMatches)}`
    );
  }
  if (
    manifest.default_locale !== "en" ||
    manifest.description !== "__MSG_extensionDescription__"
  ) {
    throw new Error("Chrome artifact manifest localization is invalid");
  }

  const localizedDescriptions = ["en", "zh_TW"].map((locale) => {
    const messagesPath = join(
      artifactDirectory,
      "_locales",
      locale,
      "messages.json"
    );
    if (!existsSync(messagesPath)) {
      throw new Error(`Chrome artifact is missing locale: ${locale}`);
    }
    const messages = JSON.parse(readFileSync(messagesPath, "utf8"));
    const description = messages.extensionDescription?.message;
    if (typeof description !== "string" || description.length === 0) {
      throw new Error(
        `Chrome artifact locale is missing extensionDescription: ${locale}`
      );
    }
    return description;
  });
  if (new Set(localizedDescriptions).size !== localizedDescriptions.length) {
    throw new Error("Chrome artifact localized descriptions must be distinct");
  }

  const background = readFileSync(backgroundPath, "utf8");
  for (const requiredText of [
    "onMessageExternal",
    "configureBrowserExtensionPairing",
    ...trustedOrigins,
  ]) {
    if (!background.includes(requiredText)) {
      throw new Error(
        `Chrome artifact background is missing required pairing content: ${requiredText}`
      );
    }
  }
}

function listFiles(directory, prefix = "") {
  return readdirSync(directory, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap((entry) => {
      const relativePath = join(prefix, entry.name);
      return entry.isDirectory()
        ? listFiles(join(directory, entry.name), relativePath)
        : [relativePath];
    });
}

function assertDirectoriesEqual(expectedDirectory, actualDirectory) {
  const expectedFiles = listFiles(expectedDirectory);
  const actualFiles = listFiles(actualDirectory);
  if (JSON.stringify(actualFiles) !== JSON.stringify(expectedFiles)) {
    throw new Error("Tracked Chrome release file list does not match the build output");
  }

  for (const relativePath of expectedFiles) {
    const expected = readFileSync(join(expectedDirectory, relativePath));
    const actual = readFileSync(join(actualDirectory, relativePath));
    if (!actual.equals(expected)) {
      throw new Error(
        `Tracked Chrome release differs from the build output: ${relativePath}`
      );
    }
  }
}

function runWxtBuild() {
  const wxtCli = join(extensionDirectory, "node_modules", "wxt", "bin", "wxt.mjs");
  const result = spawnSync(process.execPath, [wxtCli, "build"], {
    cwd: extensionDirectory,
    env: process.env,
    stdio: "inherit",
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`WXT build failed with exit code ${result.status}`);
  }
}

function publishRelease(trustedOrigins) {
  rmSync(stagingDirectory, { force: true, recursive: true });
  rmSync(backupDirectory, { force: true, recursive: true });
  cpSync(outputDirectory, stagingDirectory, { recursive: true });
  assertArtifact(stagingDirectory, trustedOrigins);

  let backupCreated = false;
  try {
    if (existsSync(releaseDirectory)) {
      renameSync(releaseDirectory, backupDirectory);
      backupCreated = true;
    }
    renameSync(stagingDirectory, releaseDirectory);
    rmSync(backupDirectory, { force: true, recursive: true });
  } catch (error) {
    rmSync(releaseDirectory, { force: true, recursive: true });
    if (backupCreated && existsSync(backupDirectory)) {
      renameSync(backupDirectory, releaseDirectory);
    }
    throw error;
  } finally {
    rmSync(stagingDirectory, { force: true, recursive: true });
    rmSync(backupDirectory, { force: true, recursive: true });
  }
}

const command = process.argv[2];
if (command !== "publish" && command !== "verify") {
  throw new Error("Expected command: publish or verify");
}

const trustedOrigins = getTrustedOrigins();
runWxtBuild();
assertArtifact(outputDirectory, trustedOrigins);

if (command === "publish") {
  publishRelease(trustedOrigins);
  assertArtifact(releaseDirectory, trustedOrigins);
  console.log("Chrome release artifact was published and verified");
} else {
  assertArtifact(releaseDirectory, trustedOrigins);
  assertDirectoriesEqual(outputDirectory, releaseDirectory);
  console.log("Tracked Chrome release matches the verified build output");
}
