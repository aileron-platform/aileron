import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MarkdownRenderer } from './MarkdownRenderer';

vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));

describe('MarkdownRenderer', () => {
  it('AI CHAT 路徑使用 chat variant 的共用 markdown renderer', () => {
    const { container } = render(<MarkdownRenderer content="**chat**" />);

    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('prose');
    expect(container.querySelector('strong')).not.toBeNull();
  });

  it('渲染表格時只產生單一外框容器', () => {
    const content = '| A | B |\n|---|---|\n| 1 | 2 |';
    const { container } = render(<MarkdownRenderer content={content} />);

    expect(container.querySelectorAll('.markdown-table-shell')).toHaveLength(1);
    expect(container.querySelectorAll('table')).toHaveLength(1);
    expect(container.querySelector('table')?.className).toContain('border-separate');
  });
});
