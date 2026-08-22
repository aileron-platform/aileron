import type React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MarkdownContent } from './MarkdownContent';

vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));
vi.mock('react-syntax-highlighter', () => ({
  Prism: ({
    children,
    language,
    PreTag = 'div',
    customStyle,
  }: {
    children: string;
    language?: string;
    PreTag?: string;
    customStyle?: React.CSSProperties;
  }) => {
    const Tag = PreTag as 'pre' | 'div';
    return (
      <Tag
        data-testid="syntax-highlighter"
        data-language={language}
        style={customStyle}
      >
        <code>{children}</code>
      </Tag>
    );
  },
}));

vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  oneDark: { name: 'dark' },
  oneLight: { name: 'light' },
}));

describe('MarkdownContent', () => {
  it('does not render empty content', () => {
    const { container } = render(<MarkdownContent content="" />);
    expect(container.firstChild).toBeNull();
  });

  it('applies prose class to the default variant root', () => {
    const { container } = render(<MarkdownContent content="Hello" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('prose');
  });

  it('applies prose class to the compact variant root', () => {
    const { container } = render(<MarkdownContent content="Hello" variant="compact" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('prose');
  });

  it('applies prose class to the chat variant root', () => {
    const { container } = render(<MarkdownContent content="Hello" variant="chat" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('prose');
  });

  it('renders bold text', () => {
    render(<MarkdownContent content="**Bold text**" />);
    expect(screen.getByText('Bold text').tagName).toBe('STRONG');
  });

  it('renders italic text', () => {
    render(<MarkdownContent content="*Italic text*" />);
    expect(screen.getByText('Italic text').tagName).toBe('EM');
  });

  it('renders GFM strikethrough text', () => {
    render(<MarkdownContent content="~~Deleted text~~" />);
    expect(screen.getByText('Deleted text').tagName).toBe('DEL');
  });

  it('renders inline code', () => {
    render(<MarkdownContent content="`someCode`" />);
    const code = screen.getByText('someCode');
    expect(code.tagName).toBe('CODE');
  });

  it('renders code blocks', () => {
    const { container } = render(<MarkdownContent content={'```\nconst x = 1;\n```'} />);
    const pre = container.querySelector('pre');
    expect(pre).not.toBeNull();
    expect(pre?.querySelector('code')).not.toBeNull();
  });

  it('renders fenced code without an AppProvider', () => {
    const { container } = render(
      <MarkdownContent content={'```typescript\nconst value = 1;\n```'} />,
    );

    expect(container.querySelector('pre')).not.toBeNull();
    expect(screen.getByText(/const value = 1/)).toBeTruthy();
  });

  it('renders typed fenced code through the syntax highlighter without nested pre elements', async () => {
    const { container } = render(
      <MarkdownContent content={'```typescript\nconst value = 1;\n```'} />,
    );

    expect(screen.getByText(/const value = 1/)).toBeTruthy();
    const highlighted = await screen.findByTestId('syntax-highlighter');
    expect(highlighted.getAttribute('data-language')).toBe('typescript');
    expect(container.querySelectorAll('pre')).toHaveLength(1);
    expect(container.querySelector('pre')?.className).toContain('max-h-[70vh]');
  });

  it('keeps inline code out of the block highlighter', () => {
    render(<MarkdownContent content={'Use `inlineCode` here'} />);

    expect(screen.getByText('inlineCode').tagName).toBe('CODE');
    expect(screen.queryByTestId('syntax-highlighter')).toBeNull();
  });

  it('renders fenced code without a language as plain fallback', () => {
    const { container } = render(<MarkdownContent content={'```\nplain text\n```'} />);

    expect(screen.getByText(/plain text/)).toBeTruthy();
    expect(screen.queryByTestId('syntax-highlighter')).toBeNull();
    expect(container.querySelectorAll('pre')).toHaveLength(1);
  });

  it('passes unknown fenced languages to Prism without maintaining a supported list', async () => {
    render(<MarkdownContent content={'```madeuplang\nvalue\n```'} />);

    const highlighted = await screen.findByTestId('syntax-highlighter');
    expect(highlighted.getAttribute('data-language')).toBe('madeuplang');
    expect(screen.getByText(/value/)).toBeTruthy();
  });

  it('renders GFM tables', () => {
    const tableContent = '| A | B |\n|---|---|\n| 1 | 2 |';
    const { container } = render(<MarkdownContent content={tableContent} />);
    expect(container.querySelector('table')).not.toBeNull();
    expect(container.querySelector('th')).not.toBeNull();
    expect(container.querySelector('td')).not.toBeNull();
  });

  it('renders GFM table cell content', () => {
    const tableContent = '| Name | Age |\n|------|-----|\n| Alice | 30 |';
    render(<MarkdownContent content={tableContent} />);
    expect(screen.getByText('Name')).toBeTruthy();
    expect(screen.getByText('Alice')).toBeTruthy();
  });

  it('renders headings', () => {
    const { container } = render(<MarkdownContent content={`# Heading one\n\n## Heading two`} />);
    expect(container.querySelector('h1')).not.toBeNull();
    expect(container.querySelector('h2')).not.toBeNull();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Heading one');
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Heading two');
  });

  it('renders unordered lists', () => {
    const { container } = render(<MarkdownContent content={`- item 1\n- item 2`} />);
    expect(container.querySelector('ul')).not.toBeNull();
    expect(screen.getByText('item 1')).toBeTruthy();
    expect(screen.getByText('item 2')).toBeTruthy();
  });

  it('renders links', () => {
    const { container } = render(<MarkdownContent content="[Link](https://example.com)" />);
    const a = container.querySelector('a');
    expect(a).not.toBeNull();
    expect(a?.getAttribute('href')).toBe('https://example.com');
  });

  it('adds safe new-window attributes to external links', () => {
    const { container } = render(<MarkdownContent content="[Link](https://example.com)" />);
    const a = container.querySelector('a');
    expect(a?.getAttribute('target')).toBe('_blank');
    expect(a?.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('leaves internal links in the same window and calls the click handler', () => {
    const onLinkClick = vi.fn((_: string, event: React.MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault();
    });
    const { container } = render(
      <MarkdownContent
        content="[Config](../../schemas/spec-driven-api/standards/configuration-standards.md)"
        onLinkClick={onLinkClick}
      />,
    );

    const a = container.querySelector('a');
    expect(a?.getAttribute('target')).toBeNull();
    expect(a?.getAttribute('rel')).toBeNull();

    fireEvent.click(screen.getByRole('link', { name: 'Config' }));

    expect(onLinkClick).toHaveBeenCalledWith(
      '../../schemas/spec-driven-api/standards/configuration-standards.md',
      expect.anything(),
    );
  });

  it('appends className to the root element', () => {
    const { container } = render(<MarkdownContent content="Hello" className="custom-class" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('custom-class');
  });

  it('renders YAML frontmatter as a structured block', () => {
    const content = `---
name: generate-contracts
description: Generate example artifacts
metadata:
  author: example
  version: "1.0"
---`;

    const { container } = render(<MarkdownContent content={content} />);
    expect(container.querySelector('pre code')).toBeNull();
    expect(screen.getByText('generate-contracts')).toBeTruthy();
    expect(screen.getByText('example')).toBeTruthy();
    expect(screen.getByText('1.0')).toBeTruthy();
  });

  it('continues rendering markdown content after embedded frontmatter', () => {
    const content = `<skill>
<name>sample-skill-update</name>
---
name: sample-skill-update
metadata:
  author: example
---

## Steps`;

    render(<MarkdownContent content={content} />);
    expect(screen.getByText('sample-skill-update')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Steps');
  });

  it('renders <br> and <br/> as line breaks', () => {
    const { container, rerender } = render(<MarkdownContent content="line 1<br>line 2" />);
    expect(container.querySelectorAll('br')).toHaveLength(1);

    rerender(<MarkdownContent content="line 1<br/>line 2" />);
    expect(container.querySelectorAll('br')).toHaveLength(1);
  });

  it('preserves table structure and renders <br> in table cells', () => {
    const content = `| A | B |\n|---|---|\n| 1 | line 1<br>line 2 |`;
    const { container } = render(<MarkdownContent content={content} />);

    expect(container.querySelector('table')).not.toBeNull();
    expect(container.querySelectorAll('td')).toHaveLength(2);
    expect(container.querySelectorAll('br')).toHaveLength(1);
  });

  it('creates one table shell and preserves inner grid lines', () => {
    const content = '| A | B |\n|---|---|\n| 1 | 2 |';
    const { container } = render(<MarkdownContent content={content} variant="chat" />);
    const thClasses = container.querySelector('th')?.className.split(/\s+/) ?? [];
    const tdClasses = container.querySelector('td')?.className.split(/\s+/) ?? [];

    const shells = container.querySelectorAll('.markdown-table-shell');
    expect(shells).toHaveLength(1);
    expect(container.querySelector('table')?.className).toContain('border-separate');
    expect(container.querySelector('table')?.className).toContain('my-0');
    expect(thClasses).not.toContain('border');
    expect(tdClasses).not.toContain('border');
    expect(thClasses).toContain('border-b');
    expect(tdClasses).toContain('border-r');
  });
});
