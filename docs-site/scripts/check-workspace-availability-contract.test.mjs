import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const manifest = JSON.parse(await readFile(
  new URL('../../contracts/workspace-availability.json', import.meta.url),
));

const expectedDeletionPhases = [
  'queued',
  'cancelling_automations',
  'stopping_runtime',
  'deleting_resources',
  'finalizing',
];

test('uses the backend deletion job phases in the public projection', () => {
  const deletion = manifest.deletionProjection;

  assert.deepEqual(deletion.phases, expectedDeletionPhases);
  assert.deepEqual(Object.keys(deletion.phaseProjection), expectedDeletionPhases);
  assert.deepEqual(deletion.progress.requiredPhases, expectedDeletionPhases);
});

test('keeps deletion entry and failure actions outside the phase literal set', () => {
  const deletion = manifest.deletionProjection;

  assert.deepEqual(deletion.entry.allowedActions, ['delete']);
  assert.deepEqual(deletion.failure.allowedActions, ['retry']);
  assert.equal(deletion.completion.availability, 'not_found');
  assert.equal(deletion.completion.httpStatus, 404);
  assert.equal(deletion.phaseProjection.finalizing.availability, 'deleting');
});
