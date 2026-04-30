/**
 * ReadWidget - file read display with Markdown parsing and code highlighting.
 */

import React, { useEffect, useMemo } from 'react';
import { FileText, Maximize2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';
import { useApp } from '@/app/providers/AppProvider';

type SyntaxHighlighterBundle = {
  SyntaxHighlighter: React.ComponentType<any>;
  oneDark: any;
  oneLight: any;
};

let syntaxHighlighterPromise: Promise<SyntaxHighlighterBundle> | null = null;

const loadSyntaxHighlighter = async (): Promise<SyntaxHighlighterBundle> => {
  syntaxHighlighterPromise ??= Promise.all([
    import('react-syntax-highlighter'),
    import('react-syntax-highlighter/dist/esm/styles/prism'),
  ]).then(([syntaxModule, stylesModule]) => ({
    SyntaxHighlighter: syntaxModule.Prism,
    oneDark: stylesModule.oneDark,
    oneLight: stylesModule.oneLight,
  }));
  return syntaxHighlighterPromise;
};

interface LazySyntaxHighlighterProps {
  children: string;
  isDark: boolean;
  language: string;
  showLineNumbers?: boolean;
  startingLineNumber?: number;
  PreTag?: string;
  customStyle?: React.CSSProperties;
  lineNumberStyle?: React.CSSProperties;
}

const LazySyntaxHighlighter: React.FC<LazySyntaxHighlighterProps> = ({
  children,
  isDark,
  language,
  showLineNumbers,
  startingLineNumber,
  PreTag,
  customStyle,
  lineNumberStyle,
}) => {
  const [bundle, setBundle] = React.useState<SyntaxHighlighterBundle | null>(null);

  useEffect(() => {
    let isMounted = true;

    loadSyntaxHighlighter()
      .then((loadedBundle) => {
        if (isMounted) {
          setBundle(loadedBundle);
        }
      })
      .catch(() => {
        if (isMounted) {
          setBundle(null);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  if (!bundle) {
    return (
      <pre style={customStyle}>
        <code>{children}</code>
      </pre>
    );
  }

  const { SyntaxHighlighter, oneDark, oneLight } = bundle;

  return (
    <SyntaxHighlighter
      style={isDark ? oneDark : oneLight}
      language={language}
      showLineNumbers={showLineNumbers}
      startingLineNumber={startingLineNumber}
      PreTag={PreTag}
      customStyle={customStyle}
      lineNumberStyle={lineNumberStyle}
    >
      {children}
    </SyntaxHighlighter>
  );
};

// Resolve a syntax highlighter language from the file path.
const getLanguageFromPath = (filePath: string): string => {
  const ext = filePath.split('.').pop()?.toLowerCase() || '';
  const languageMap: Record<string, string> = {
    js: 'javascript',
    mjs: 'javascript',
    cjs: 'javascript',
    jsx: 'jsx',
    ts: 'typescript',
    tsx: 'tsx',
    py: 'python',
    rb: 'ruby',
    go: 'go',
    rs: 'rust',
    java: 'java',
    kt: 'kotlin',
    swift: 'swift',
    c: 'c',
    cpp: 'cpp',
    h: 'c',
    hpp: 'cpp',
    cs: 'csharp',
    php: 'php',
    html: 'html',
    htm: 'html',
    css: 'css',
    scss: 'scss',
    sass: 'sass',
    less: 'less',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    xml: 'xml',
    sql: 'sql',
    sh: 'bash',
    bash: 'bash',
    zsh: 'bash',
    ps1: 'powershell',
    dockerfile: 'dockerfile',
    md: 'markdown',
    markdown: 'markdown',
    toml: 'toml',
    ini: 'ini',
    graphql: 'graphql',
    gql: 'graphql',
  };
  return languageMap[ext] || 'text';
};

// Detect Markdown file extensions.
const isMarkdownFile = (filePath: string): boolean => {
  const ext = filePath.split('.').pop()?.toLowerCase() || '';
  return ext === 'md' || ext === 'markdown';
};

// Markdown renderer configuration.
const createMarkdownComponents = (isDark: boolean): Components => ({
  p: ({ children }) => (
    <p className="mb-4 break-words text-sm leading-relaxed">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-4 ml-6 list-disc break-words text-sm leading-relaxed space-y-2">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-4 ml-6 list-decimal break-words text-sm leading-relaxed space-y-2">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="break-words text-sm leading-relaxed">{children}</li>
  ),
  h1: ({ children }) => (
    <h1 className="mb-4 mt-6 text-xl font-bold first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-3 mt-5 text-lg font-semibold first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-4 text-base font-semibold first:mt-0">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="mb-2 mt-3 text-sm font-semibold first:mt-0">{children}</h4>
  ),
  hr: () => <hr className="my-6 border-border" />,
  blockquote: ({ children }) => (
    <blockquote className="mb-4 border-l-4 border-border pl-4 text-sm italic text-muted-foreground">{children}</blockquote>
  ),
  pre: ({ children }) => (
    <div className="mb-4 overflow-hidden rounded-md">{children}</div>
  ),
  code: ({ className, children, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '');
    const isInline = !match && !className;

    if (isInline) {
      return (
        <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono" {...props}>
          {children}
        </code>
      );
    }

    return (
      <LazySyntaxHighlighter
        isDark={isDark}
        language={match ? match[1] : 'text'}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: '0.375rem',
          fontSize: '0.75rem',
        }}
      >
        {String(children).replace(/\n$/, '')}
      </LazySyntaxHighlighter>
    );
  },
  a: ({ href, children }) => (
    <a href={href} className="text-blue-600 hover:underline dark:text-blue-400" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="mb-4 overflow-x-auto">
      <table className="w-full border-collapse border border-border text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-border bg-muted px-3 py-2 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-3 py-2">{children}</td>
  ),
});

export const ReadWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const { t } = useI18n();
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const { state } = useApp();
  const isDark = state.ui.currentTheme === 'dark';

  const filePath = input?.file_path || '';
  const content = typeof output === 'string' ? output : '';
  const isMarkdown = isMarkdownFile(filePath);
  const language = getLanguageFromPath(filePath);

  // Parse Claude's numbered read output and strip line number prefixes.
  const parseContent = (rawContent: string) => {
    const lines = rawContent.split('\n');
    const codeLines: string[] = [];
    let minLineNumber = 1;

    const hasLineNumbers = lines.some(line => /^\s*\d+→/.test(line));
    if (!hasLineNumbers) return { code: rawContent, startLine: 1 };

    for (const line of lines) {
      const match = line.match(/^\s*(\d+)→(.*)$/);
      if (match) {
        if (minLineNumber === 1) minLineNumber = parseInt(match[1], 10);
        codeLines.push(match[2]);
      } else {
        codeLines.push(line);
      }
    }
    return { code: codeLines.join('\n'), startLine: minLineNumber };
  };

  const { code, startLine } = parseContent(content);
  const lines = code.split('\n');
  const PREVIEW_LINES = 10;

  // Memoize Markdown components to avoid unnecessary recreation.
  const markdownComponents = useMemo(() => createMarkdownComponents(isDark), [isDark]);

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  // Render non-Markdown code content.
  const renderCodeContent = (previewOnly: boolean = false) => {
    const displayLines = previewOnly ? lines.slice(0, PREVIEW_LINES) : lines;
    const displayCode = displayLines.join('\n');

    return (
      <LazySyntaxHighlighter
        isDark={isDark}
        language={language}
        showLineNumbers={true}
        startingLineNumber={startLine}
        customStyle={{
          margin: 0,
          padding: '0.75rem',
          fontSize: '0.75rem',
          lineHeight: '1.5',
          borderRadius: 0,
          background: isDark ? '#1e1e1e' : '#f8f8f8',
        }}
        lineNumberStyle={{
          minWidth: '2.5em',
          paddingRight: '1em',
          color: isDark ? '#6b7280' : '#9ca3af',
          userSelect: 'none',
        }}
      >
        {displayCode}
      </LazySyntaxHighlighter>
    );
  };

  // Render Markdown content.
  const renderMarkdownContent = (markdownContent: string, className: string = '') => {
    return (
      <div className={`prose prose-sm dark:prose-invert max-w-none p-4 ${className}`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {markdownContent}
        </ReactMarkdown>
      </div>
    );
  };

  return (
    <>
      <div className="bg-gray-50 dark:bg-zinc-900 overflow-hidden">
        <div className="overflow-x-auto max-h-80">
          {isMarkdown ? (
            // Markdown preview.
            <div className="text-gray-900 dark:text-zinc-100">
              {renderMarkdownContent(code, 'text-xs')}
            </div>
          ) : (
            // Code preview.
            renderCodeContent(true)
          )}
        </div>
        {(isMarkdown ? code.length > 500 : lines.length > PREVIEW_LINES) && (
          <div className="px-4 py-2 bg-gray-100/50 dark:bg-zinc-800/50 border-t border-gray-200 dark:border-zinc-700 text-center">
            <button
              onClick={() => setShowFullscreen(true)}
              className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
            >
              <Maximize2 className="h-3 w-3" />
              {isMarkdown
                ? t('workspace.chat.widgets.agentTools.viewFullContentPlain')
                : t('workspace.chat.widgets.agentTools.viewFullContent', { count: lines.length })}
            </button>
          </div>
        )}
      </div>

      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <FileText className="h-4 w-4" />
              {filePath}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto bg-gray-50 dark:bg-zinc-900 rounded">
            {isMarkdown ? (
              // Fullscreen Markdown.
              <div className="text-gray-900 dark:text-zinc-100">
                {renderMarkdownContent(code)}
              </div>
            ) : (
              // Fullscreen code.
              renderCodeContent(false)
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ReadWidget;
