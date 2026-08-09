export interface MarkdownSelection {
  selectionStart: number;
  selectionEnd: number;
}

export interface MarkdownEditResult extends MarkdownSelection {
  value: string;
}

export type MarkdownToolbarCommand =
  | 'bold'
  | 'italic'
  | 'link'
  | 'code'
  | 'image'
  | 'quote'
  | 'unorderedList'
  | 'orderedList';

export interface MarkdownToolbarCommandInput extends MarkdownSelection {
  text: string;
  command: MarkdownToolbarCommand;
  placeholder: string;
}

const unorderedMarkerPattern = /^(\s*)([-+*]\s+)(.*)$/;
const orderedMarkerPattern = /^(\s*)(\d+[.)]\s+)(.*)$/;
const quotePattern = /^(\s*)>\s?(.*)$/;

const getSelectedText = (text: string, selectionStart: number, selectionEnd: number, placeholder: string) => (
  selectionStart === selectionEnd ? placeholder : text.slice(selectionStart, selectionEnd)
);

const applySurroundingCommand = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  prefix: string,
  suffix: string,
  placeholder: string
): MarkdownEditResult => {
  const hasSelection = selectionStart !== selectionEnd;
  const selectedText = getSelectedText(text, selectionStart, selectionEnd, placeholder);
  const isExactWrapped =
    selectedText.startsWith(prefix) &&
    selectedText.endsWith(suffix) &&
    selectedText.length >= prefix.length + suffix.length;
  const isAmbiguousSingleAsteriskWrapper =
    prefix === '*' &&
    suffix === '*' &&
    selectedText.startsWith('**') &&
    selectedText.endsWith('**');

  if (
    hasSelection &&
    isExactWrapped &&
    !isAmbiguousSingleAsteriskWrapper
  ) {
    const unwrapped = selectedText.slice(prefix.length, selectedText.length - suffix.length);
    return {
      value: text.slice(0, selectionStart) + unwrapped + text.slice(selectionEnd),
      selectionStart,
      selectionEnd: selectionStart + unwrapped.length,
    };
  }

  const hasSurroundingMarkers =
    selectionStart >= prefix.length &&
    selectionEnd + suffix.length <= text.length &&
    text.slice(selectionStart - prefix.length, selectionStart) === prefix &&
    text.slice(selectionEnd, selectionEnd + suffix.length) === suffix;

  if (hasSelection && hasSurroundingMarkers) {
    return {
      value:
        text.slice(0, selectionStart - prefix.length) +
        selectedText +
        text.slice(selectionEnd + suffix.length),
      selectionStart: selectionStart - prefix.length,
      selectionEnd: selectionEnd - prefix.length,
    };
  }

  const wrapped = `${prefix}${selectedText}${suffix}`;
  return {
    value: text.slice(0, selectionStart) + wrapped + text.slice(selectionEnd),
    selectionStart: selectionStart + prefix.length,
    selectionEnd: selectionStart + prefix.length + selectedText.length,
  };
};

const getSelectedLineRange = (text: string, selectionStart: number, selectionEnd: number): MarkdownSelection => {
  const rangeStart = Math.max(0, Math.min(selectionStart, text.length));
  const rangeEnd = Math.max(rangeStart, Math.min(selectionEnd, text.length));
  const effectiveEnd = rangeEnd > rangeStart && text[rangeEnd - 1] === '\n' ? rangeEnd - 1 : rangeEnd;
  const lineStart = text.lastIndexOf('\n', rangeStart - 1) + 1;
  const nextLineBreak = text.indexOf('\n', effectiveEnd);
  const lineEnd = nextLineBreak === -1 ? text.length : nextLineBreak;
  return { selectionStart: lineStart, selectionEnd: lineEnd };
};

const stripListMarker = (line: string): { indent: string; content: string; type: 'unordered' | 'ordered' | null } => {
  const unordered = unorderedMarkerPattern.exec(line);
  if (unordered) {
    return { indent: unordered[1], content: unordered[3], type: 'unordered' };
  }

  const ordered = orderedMarkerPattern.exec(line);
  if (ordered) {
    return { indent: ordered[1], content: ordered[3], type: 'ordered' };
  }

  return { indent: line.match(/^\s*/)?.[0] ?? '', content: line.trimStart(), type: null };
};

const transformSelectedLines = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  transform: (lines: string[]) => string[]
): MarkdownEditResult => {
  const range = getSelectedLineRange(text, selectionStart, selectionEnd);
  const selectedBlock = text.slice(range.selectionStart, range.selectionEnd);
  const transformed = transform(selectedBlock.split('\n')).join('\n');

  return {
    value: text.slice(0, range.selectionStart) + transformed + text.slice(range.selectionEnd),
    selectionStart: range.selectionStart,
    selectionEnd: range.selectionStart + transformed.length,
  };
};

const applyListCommand = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  target: 'unordered' | 'ordered',
  placeholder: string
): MarkdownEditResult => {
  if (selectionStart === selectionEnd) {
    const marker = target === 'unordered' ? '- ' : '1. ';
    const insertion = `${marker}${placeholder}`;
    return {
      value: text.slice(0, selectionStart) + insertion + text.slice(selectionEnd),
      selectionStart: selectionStart + marker.length,
      selectionEnd: selectionStart + insertion.length,
    };
  }

  return transformSelectedLines(text, selectionStart, selectionEnd, (lines) => {
    const meaningfulLines = lines.filter((line) => line.trim().length > 0);
    const allAlreadyTarget = meaningfulLines.length > 0 && meaningfulLines.every((line) => {
      const parsed = stripListMarker(line);
      return parsed.type === target;
    });

    let orderedIndex = 1;
    return lines.map((line) => {
      if (!line.trim()) {
        return line;
      }

      const parsed = stripListMarker(line);
      if (allAlreadyTarget) {
        return `${parsed.indent}${parsed.content}`;
      }

      if (target === 'unordered') {
        return `${parsed.indent}- ${parsed.content}`;
      }

      const nextLine = `${parsed.indent}${orderedIndex}. ${parsed.content}`;
      orderedIndex += 1;
      return nextLine;
    });
  });
};

