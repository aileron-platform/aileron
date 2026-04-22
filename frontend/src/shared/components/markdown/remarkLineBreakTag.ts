import { visit } from 'unist-util-visit';

interface HtmlNode {
  type: 'html';
  value?: string;
}

interface ParentNode {
  children?: unknown[];
}

interface BreakNode {
  type: 'break';
}

const BR_TAG_PATTERN = /^<br\s*\/?>$/i;

export function remarkLineBreakTag() {
  return (tree: unknown) => {
    visit(tree, 'html', (node: HtmlNode, index, parent: ParentNode | undefined) => {
      if (index === undefined || !parent?.children || !BR_TAG_PATTERN.test(node.value?.trim() ?? '')) {
        return;
      }

      (parent.children as unknown[]).splice(index, 1, { type: 'break' } satisfies BreakNode);
    });
  };
}

export default remarkLineBreakTag;
