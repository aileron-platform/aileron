import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const docsRoot = path.resolve(scriptDir, '..');
const repositoryRoot = path.resolve(docsRoot, '..');
const schema = JSON.parse(fs.readFileSync(
  path.join(repositoryRoot, 'helm/aileron/values.schema.json'),
  'utf8',
));

const documents = [
  'docs/reference/helm-values.md',
  'i18n/en/docusaurus-plugin-content-docs/current/reference/helm-values.md',
  'docs/installation/production.md',
  'i18n/en/docusaurus-plugin-content-docs/current/installation/production.md',
  'docs/installation/kubernetes-networking.md',
  'i18n/en/docusaurus-plugin-content-docs/current/installation/kubernetes-networking.md',
].map((relativePath) => ({
  relativePath,
  contents: fs.readFileSync(path.join(docsRoot, relativePath), 'utf8'),
}));

const removedPaths = [
  'runtimeDatabase.credentialKey',
  'postgres.auth.password',
  'oidc.scopes',
  'oidc.allowedAlgorithms',
  'oidc.maxTokenLifetimeSeconds',
  'oidc.requiredAcr',
  'oidc.jwksCacheTtl',
  'oidc.discoveryTimeoutSeconds',
  'turn.iceServersSecretName',
];

for (const { relativePath, contents } of documents) {
  for (const removedPath of removedPaths) {
    assert.equal(
      contents.includes(removedPath),
      false,
      `${relativePath} documents removed Helm path ${removedPath}`,
    );
  }
}

function schemaHasPath(dotPath) {
  let current = schema;
  for (const segment of dotPath.split('.')) {
    current = current.properties?.[segment];
    if (!current) return false;
  }
  return true;
}

const documentedSecretReferences = [
  'platformSecrets.existingSecretName',
  'platformSecrets.databaseUrlKey',
  'platformSecrets.runtimeDatabaseCredentialKey',
  'platformSecrets.postgresUsernameKey',
  'platformSecrets.postgresPasswordKey',
  'oidc.clientSecretName',
  'oidc.clientSecretKey',
  'turn.existingSecretName',
];

for (const dotPath of documentedSecretReferences) {
  assert.equal(schemaHasPath(dotPath), true, `Helm schema is missing ${dotPath}`);
  for (const { relativePath, contents } of documents.slice(0, 2)) {
    assert.equal(
      contents.includes(dotPath),
      true,
      `${relativePath} is missing current Helm path ${dotPath}`,
    );
  }
}

console.log('Helm values documentation matches the current Secret-reference contract');
