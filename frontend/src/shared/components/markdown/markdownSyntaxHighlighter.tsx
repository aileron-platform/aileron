import React from 'react';
import type { SyntaxHighlighterProps } from 'react-syntax-highlighter';
import { useResolvedTheme } from '@/shared/contexts/ResolvedThemeContext';

export type SyntaxHighlighterBundle = {
  SyntaxHighlighter: React.ComponentType<SyntaxHighlighterProps>;
  oneDark: NonNullable<SyntaxHighlighterProps['style']>;
  oneLight: NonNullable<SyntaxHighlighterProps['style']>;
};

let syntaxHighlighterPromise: Promise<SyntaxHighlighterBundle> | null = null;

export const loadMarkdownSyntaxHighlighter = async (): Promise<SyntaxHighlighterBundle> => {
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

export interface MarkdownSyntaxHighlighterProps {
  code: string;
  language?: string;
  className?: string;
  showLineNumbers?: boolean;
  startingLineNumber?: number;
  preTag?: 'div' | 'pre';
  customStyle?: React.CSSProperties;
  lineNumberStyle?: React.CSSProperties;
}

const fallbackStyle: React.CSSProperties = {
  margin: 0,
  padding: 0,
  background: 'transparent',
  borderRadius: 0,
  fontSize: 'inherit',
  lineHeight: 'inherit',
};

const renderFallbackCode = (
  code: string,
  className: string | undefined,
  preTag: string,
  customStyle: React.CSSProperties | undefined,
) => {
  if (preTag === 'pre') {
    return (
      <pre style={{ ...fallbackStyle, ...customStyle }}>
        <code className={className}>{code}</code>
      </pre>
    );
  }

  return (
    <code className={className}>
      {code}
    </code>
  );
};

export const MarkdownSyntaxHighlighter: React.FC<MarkdownSyntaxHighlighterProps> = ({
  code,
  language,
  className,
  showLineNumbers,
  startingLineNumber,
  preTag = 'div',
  customStyle,
  lineNumberStyle,
}) => {
  const resolvedTheme = useResolvedTheme();
  const isDark = resolvedTheme === 'dark';
  const [bundle, setBundle] = React.useState<SyntaxHighlighterBundle | null>(null);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    if (!language) {
      return;
    }

    let isMounted = true;

    loadMarkdownSyntaxHighlighter()
      .then((loadedBundle) => {
        if (isMounted) {
          setBundle(loadedBundle);
          setFailed(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setBundle(null);
          setFailed(true);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [language]);

  if (!language || failed || !bundle) {
    return renderFallbackCode(code, className, preTag, customStyle);
  }

  const { SyntaxHighlighter, oneDark, oneLight } = bundle;

  return (
    <SyntaxHighlighter
      style={isDark ? oneDark : oneLight}
      language={language}
      showLineNumbers={showLineNumbers}
      startingLineNumber={startingLineNumber}
      PreTag={preTag}
      customStyle={{ ...fallbackStyle, ...customStyle }}
      lineNumberStyle={lineNumberStyle}
    >
      {code}
    </SyntaxHighlighter>
  );
};
