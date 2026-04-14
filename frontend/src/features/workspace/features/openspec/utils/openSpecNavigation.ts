import type { FileNode } from '../../file-management/types';

export interface OpenSpecSpecItem {
  id: string;
  capabilityName: string;
  path: string;
}

export interface OpenSpecChangeItem {
  id: string;
  name: string;
  archived: boolean;
  proposalPath?: string;
  designPath?: string;
  tasksPath?: string;
  specs: OpenSpecSpecItem[];
}

export type OpenSpecChangeStatus = 'in-progress' | 'complete' | 'archived';

const OPEN_SPEC_ROOT = '/openspec';

const flattenNodes = (nodes: FileNode[]): FileNode[] => {
  const flattened: FileNode[] = [];

  const visit = (nodeList: FileNode[]) => {
    nodeList.forEach((node) => {
      flattened.push(node);
      if (node.children?.length) {
        visit(node.children);
      }
    });
  };

  visit(nodes);
  return flattened;
};

export const hasOpenSpecDirectory = (nodes: FileNode[]): boolean => {
  return flattenNodes(nodes).some(
    (node) => node.type === 'directory' && node.path === OPEN_SPEC_ROOT,
  );
};

export const buildOpenSpecChangeItems = (nodes: FileNode[]): OpenSpecChangeItem[] => {
  const allNodes = flattenNodes(nodes);
  const fileNodes = allNodes.filter(
    (node) => node.type === 'file' && node.path.startsWith(`${OPEN_SPEC_ROOT}/changes/`),
  );
  const changes = new Map<string, OpenSpecChangeItem>();

  fileNodes.forEach((node) => {
    const segments = node.path.split('/').filter(Boolean);

    if (segments.length < 4 || segments[0] !== 'openspec' || segments[1] !== 'changes') {
      return;
    }

    const archived = segments[2] === 'archive';
    const changeName = archived ? segments[3] : segments[2];

    if (!changeName) {
      return;
    }

    const changeId = `${archived ? 'archive' : 'active'}:${changeName}`;
    const existing = changes.get(changeId) ?? {
      id: changeId,
      name: changeName,
      archived,
      specs: [],
    };

    const fileName = segments.at(-1);

    if (fileName === 'proposal.md') {
      existing.proposalPath = node.path;
    } else if (fileName === 'design.md') {
      existing.designPath = node.path;
    } else if (fileName === 'tasks.md') {
      existing.tasksPath = node.path;
    } else if (fileName === 'spec.md') {
      const capabilityName = segments.at(-2);
      if (capabilityName) {
        existing.specs.push({
          id: `${changeId}:spec:${capabilityName}`,
          capabilityName,
          path: node.path,
        });
      }
    }

    changes.set(changeId, existing);
  });

  return Array.from(changes.values())
    .map((change) => ({
      ...change,
      specs: [...change.specs].sort((a, b) => a.capabilityName.localeCompare(b.capabilityName)),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
};

export const getOpenSpecChangeStatus = (
  change: OpenSpecChangeItem,
  tasksContent?: string,
): OpenSpecChangeStatus => {
  if (change.archived) {
    return 'archived';
  }

  if (!change.tasksPath || !tasksContent) {
    return 'in-progress';
  }

  const checklistLines = tasksContent.match(/^\s*-\s\[(x|X| )\]\s.+$/gm) ?? [];
  if (checklistLines.length === 0) {
    return 'in-progress';
  }

  const hasIncompleteTask = checklistLines.some((line) => /^\s*-\s\[\s\]\s.+$/.test(line));
  return hasIncompleteTask ? 'in-progress' : 'complete';
};
