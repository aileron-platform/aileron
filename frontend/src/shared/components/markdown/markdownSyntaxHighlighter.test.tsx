import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ResolvedThemeProvider } from '@/shared/contexts/ResolvedThemeContext';
import { MarkdownSyntaxHighlighter } from './markdownSyntaxHighlighter';

vi.mock('react-syntax-highlighter', () => ({
  Prism: ({
    children,
    language,
    showLineNumbers,
    startingLineNumber,
    PreTag = 'pre',
    customStyle,
    style: syntaxTheme,
  }: {
    children: string;
    language?: string;
    showLineNumbers?: boolean;
    startingLineNumber?: number;
    PreTag?: string;
    customStyle?: React.CSSProperties;
    style?: { name?: string };
  }) => {
    const Tag = PreTag as 'pre' | 'div';
    return (
      <Tag
        data-testid="syntax-highlighter"
        data-syntax-theme={syntaxTheme?.name}
        data-language={language}
        data-show-line-numbers={showLineNumbers ? 'true' : 'false'}
        data-starting-line-number={startingLineNumber}
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

describe('MarkdownSyntaxHighlighter', () => {
  it('loads Prism and renders typed code through the syntax highlighter', async () => {
    render(<MarkdownSyntaxHighlighter code="const value = 1;" language="typescript" />);

    expect(screen.getByText('const value = 1;')).toBeTruthy();
    const highlighted = await screen.findByTestId('syntax-highlighter');
    expect(highlighted.getAttribute('data-language')).toBe('typescript');
    expect(highlighted).toHaveAttribute('data-syntax-theme', 'light');
  });

  it('uses the dark syntax theme from the shared resolved-theme context', async () => {
    render(
      <ResolvedThemeProvider value="dark">
        <MarkdownSyntaxHighlighter code="const value = 1;" language="typescript" />
      </ResolvedThemeProvider>,
    );

    expect(await screen.findByTestId('syntax-highlighter')).toHaveAttribute(
      'data-syntax-theme',
      'dark',
    );
  });

  it('renders plain code when no language is provided', () => {
    render(<MarkdownSyntaxHighlighter code="plain text" />);

    expect(screen.getByText('plain text').tagName).toBe('CODE');
    expect(screen.queryByTestId('syntax-highlighter')).toBeNull();
  });

  it('wraps fallback code when preTag and customStyle are provided', () => {
    render(
      <MarkdownSyntaxHighlighter
        code="plain text"
        preTag="pre"
        customStyle={{ padding: '12px' }}
      />,
    );

    const pre = screen.getByText('plain text').closest('pre');
    expect(pre).not.toBeNull();
    expect(pre).toHaveStyle({ padding: '12px' });
  });
});
