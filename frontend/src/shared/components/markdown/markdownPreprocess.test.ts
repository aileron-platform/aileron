import { describe, it, expect } from 'vitest';
import { parseFrontmatterSegments, preprocessLatex, preprocessMarkdown } from './markdownPreprocess';

describe('preprocessLatex', () => {
  it('\u88f8 LaTeX equation block \u88ab\u5305\u88dd\u70ba $$', () => {
    const input = '\\begin{equation}\nE=mc^2\n\\end{equation}';
    const result = preprocessLatex(input);
    expect(result).toBe('$$\n\\begin{equation}\nE=mc^2\n\\end{equation}\n$$');
  });

  it('\u88f8 LaTeX align block \u88ab\u5305\u88dd\u70ba $$', () => {
    const input = 'Some text\n\\begin{align}\na &= b \\\\\nc &= d\n\\end{align}\nMore text';
    const result = preprocessLatex(input);
    expect(result).toContain('$$\n\\begin{align}');
    expect(result).toContain('\\end{align}\n$$');
  });

  it('\u5df2\u88ab $$ \u5305\u570d\u7684 LaTeX block \u4e0d\u91cd\u8907\u5305\u88dd', () => {
    const input = '$$\n\\begin{equation}\nE=mc^2\n\\end{equation}\n$$';
    const result = preprocessLatex(input);
    expect(result).toBe(input);
  });

  it('\u4e0d\u542b LaTeX block \u7684\u7d14\u6587\u5b57\u4e0d\u53d7\u5f71\u97ff', () => {
    const input = '# Hello\n\nThis is plain markdown with **bold** and *italic*.';
    const result = preprocessLatex(input);
    expect(result).toBe(input);
  });

  it('\u4e0d\u542b LaTeX block \u7684\u7a7a\u5b57\u4e32\u4e0d\u53d7\u5f71\u97ff', () => {
    expect(preprocessLatex('')).toBe('');
  });

  it('inline math $...$ \u4e0d\u53d7\u5f71\u97ff', () => {
    const input = 'The formula $E=mc^2$ is famous.';
    const result = preprocessLatex(input);
    expect(result).toBe(input);
  });
});

describe('parseFrontmatterSegments', () => {
  it('\u89e3\u6790\u6587\u4ef6\u958b\u982d\u7684 YAML frontmatter \u5340\u584a', () => {
    const input = `---
name: sample-skill-update
description: Fast-forward through artifact creation
metadata:
  author: example
---

# Title`;

    const result = parseFrontmatterSegments(input);
    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({
      type: 'frontmatter',
      data: {
        name: 'sample-skill-update',
        description: 'Fast-forward through artifact creation',
        metadata: { author: 'example' },
      },
    });
    expect(result[1]).toMatchObject({
      type: 'markdown',
      content: '\n\n# Title',
    });
  });

  it('\u89e3\u6790\u6587\u4ef6\u4e2d\u6bb5\u7684 YAML frontmatter \u5340\u584a', () => {
    const input = `<skill>
<name>sample-skill-update</name>
---
name: sample-skill-update
compatibility: Requires the example CLI.
metadata:
  version: "1.0"
---
`;

    const result = parseFrontmatterSegments(input);
    expect(result).toHaveLength(3);
    expect(result[0]).toMatchObject({
      type: 'markdown',
      content: '<skill>\n<name>sample-skill-update</name>\n',
    });
    expect(result[1]).toMatchObject({
      type: 'frontmatter',
      data: {
        name: 'sample-skill-update',
        compatibility: 'Requires the example CLI.',
        metadata: { version: '1.0' },
      },
    });
  });

  it('\u975e YAML \u5206\u9694\u7dda\u5340\u584a\u4e0d\u8996\u70ba frontmatter', () => {
    const input = `---
not valid: [
---
`;

    expect(parseFrontmatterSegments(input)).toEqual([{ type: 'markdown', content: input }]);
  });
});

describe('preprocessMarkdown', () => {
  it('\u4fdd\u7559 LaTeX block \u9810\u8655\u7406', () => {
    const input = `\\begin{equation}
E=mc^2
\\end{equation}`;

    const result = preprocessMarkdown(input);
    expect(result).toContain('$$\n\\begin{equation}');
  });

  it('\u4fdd\u7559 <br> \u6a19\u7c64，\u4ea4\u7d66\u5f8c\u7e8c markdown plugin \u8655\u7406', () => {
    const input = 'line 1<br>line 2\n\n```md\nline 1<br>line 2\n```';
    const result = preprocessMarkdown(input);

    expect(result).toBe(input);
  });

  it('\u4e0d\u91cd\u5beb\u91d1\u984d dollar signs，\u4ea4\u7d66 remark parser \u5206\u985e', () => {
    const input = '**\u672c\u5b63\u71df\u6536**\u70ba US$1.25 \u5104，*\u53bb\u5e74*\u70ba US$0.98 \u5104。';

    expect(preprocessMarkdown(input)).toBe(input);
  });

  it('\u4fdd\u7559\u6709\u6548 inline/display math \u8207\u6578\u5b57\u958b\u982d\u7684 inline math', () => {
    const input = [
      'Formulas: $E=mc^2$, $1 + 2 = 3$, and $100 million$.',
      '',
      '$$',
      '\\sum_{i=1}^{n} i',
      '$$',
    ].join('\n');

    expect(preprocessMarkdown(input)).toBe(input);
  });

  it('\u4fdd\u7559 escaped dollar signs \u8207 code spans/fences \u7684\u539f\u59cb\u5167\u5bb9', () => {
    const input = [
      'Escaped \\$100 and \\$80.',
      '',
      '`$100 and $80`',
      '',
      '```text',
      '$100 and $80',
      '```',
    ].join('\n');

    expect(preprocessMarkdown(input)).toBe(input);
  });
});
