import { describe, it, expect } from 'vitest';
import { preprocessLatex } from './markdownPreprocess';

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
