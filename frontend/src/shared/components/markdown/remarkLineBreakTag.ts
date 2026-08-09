import type { Break, Root } from 'mdast';
import { visit } from 'unist-util-visit';

const BR_TAG_PATTERN = /^<br\s*\/?>$/i;

export function remarkLineBreakTag() {
  return (tree: Root) => {
    visit(tree, 'html', (node, index, parent) => {
      if (index === undefined || !parent || !BR_TAG_PATTERN.test(node.value.trim())) {
        return;
      }

      parent.children.splice(index, 1, { type: 'break' } satisfies Break);
    });
  };
}
