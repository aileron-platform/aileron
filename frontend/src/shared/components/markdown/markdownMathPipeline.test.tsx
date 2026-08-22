import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { describe, expect, it, vi } from 'vitest';
import { preprocessMarkdown, remarkCurrencyDollars } from './markdownPreprocess';

function renderMarkdown(content: string): string {
  return renderToStaticMarkup(
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath, remarkCurrencyDollars]}
      rehypePlugins={[rehypeKatex]}
    >
      {preprocessMarkdown(content)}
    </ReactMarkdown>,
  );
}

describe('Markdown math pipeline', () => {
  it('keeps financial prose out of KaTeX without unicodeTextInMathMode warnings', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    try {
      const html = renderMarkdown(
        '**\u672c\u5b63\u71df\u6536**\u70ba US$1.25 \u5104，*\u53bb\u5e74*\u70ba US$0.98 \u5104。',
      );

      expect(html).toContain('<strong>\u672c\u5b63\u71df\u6536</strong>\u70ba US$1.25 \u5104');
      expect(html).toContain('<em>\u53bb\u5e74</em>\u70ba US$0.98 \u5104');
      expect(html).not.toContain('class="katex"');
      expect(warn.mock.calls.flat().join(' ')).not.toContain('unicodeTextInMathMode');
    } finally {
      warn.mockRestore();
    }
  });

  it('keeps no-space CJK currency prose visible and out of KaTeX', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    try {
      const html = renderMarkdown('\u71df\u6536$100\u5104\u5143，\u6210\u672c$80\u5104\u5143；US$60\u5104\u5143、\u53bb\u5e74US$50\u5104\u5143。');

      expect(html).toContain('\u71df\u6536$100\u5104\u5143，\u6210\u672c$80\u5104\u5143');
      expect(html).toContain('US$60\u5104\u5143、\u53bb\u5e74US$50\u5104\u5143');
      expect(html).not.toContain('class="katex"');
      expect(warn.mock.calls.flat().join(' ')).not.toContain('unicodeTextInMathMode');
    } finally {
      warn.mockRestore();
    }
  });

  it.each([
    ['ideographic punctuation', '\u71df\u6536$100\u5104、\u6210\u672c$80\u5104。'],
    ['yuan units', '\u552e\u50f9$100\u5143，\u6210\u672c$80\u5143。'],
    ['space-separated comparison', '\u71df\u6536US$100\u5104 \u53bb\u5e74US$80\u5104'],
  ])('keeps minimal unit currency prose out of KaTeX: %s', (_case, content) => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    try {
      const html = renderMarkdown(content);

      expect(html).toContain(content);
      expect(html).not.toContain('class="katex"');
      expect(warn.mock.calls.flat().join(' ')).not.toContain('unicodeTextInMathMode');
    } finally {
      warn.mockRestore();
    }
  });

  it('realigns a currency marker before genuine inline math', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    try {
      const html = renderMarkdown('\u6210\u672cUS$100\u5104\u5143，\u516c\u5f0f $2x + 1$。');

      expect(html).toContain('\u6210\u672cUS$100\u5104\u5143，\u516c\u5f0f ');
      expect(html.match(/class="katex"/g)).toHaveLength(1);
      expect(html).toContain('<annotation encoding="application/x-tex">2x + 1</annotation>');
      expect(warn.mock.calls.flat().join(' ')).not.toContain('unicodeTextInMathMode');
    } finally {
      warn.mockRestore();
    }
  });

  it('preserves escaped dollars and dollar signs inside code', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const content = [
      'Escaped \\$100 and \\$80. Inline `$100\u5104\u5143、$80\u5104\u5143`.',
      '',
      '```text',
      '$100\u5104\u5143、$80\u5104\u5143',
      '```',
    ].join('\n');

    try {
      const html = renderMarkdown(content);

      expect(html).toContain('Escaped $100 and $80.');
      expect(html).toContain('<code>$100\u5104\u5143、$80\u5104\u5143</code>');
      expect(html).not.toContain('class="katex"');
      expect(warn.mock.calls.flat().join(' ')).not.toContain('unicodeTextInMathMode');
    } finally {
      warn.mockRestore();
    }
  });

  it('preserves explicitly delimited inline math even when it resembles prose', () => {
    const html = renderMarkdown('Values $100 million$, $2x$, and $x$ remain math.');

    expect(html.match(/class="katex"/g)).toHaveLength(3);
  });

  it('does not inspect dollar signs in link destinations as math', () => {
    const html = renderMarkdown('[Pricing](https://example.com/$100?compare=$80)');

    expect(html).toContain('href="https://example.com/$100?compare=$80"');
    expect(html).not.toContain('class="katex"');
  });

  it('still renders inline, display, and bare begin/end math with real KaTeX', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const content = [
      'Inline $E=mc^2$.',
      '',
      '$$',
      '\\sum_{i=1}^{n} i',
      '$$',
      '',
      'Bare environment:',
      '',
      '\\begin{aligned}',
      'a &= b \\\\',
      'c &= d',
      '\\end{aligned}',
    ].join('\n');

    try {
      const html = renderMarkdown(content);

      expect(html.match(/class="katex"/g)).toHaveLength(3);
      expect(html).toContain('<annotation encoding="application/x-tex">E=mc^2</annotation>');
      expect(warn.mock.calls.flat().join(' ')).not.toContain('unicodeTextInMathMode');
    } finally {
      warn.mockRestore();
    }
  });
});
