import { describe, it, expect } from 'vitest';
import { parseFrontmatterSegments, preprocessLatex, preprocessMarkdown } from './markdownPreprocess';

describe('preprocessLatex', () => {
  it('裸 LaTeX equation block 被包裝為 $$', () => {
    const input = '\\begin{equation}\nE=mc^2\n\\end{equation}';
    const result = preprocessLatex(input);
    expect(result).toBe('$$\n\\begin{equation}\nE=mc^2\n\\end{equation}\n$$');
  });

  it('裸 LaTeX align block 被包裝為 $$', () => {
    const input = 'Some text\n\\begin{align}\na &= b \\\\\nc &= d\n\\end{align}\nMore text';
    const result = preprocessLatex(input);
    expect(result).toContain('$$\n\\begin{align}');
    expect(result).toContain('\\end{align}\n$$');
  });

  it('已被 $$ 包圍的 LaTeX block 不重複包裝', () => {
    const input = '$$\n\\begin{equation}\nE=mc^2\n\\end{equation}\n$$';
    const result = preprocessLatex(input);
    expect(result).toBe(input);
  });

  it('不含 LaTeX block 的純文字不受影響', () => {
    const input = '# Hello\n\nThis is plain markdown with **bold** and *italic*.';
    const result = preprocessLatex(input);
    expect(result).toBe(input);
  });

  it('不含 LaTeX block 的空字串不受影響', () => {
    expect(preprocessLatex('')).toBe('');
  });

  it('inline math $...$ 不受影響', () => {
    const input = 'The formula $E=mc^2$ is famous.';
    const result = preprocessLatex(input);
    expect(result).toBe(input);
  });
});

describe('parseFrontmatterSegments', () => {
  it('解析文件開頭的 YAML frontmatter 區塊', () => {
    const input = `---
name: openspec-ff-change
description: Fast-forward through artifact creation
metadata:
  author: openspec
---

# Title`;

    const result = parseFrontmatterSegments(input);
    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({
      type: 'frontmatter',
      data: {
        name: 'openspec-ff-change',
        description: 'Fast-forward through artifact creation',
        metadata: { author: 'openspec' },
      },
    });
    expect(result[1]).toMatchObject({
      type: 'markdown',
      content: '\n\n# Title',
    });
  });

  it('解析文件中段的 YAML frontmatter 區塊', () => {
    const input = `<skill>
<name>openspec-ff-change</name>
---
name: openspec-ff-change
compatibility: Requires openspec CLI.
metadata:
  version: "1.0"
---
`;

    const result = parseFrontmatterSegments(input);
    expect(result).toHaveLength(3);
    expect(result[0]).toMatchObject({
      type: 'markdown',
      content: '<skill>\n<name>openspec-ff-change</name>\n',
    });
    expect(result[1]).toMatchObject({
      type: 'frontmatter',
      data: {
        name: 'openspec-ff-change',
        compatibility: 'Requires openspec CLI.',
        metadata: { version: '1.0' },
      },
    });
  });

  it('非 YAML 分隔線區塊不視為 frontmatter', () => {
    const input = `---
not valid: [
---
`;

    expect(parseFrontmatterSegments(input)).toEqual([{ type: 'markdown', content: input }]);
  });
});

describe('preprocessMarkdown', () => {
  it('保留 LaTeX block 預處理', () => {
    const input = `\\begin{equation}
E=mc^2
\\end{equation}`;

    const result = preprocessMarkdown(input);
    expect(result).toContain('$$\n\\begin{equation}');
  });
});