const applyQuoteCommand = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  placeholder: string
): MarkdownEditResult => {
  if (selectionStart === selectionEnd) {
    const insertion = `> ${placeholder}`;
    return {
      value: text.slice(0, selectionStart) + insertion + text.slice(selectionEnd),
      selectionStart: selectionStart + 2,
      selectionEnd: selectionStart + insertion.length,
    };
  }

  return transformSelectedLines(text, selectionStart, selectionEnd, (lines) => {
    const meaningfulLines = lines.filter((line) => line.trim().length > 0);
    const allQuoted = meaningfulLines.length > 0 && meaningfulLines.every((line) => quotePattern.test(line));

    return lines.map((line) => {
      if (!line.trim()) {
        return line;
      }
      if (allQuoted) {
        return line.replace(quotePattern, '$1$2');
      }
      const indent = line.match(/^\s*/)?.[0] ?? '';
      return `${indent}> ${line.slice(indent.length)}`;
    });
  });
};

const applyCodeCommand = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  placeholder: string
): MarkdownEditResult => {
  const selectedText = text.slice(selectionStart, selectionEnd);
  if (selectedText.includes('\n')) {
    return applySurroundingCommand(text, selectionStart, selectionEnd, '```\n', '\n```', placeholder);
  }

  return applySurroundingCommand(text, selectionStart, selectionEnd, '`', '`', placeholder);
};

const applyImageCommand = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  placeholder: string
): MarkdownEditResult => {
  const selectedText = getSelectedText(text, selectionStart, selectionEnd, placeholder);
  const insertion = `![${selectedText}](https://image.url)`;
  return {
    value: text.slice(0, selectionStart) + insertion + text.slice(selectionEnd),
    selectionStart: selectionStart + 2,
    selectionEnd: selectionStart + 2 + selectedText.length,
  };
};

export const applyMarkdownToolbarCommand = ({
  text,
  selectionStart,
  selectionEnd,
  command,
  placeholder,
}: MarkdownToolbarCommandInput): MarkdownEditResult => {
  switch (command) {
    case 'bold':
      return applySurroundingCommand(text, selectionStart, selectionEnd, '**', '**', placeholder);
    case 'italic':
      return applySurroundingCommand(text, selectionStart, selectionEnd, '*', '*', placeholder);
    case 'link':
      return applySurroundingCommand(text, selectionStart, selectionEnd, '[', '](https://example.com)', placeholder);
    case 'code':
      return applyCodeCommand(text, selectionStart, selectionEnd, placeholder);
    case 'image':
      return applyImageCommand(text, selectionStart, selectionEnd, placeholder);
    case 'quote':
      return applyQuoteCommand(text, selectionStart, selectionEnd, placeholder);
    case 'unorderedList':
      return applyListCommand(text, selectionStart, selectionEnd, 'unordered', placeholder);
    case 'orderedList':
      return applyListCommand(text, selectionStart, selectionEnd, 'ordered', placeholder);
  }
};

const applyLineIndent = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  shiftKey: boolean
): MarkdownEditResult => {
  return transformSelectedLines(text, selectionStart, selectionEnd, (lines) => (
    lines.map((line) => {
      if (shiftKey) {
        return line.replace(/^( {1,2}|\t)/, '');
      }
      return line.trim().length > 0 ? `  ${line}` : line;
    })
  ));
};

const continueListLine = (
  text: string,
  selectionStart: number,
  selectionEnd: number
): MarkdownEditResult | null => {
  if (selectionStart !== selectionEnd) {
    return null;
  }

  const lineStart = text.lastIndexOf('\n', selectionStart - 1) + 1;
  const lineEnd = text.indexOf('\n', selectionStart);
  const normalizedLineEnd = lineEnd === -1 ? text.length : lineEnd;
  const currentLine = text.slice(lineStart, selectionStart);
  const fullLine = text.slice(lineStart, normalizedLineEnd);
  const unordered = /^(\s*)([-+*])\s(.*)$/.exec(currentLine);
  const ordered = /^(\s*)(\d+)([.)])\s(.*)$/.exec(currentLine);

  if (!unordered && !ordered) {
    return null;
  }

  const content = fullLine.replace(/^(\s*)(?:[-+*]|\d+[.)])\s/, '');
  if (!content.trim()) {
    return {
      value: text.slice(0, lineStart) + text.slice(selectionEnd),
      selectionStart: lineStart,
      selectionEnd: lineStart,
    };
  }

  const insertion = unordered
    ? `\n${unordered[1]}${unordered[2]} `
    : `\n${ordered![1]}${Number.parseInt(ordered![2], 10) + 1}${ordered![3]} `;

  return {
    value: text.slice(0, selectionStart) + insertion + text.slice(selectionEnd),
    selectionStart: selectionStart + insertion.length,
    selectionEnd: selectionStart + insertion.length,
  };
};

export const applyMarkdownKeyCommand = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  event: Pick<KeyboardEvent, 'code' | 'key' | 'keyCode' | 'shiftKey'>
): MarkdownEditResult | null => {
  const code = event.code.toLowerCase();
  if (code === 'tab') {
    return applyLineIndent(text, selectionStart, selectionEnd, event.shiftKey);
  }

  if (code === 'enter' || event.key === 'Enter' || event.keyCode === 13) {
    return continueListLine(text, selectionStart, selectionEnd);
  }

  return null;
};
