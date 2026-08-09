import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  assertPlatformResourceContract,
  assertPlatformResourceDocumentation,
} from './platform-resource-observability-validator.mjs';

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const docsSiteDirectory = path.resolve(scriptDirectory, '..');
const repositoryDirectory = path.resolve(docsSiteDirectory, '..');
const relativeChapter = path.join('features', 'platform', 'resource-statistics-and-capacity.md');
const contract = JSON.parse(await readFile(
  path.join(repositoryDirectory, 'contracts', 'platform-resource-observability', 'wire-contract.json'),
  'utf8',
));

assertPlatformResourceContract(contract);
assertPlatformResourceDocumentation({
  contract,
  zhHantSource: await readFile(path.join(docsSiteDirectory, 'docs', relativeChapter), 'utf8'),
  englishSource: await readFile(path.join(
    docsSiteDirectory,
    'i18n',
    'en',
    'docusaurus-plugin-content-docs',
    'current',
    relativeChapter,
  ), 'utf8'),
  sidebarSource: await readFile(path.join(docsSiteDirectory, 'sidebars.ts'), 'utf8'),
});

process.stdout.write('Platform resource observability documentation matches the shared contract.\n');
