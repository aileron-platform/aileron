import { describe, expect, it } from 'vitest';
import {
  basenameWithoutKnownDocumentExtension,
  replaceFileNameInPath,
  splitDocumentPath,
} from './documentMetadata';

describe('documentMetadata helpers', () => {
  it('splits file name and namespace from a nested markdown path', () => {
    expect(splitDocumentPath('team/review-command.md')).toEqual({
      fileName: 'review-command.md',
      namespace: 'team',
      path: 'team/review-command.md',
    });
  });

  it('does not invent namespace for flat paths', () => {
    expect(splitDocumentPath('output-style.md')).toEqual({
      fileName: 'output-style.md',
      namespace: undefined,
      path: 'output-style.md',
    });
  });

  it('replaces only the file name part of a path', () => {
    expect(replaceFileNameInPath('team/review-command.md', 'qa-command.md')).toBe('team/qa-command.md');
    expect(replaceFileNameInPath('review-command.md', 'qa-command.md')).toBe('qa-command.md');
  });

  it('derives a document name from fileName without known document extension', () => {
    expect(basenameWithoutKnownDocumentExtension('incident-review.md')).toBe('incident-review');
    expect(basenameWithoutKnownDocumentExtension('ops/incident-review.md')).toBe('incident-review');
  });
});
