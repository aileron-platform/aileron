import yaml from 'js-yaml';

export type FrontmatterValue =
  | string
  | number
  | boolean
  | null
  | FrontmatterValue[]
  | { [key: string]: FrontmatterValue };

export interface MarkdownSegment {
  type: 'markdown';
  content: string;
}

export interface FrontmatterSegment {
  type: 'frontmatter';
  data: Record<string, FrontmatterValue>;
  raw: string;
}

export type ParsedMarkdownSegment = MarkdownSegment | FrontmatterSegment;

/**
 * Wraps bare \begin{...}...\end{...} LaTeX blocks with $$ delimiters
 * so remark-math can pick them up.
 */
export function preprocessLatex(text: string): string {
  return text.replace(
    /(?<!\$\$\s*)(\\begin\{[^}]+\}[\s\S]*?\\end\{[^}]+\})(?!\s*\$\$)/g,
    (_match, block: string) => `$$\n${block}\n$$`,
  );
}

const isFrontmatterRecord = (value: unknown): value is Record<string, FrontmatterValue> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

export function parseFrontmatterSegments(text: string): ParsedMarkdownSegment[] {
  const segments: ParsedMarkdownSegment[] = [];
  const frontmatterPattern = /(^|\n)---\n([\s\S]*?)\n---(?=\n|$)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = frontmatterPattern.exec(text)) !== null) {
    const prefix = match[1] ?? '';
    const rawBlock = match[2] ?? '';
    const blockStart = match.index + prefix.length;

    let parsed: unknown;
    try {
      parsed = yaml.load(rawBlock);
    } catch {
      continue;
    }

    if (!isFrontmatterRecord(parsed)) {
      continue;
    }

    if (blockStart > cursor) {
      segments.push({
        type: 'markdown',
        content: text.slice(cursor, blockStart),
      });
    }

    segments.push({
      type: 'frontmatter',
      data: parsed,
      raw: rawBlock,
    });

    cursor = blockStart + match[0].length - prefix.length;
  }

  if (cursor < text.length) {
    segments.push({
      type: 'markdown',
      content: text.slice(cursor),
    });
  }

  if (segments.length === 0) {
    return [{ type: 'markdown', content: text }];
  }

  return segments;
}

export function preprocessMarkdown(text: string): string {
  return preprocessLatex(text);
}
