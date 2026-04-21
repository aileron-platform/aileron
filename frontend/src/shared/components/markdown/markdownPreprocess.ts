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
