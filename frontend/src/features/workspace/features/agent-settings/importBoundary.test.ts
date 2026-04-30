import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const root = path.resolve(__dirname);

const collectSourceFiles = (dir: string): string[] => {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      return collectSourceFiles(fullPath);
    }
    return /\.(ts|tsx)$/.test(entry.name) ? [fullPath] : [];
  });
};

describe('agent-settings import boundary', () => {
  it('does not import from the claude-code module', () => {
    const offenders = collectSourceFiles(root).filter((file) => {
      const content = fs.readFileSync(file, 'utf8');
      return /from ['"].*claude-code|import\(['"].*claude-code/.test(content);
    });

    expect(offenders.map((file) => path.relative(root, file))).toEqual([]);
  });
});
