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

type MicromarkCode = number | null;
type MicromarkState = (code: MicromarkCode) => MicromarkState | undefined;

interface MicromarkConstruct {
  name?: string;
  partial?: boolean;
  tokenize: (
    effects: MicromarkEffects,
    ok: MicromarkState,
    nok: MicromarkState,
  ) => MicromarkState;
}

interface MicromarkEffects {
  check: (
    construct: MicromarkConstruct,
    ok: MicromarkState,
    nok?: MicromarkState,
  ) => MicromarkState;
  consume: (code: MicromarkCode) => undefined;
  enter: (type: string) => unknown;
  exit: (type: string) => unknown;
}

interface RemarkParserData {
  micromarkExtensions?: unknown[];
}

interface RemarkParserProcessor {
  data: () => RemarkParserData;
}

const DOLLAR_SIGN = 36;
const decimalNumberPattern = /\p{Decimal_Number}/u;
const mathNumberPattern = /^\p{Decimal_Number}+(?:[.,]\p{Decimal_Number}+)?$/u;
const singleMathLetterPattern = /^\p{Letter}\p{Mark}*$/u;
const mathLettersPattern = /^(?:\p{Letter}\p{Mark}*)+$/u;
const mathOperatorPattern = /^[+\-*/=<>|&]$/u;
const compactMathAtomPattern = /^[\p{Letter}\p{Mark}\p{Decimal_Number}.^_{}()[\]+\-*/=<>|&]+$/u;
const explicitMathSyntaxPattern = /[\^_{}()[\]+\-*/=<>|&]/u;

function isClearlyInlineMath(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (/\\[A-Za-z]+/.test(trimmed)) return true;

  const tokens = trimmed.split(/\s+/u);
  const hasWhitespace = tokens.length > 1;
  const hasExplicitMathSyntax = tokens.some((token) => (
    mathOperatorPattern.test(token) || explicitMathSyntaxPattern.test(token)
  ));

  return tokens.every((token) => {
    if (
      mathNumberPattern.test(token)
      || singleMathLetterPattern.test(token)
      || mathOperatorPattern.test(token)
    ) {
      return true;
    }

    if (/^\*+.*\*+$/.test(token) || /^~+.*~+$/.test(token)) return false;
    if (!compactMathAtomPattern.test(token)) return false;
    if (explicitMathSyntaxPattern.test(token)) return true;
    if (/^[A-Za-z\d.]+$/.test(token)) {
      return !hasWhitespace || hasExplicitMathSyntax || /\d/.test(token);
    }
    if (mathLettersPattern.test(token)) {
      return !hasWhitespace || hasExplicitMathSyntax;
    }

    const letterCount = [...token.matchAll(/\p{Letter}\p{Mark}*/gu)]
      .reduce((count, match) => count + [...match[0]].length, 0);
    return /\p{Decimal_Number}/u.test(token) && letterCount <= 1;
  });
}

function isClearlyFollowingInlineMath(value: string): boolean {
  const trimmed = value.trim();
  if (!isClearlyInlineMath(trimmed)) return false;
  if (/\\[A-Za-z]+/.test(trimmed) || explicitMathSyntaxPattern.test(trimmed)) return true;

  const tokens = trimmed.split(/\s+/u);
  return tokens.every((token) => (
    mathNumberPattern.test(token) || singleMathLetterPattern.test(token)
  )) || /\p{Decimal_Number}/u.test(trimmed);
}

function isHorizontalSpace(code: MicromarkCode): boolean {
  return code === -2 || code === -1 || code === 32;
}

function isDecimalCode(code: MicromarkCode): boolean {
  return code !== null
    && code >= 0
    && decimalNumberPattern.test(String.fromCodePoint(code));
}

function codeToClassifierText(code: Exclude<MicromarkCode, null>): string {
  if (code === -5 || code === -4 || code === -3) return '\n';
  if (code === -2) return '\t';
  if (code === -1) return ' ';
  return String.fromCodePoint(code);
}

