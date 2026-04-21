import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MarkdownContent } from './MarkdownContent';

// rehype-katex 在 jsdom 可能產生警告，mock 掉避免干擾測試輸出
vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));

describe('MarkdownContent', () => {
  it('空 content 不渲染任何元素（回傳 null）', () => {
    const { container } = render(<MarkdownContent content="" />);
    expect(container.firstChild).toBeNull();
  });

  it('根容器包含 prose class（default variant）', () => {
    const { container } = render(<MarkdownContent content="Hello" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('prose');
  });

  it('compact variant 根容器包含 prose class', () => {
    const { container } = render(<MarkdownContent content="Hello" variant="compact" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('prose');
  });

  it('渲染粗體', () => {
    render(<MarkdownContent content="**粗體文字**" />);
    expect(screen.getByText('粗體文字').tagName).toBe('STRONG');
  });

  it('渲染斜體', () => {
    render(<MarkdownContent content="*斜體文字*" />);
    expect(screen.getByText('斜體文字').tagName).toBe('EM');
  });

  it('渲染刪除線（GFM）', () => {
    render(<MarkdownContent content="~~刪除線~~" />);
    expect(screen.getByText('刪除線').tagName).toBe('DEL');
  });

  it('渲染 inline code', () => {
    render(<MarkdownContent content="`someCode`" />);
    const code = screen.getByText('someCode');
    expect(code.tagName).toBe('CODE');
  });

  it('渲染 code block（pre > code）', () => {
    const { container } = render(<MarkdownContent content={'```\nconst x = 1;\n```'} />);
    const pre = container.querySelector('pre');
    expect(pre).not.toBeNull();
    expect(pre?.querySelector('code')).not.toBeNull();
  });

  it('渲染 GFM 表格', () => {
    const tableContent = '| A | B |\n|---|---|\n| 1 | 2 |';
    const { container } = render(<MarkdownContent content={tableContent} />);
    expect(container.querySelector('table')).not.toBeNull();
    expect(container.querySelector('th')).not.toBeNull();
    expect(container.querySelector('td')).not.toBeNull();
  });

  it('GFM 表格有正確的欄位內容', () => {
    const tableContent = '| Name | Age |\n|------|-----|\n| Alice | 30 |';
    render(<MarkdownContent content={tableContent} />);
    expect(screen.getByText('Name')).toBeTruthy();
    expect(screen.getByText('Alice')).toBeTruthy();
  });

  it('渲染標題', () => {
    const { container } = render(<MarkdownContent content={`# 標題一\n\n## 標題二`} />);
    expect(container.querySelector('h1')).not.toBeNull();
    expect(container.querySelector('h2')).not.toBeNull();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('標題一');
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('標題二');
  });

  it('渲染無序列表', () => {
    const { container } = render(<MarkdownContent content={`- item 1\n- item 2`} />);
    expect(container.querySelector('ul')).not.toBeNull();
    expect(screen.getByText('item 1')).toBeTruthy();
    expect(screen.getByText('item 2')).toBeTruthy();
  });

  it('渲染連結', () => {
    const { container } = render(<MarkdownContent content="[Link](https://example.com)" />);
    const a = container.querySelector('a');
    expect(a).not.toBeNull();
    expect(a?.getAttribute('href')).toBe('https://example.com');
  });

  it('className prop 附加到根容器', () => {
    const { container } = render(<MarkdownContent content="Hello" className="custom-class" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('custom-class');
  });

  it('將 YAML frontmatter 呈現為結構化區塊', () => {
    const content = `---
name: generate-contracts
description: 依據 OpenSpec change 的 delta spec 內容產生 contract
metadata:
  author: openspec
  version: "1.0"
---`;

    const { container } = render(<MarkdownContent content={content} />);
    expect(container.querySelector('pre code')).toBeNull();
    expect(screen.getByText('generate-contracts')).toBeTruthy();
    expect(screen.getByText('openspec')).toBeTruthy();
    expect(screen.getByText('1.0')).toBeTruthy();
  });

  it('在中段 frontmatter 後仍繼續渲染 markdown 正文', () => {
    const content = `<skill>
<name>openspec-ff-change</name>
---
name: openspec-ff-change
metadata:
  author: openspec
---

## Steps`;

    render(<MarkdownContent content={content} />);
    expect(screen.getByText('openspec-ff-change')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Steps');
  });
});
