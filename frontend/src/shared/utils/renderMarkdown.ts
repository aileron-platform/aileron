export const renderMarkdown = (markdown: string): string => {
  if (!markdown) {
    return '';
  }

  const escapeHtml = (unsafe: string) =>
    unsafe
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');

  let processed = markdown;
  const codeBlocks: string[] = [];
  processed = processed.replace(/```([\s\S]*?)```/g, (_, code) => {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    codeBlocks.push(
      `<pre class="bg-muted text-foreground" style="padding:12px;border-radius:6px;overflow:auto;font-family:'Fira Code',monospace;border:1px solid var(--border);"><code>${escapeHtml(
        code.trim()
      )}</code></pre>`
    );
    return placeholder;
  });

  const inlineCodes: string[] = [];
  processed = processed.replace(/`([^`]+)`/g, (_, code) => {
    const placeholder = `__INLINE_CODE_${inlineCodes.length}__`;
    inlineCodes.push(
      `<code class="bg-muted text-foreground" style="padding:2px 4px;border-radius:4px;font-family:'Fira Code',monospace;">${escapeHtml(
        code
      )}</code>`
    );
    return placeholder;
  });

  let frontMatterTable = '';
  const frontMatterMatch = processed.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (frontMatterMatch) {
    const frontMatter = frontMatterMatch[1];
    const body = frontMatterMatch[2];
    const rows = frontMatter
      .split('\n')
      .filter((line) => line.trim())
      .map((line) => {
        const [key, ...rest] = line.split(':');
        return `<tr><td class="border" style="padding:6px 8px;font-weight:600;">${escapeHtml(
          key.trim()
        )}</td><td class="border" style="padding:6px 8px;">${escapeHtml(
          rest.join(':').trim()
        )}</td></tr>`;
      })
      .join('');
    frontMatterTable = `<div style="margin-bottom:16px;"><h4 class="text-muted-foreground" style="margin:0 0 12px 0;font-size:13px;">配置資訊</h4><table class="border" style="width:100%;border-collapse:collapse;">${rows}</table></div>`;
    processed = body;
  }

  // 處理表格
  const parseTable = (lines: string[], startIndex: number): { html: string; endIndex: number } | null => {
    const line = lines[startIndex]?.trim();
    if (!line || !line.startsWith('|')) return null;

    // 檢查是否有分隔符行
    if (startIndex + 1 >= lines.length) return null;
    const separatorLine = lines[startIndex + 1]?.trim();
    if (!separatorLine || !separatorLine.match(/^\|[\s\-:|]+\|$/)) return null;

    // 解析表頭
    const headers = line
      .split('|')
      .slice(1, -1)
      .map((h) => h.trim());

    // 解析對齊方式
    const alignments = separatorLine
      .split('|')
      .slice(1, -1)
      .map((sep) => {
        const trimmed = sep.trim();
        if (trimmed.startsWith(':') && trimmed.endsWith(':')) return 'center';
        if (trimmed.endsWith(':')) return 'right';
        if (trimmed.startsWith(':')) return 'left';
        return 'left';
      });

    // 解析表格內容行
    const rows: string[][] = [];
    let currentIndex = startIndex + 2;
    while (currentIndex < lines.length) {
      const rowLine = lines[currentIndex]?.trim();
      if (!rowLine || !rowLine.startsWith('|')) break;

      const cells = rowLine
        .split('|')
        .slice(1, -1)
        .map((c) => c.trim());
      rows.push(cells);
      currentIndex++;
    }

    // 生成 HTML 表格
    const theadHtml = headers
      .map((h, i) => {
        const align = alignments[i] || 'left';
        return `<th class="border border-border bg-muted/50" style="padding:8px 12px;text-align:${align};font-weight:600;">${h}</th>`;
      })
      .join('');

    const tbodyHtml = rows
      .map((row) => {
        const cellsHtml = row
          .map((cell, i) => {
            const align = alignments[i] || 'left';
            return `<td class="border border-border" style="padding:8px 12px;text-align:${align};">${cell}</td>`;
          })
          .join('');
        return `<tr>${cellsHtml}</tr>`;
      })
      .join('');

    const tableHtml = `<table class="border-collapse" style="width:100%;margin:16px 0;border:1px solid var(--border);"><thead><tr>${theadHtml}</tr></thead><tbody>${tbodyHtml}</tbody></table>`;

    return {
      html: tableHtml,
      endIndex: currentIndex - 1,
    };
  };

  // 計算縮排層級
  const getIndent = (line: string): number => {
    const match = line.match(/^(\s*)/);
    return match ? match[1].length : 0;
  };

  // 檢查是否為列表項
  const isListItem = (line: string): boolean => {
    const trimmed = line.trim();
    return trimmed.match(/^[-*]\s+/) !== null || trimmed.match(/^\d+\.\s+/) !== null;
  };

  // 遞歸處理列表項及其子項
  const processListItems = (lines: string[], startIndex: number, baseIndent: number, listType: 'ul' | 'ol'): { html: string; endIndex: number } => {
    const items: string[] = [];
    let i = startIndex;

    while (i < lines.length) {
      const rawLine = lines[i];
      const line = rawLine.trim();
      const indent = getIndent(rawLine);

      // 空行：檢查下一行
      if (!line) {
        // 向前查找下一個非空行
        let hasNextItem = false;
        for (let j = i + 1; j < lines.length; j++) {
          const nextLine = lines[j];
          const nextTrimmed = nextLine.trim();
          if (!nextTrimmed) continue;

          const nextIndent = getIndent(nextLine);
          if (isListItem(nextLine) && nextIndent >= baseIndent) {
            hasNextItem = true;
          }
          break;
        }

        if (!hasNextItem) {
          break; // 列表結束
        }
        i++;
        continue;
      }

      // 如果縮排小於基準，列表結束
      if (indent < baseIndent) {
        break;
      }

      // 如果不是列表項，列表結束
      if (!isListItem(rawLine)) {
        break;
      }

      // 如果是同層級的列表項
      if (indent === baseIndent) {
        const unorderedMatch = line.match(/^[-*]\s+(.*)$/);
        const orderedMatch = line.match(/^\d+\.\s+(.*)$/);

        // 檢查列表類型是否匹配
        const isUnordered = unorderedMatch !== null;
        const isOrdered = orderedMatch !== null;

        if ((listType === 'ul' && !isUnordered) || (listType === 'ol' && !isOrdered)) {
          // 類型不匹配，列表結束
          break;
        }

        if (unorderedMatch || orderedMatch) {
          const content = unorderedMatch ? unorderedMatch[1] : orderedMatch![1];

          // 檢查下一行是否為更深層的列表項
          let childHtml = '';
          if (i + 1 < lines.length) {
            const nextRawLine = lines[i + 1];
            const nextIndent = getIndent(nextRawLine);
            const nextTrimmed = nextRawLine.trim();

            if (nextTrimmed && isListItem(nextRawLine) && nextIndent > indent) {
              // 判斷子列表的類型
              const childIsUnordered = nextTrimmed.match(/^[-*]\s+/) !== null;
              const childListType = childIsUnordered ? 'ul' : 'ol';

              // 有子列表
              const childResult = processListItems(lines, i + 1, nextIndent, childListType);
              childHtml = `\n<${childListType}>\n${childResult.html}\n</${childListType}>`;
              i = childResult.endIndex;
            }
          }

          items.push(`<li>${content}${childHtml}</li>`);
        }
      }

      i++;
    }

    return { html: items.join('\n'), endIndex: i - 1 };
  };

  const htmlParts: string[] = [];
  const lines = processed.split('\n');
  let i = 0;

  while (i < lines.length) {
    const rawLine = lines[i];
    const line = rawLine.trim();
    const indent = getIndent(rawLine);

    if (!line) {
      i++;
      continue;
    }

    // 檢查是否為表格
    const tableResult = parseTable(lines, i);
    if (tableResult) {
      htmlParts.push(tableResult.html);
      i = tableResult.endIndex + 1;
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s*(.*)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const headingText = headingMatch[2].trim();
      htmlParts.push(`<h${level}>${headingText}</h${level}>`);
      i++;
      continue;
    }

    // 無序列表
    const unorderedMatch = line.match(/^[-*]\s+(.*)$/);
    if (unorderedMatch && indent === 0) {
      const result = processListItems(lines, i, 0, 'ul');
      htmlParts.push(`<ul>\n${result.html}\n</ul>`);
      i = result.endIndex + 1;
      continue;
    }

    // 有序列表
    const orderedMatch = line.match(/^\d+\.\s+(.*)$/);
    if (orderedMatch && indent === 0) {
      const result = processListItems(lines, i, 0, 'ol');
      htmlParts.push(`<ol>\n${result.html}\n</ol>`);
      i = result.endIndex + 1;
      continue;
    }

    if (line.startsWith('> ')) {
      htmlParts.push(
        `<blockquote class="border-l-border bg-muted/30" style="border-left-width:3px;margin:12px 0;padding:8px 16px;">${line.substring(2)}</blockquote>`
      );
      i++;
      continue;
    }

    htmlParts.push(`<p>${line}</p>`);
    i++;
  }

  let html = htmlParts.join('\n');
  codeBlocks.forEach((block, index) => {
    html = html.replace(`__CODE_BLOCK_${index}__`, block);
  });
  inlineCodes.forEach((code, index) => {
    html = html.replace(`__INLINE_CODE_${index}__`, code);
  });

  // 在最前面加上 frontmatter 表格
  if (frontMatterTable) {
    html = frontMatterTable + '\n' + html;
  }

  return html;
};

export default renderMarkdown;