const currencyDollarLookahead: MicromarkConstruct = {
  partial: true,
  tokenize(effects, ok, nok) {
    let candidate = '';
    let candidateDollarRun = 0;
    let followingCandidate = '';
    let followingDollarRun = 0;

    return start;

    function start(code: MicromarkCode): MicromarkState | undefined {
      if (code !== DOLLAR_SIGN) return nok(code);
      effects.enter('currencyDollarLookahead');
      effects.consume(code);
      return amountStart;
    }

    function succeed(code: MicromarkCode): MicromarkState | undefined {
      effects.exit('currencyDollarLookahead');
      return ok(code);
    }

    function fail(code: MicromarkCode): MicromarkState | undefined {
      effects.exit('currencyDollarLookahead');
      return nok(code);
    }

    function amountStart(code: MicromarkCode): MicromarkState | undefined {
      if (isHorizontalSpace(code)) {
        candidate += codeToClassifierText(code);
        effects.consume(code);
        return amountStart;
      }
      if (isDecimalCode(code)) {
        candidate += codeToClassifierText(code);
        effects.consume(code);
        return candidateInside;
      }
      if (code === 46) {
        candidate += '.';
        effects.consume(code);
        return amountDecimalDigit;
      }
      return fail(code);
    }

    function amountDecimalDigit(code: MicromarkCode): MicromarkState | undefined {
      if (!isDecimalCode(code)) return fail(code);
      candidate += codeToClassifierText(code);
      effects.consume(code);
      return candidateInside;
    }

    function candidateInside(code: MicromarkCode): MicromarkState | undefined {
      if (code === null) return fail(code);
      if (code === DOLLAR_SIGN) {
        candidateDollarRun = 1;
        effects.consume(code);
        return candidateDollarSequence;
      }

      candidate += codeToClassifierText(code);
      effects.consume(code);
      return candidateInside;
    }

    function candidateDollarSequence(code: MicromarkCode): MicromarkState | undefined {
      if (code === DOLLAR_SIGN) {
        candidateDollarRun += 1;
        effects.consume(code);
        return candidateDollarSequence;
      }
      if (candidateDollarRun > 1) {
        candidate += '$'.repeat(candidateDollarRun);
        return candidateInside(code);
      }
      if (isClearlyInlineMath(candidate)) return fail(code);
      return afterCandidate(code);
    }

    function afterCandidate(code: MicromarkCode): MicromarkState | undefined {
      if (isHorizontalSpace(code)) {
        followingCandidate += codeToClassifierText(code);
        effects.consume(code);
        return afterCandidate;
      }
      if (isDecimalCode(code)) return succeed(code);
      if (code === 46) {
        followingCandidate += '.';
        effects.consume(code);
        return afterCandidateDecimal;
      }
      return followingInside(code);
    }

    function afterCandidateDecimal(code: MicromarkCode): MicromarkState | undefined {
      if (isDecimalCode(code)) return succeed(code);
      return followingInside(code);
    }

    function followingInside(code: MicromarkCode): MicromarkState | undefined {
      if (code === null) return fail(code);
      if (code === DOLLAR_SIGN) {
        followingDollarRun = 1;
        effects.consume(code);
        return followingDollarSequence;
      }

      followingCandidate += codeToClassifierText(code);
      effects.consume(code);
      return followingInside;
    }

    function followingDollarSequence(code: MicromarkCode): MicromarkState | undefined {
      if (code === DOLLAR_SIGN) {
        followingDollarRun += 1;
        effects.consume(code);
        return followingDollarSequence;
      }
      if (followingDollarRun > 1) {
        followingCandidate += '$'.repeat(followingDollarRun);
        return followingInside(code);
      }
      return isClearlyFollowingInlineMath(followingCandidate) ? succeed(code) : fail(code);
    }
  },
};

const currencyDollarConstruct: MicromarkConstruct = {
  name: 'currencyDollar',
  tokenize(effects, ok, nok) {
    return effects.check(currencyDollarLookahead, consumeAsText, nok);

    function consumeAsText(code: MicromarkCode): MicromarkState | undefined {
      if (code !== DOLLAR_SIGN) return nok(code);
      effects.enter('data');
      effects.consume(code);
      effects.exit('data');
      return ok;
    }
  },
};

/**
 * Runs ahead of remark-math's single-dollar tokenizer. When a numeric amount
 * prefix would consume prose or the opening delimiter of a later real formula,
 * it tokenizes only that dollar sign as text and lets normal Markdown resume.
 * Register this plugin after remark-math so micromark gives it precedence.
 */
export function remarkCurrencyDollars(this: RemarkParserProcessor): undefined {
  const data = this.data();
  const extensions = data.micromarkExtensions
    || (data.micromarkExtensions = []);

  extensions.push({ text: { [DOLLAR_SIGN]: currencyDollarConstruct } });
  return undefined;
}

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
