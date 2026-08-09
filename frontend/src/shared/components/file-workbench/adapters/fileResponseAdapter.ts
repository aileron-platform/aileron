import type { FileOperationResponse, FileTreeNode } from '../types';

export interface FileContent {
  path: string;
  content: string;
  revision?: string;
  size?: number;
}

const mapNodes = (arr: unknown): FileTreeNode[] =>
  (Array.isArray(arr) ? arr : []).map((node) => {
    const rawNode = node as Partial<FileTreeNode> & { children?: unknown };
    return {
      id: rawNode.id ?? rawNode.path ?? '',
      name: rawNode.name ?? '',
      path: rawNode.path ?? '',
      type: rawNode.type ?? 'file',
      scope: rawNode.scope,
      size: rawNode.size,
      hasChildren: rawNode.hasChildren,
      revision: rawNode.revision,
      writable: rawNode.writable,
      extension: rawNode.extension,
      metadata: rawNode.metadata,
      badges: rawNode.badges,
      pluginId: rawNode.pluginId,
      pluginName: rawNode.pluginName,
      marketplaceName: rawNode.marketplaceName,
      modifiedAt: rawNode.modifiedAt,
      createdAt: rawNode.createdAt,
      ...(rawNode.children ? { children: mapNodes(rawNode.children) } : {}),
    };
  });

export function parseFileTree(raw: unknown): FileTreeNode[] {
  if (Array.isArray(raw)) {
    return mapNodes(raw);
  }
  const response = raw as { nodes?: unknown };
  return mapNodes(response.nodes ?? []);
}

export function parseFileContent(raw: unknown): FileContent {
  const data = raw as {
    path: string;
    content?: string;
    size?: number;
    revision?: string;
  };
  return {
    path: data.path,
    content: data.content ?? '',
    ...(data.size !== undefined ? { size: data.size } : {}),
    ...(data.revision ? { revision: data.revision } : {}),
  };
}

const hasFileOperationRevision = (value: unknown): value is { revision?: string | null } => {
  if (value === null || typeof value !== 'object' || !('revision' in value)) {
    return false;
  }

  const { revision } = value;
  return revision === undefined || revision === null || typeof revision === 'string';
};

export function getFileOperationResponseRevision(
  response?: FileOperationResponse,
): string | null | undefined {
  if (!response || !hasFileOperationRevision(response.data)) {
    return undefined;
  }

  return response.data.revision;
}
