import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import {
  claudeCodeApi,
  type FileCollectionResponse,
  type FileResponse,
  type FileCreateRequest,
  type FileUpdateRequest,
  type FileCollectionType,
  type FileTreeNode,
  type PluginSkillsResponse,
} from '../services/claudeCodeApi';

export interface UseFileCollectionOptions {
  collectionType: FileCollectionType;
  scope?: 'project' | 'user' | 'plugin';
}

export const useFileCollection = ({ collectionType, scope }: UseFileCollectionOptions) => {
  const { workspaceRuntime } = useWorkspace();
  const queryClient = useQueryClient();

  const runtimeBaseUrl = workspaceRuntime?.runtimeBaseUrl || '';
  const workspaceId = workspaceRuntime?.workspaceId || '';

  // 穩定的 queryFn，避免不必要的重新請求
  const listCollectionFn = useCallback(() => {
    if (collectionType === 'skills') {
      return claudeCodeApi.listSkills(runtimeBaseUrl, workspaceId, scope);
    } else {
      return claudeCodeApi.listScripts(runtimeBaseUrl, workspaceId);
    }
  }, [collectionType, runtimeBaseUrl, workspaceId, scope]);

  // 列表查詢
  const {
    data: collectionData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: [collectionType, workspaceId, scope],
    queryFn: listCollectionFn,
    enabled: !!workspaceId && !!runtimeBaseUrl,
  });

  // 穩定的 Plugin Skills queryFn
  const listPluginSkillsFn = useCallback(() => {
    return claudeCodeApi.listPluginSkills(runtimeBaseUrl, workspaceId);
  }, [runtimeBaseUrl, workspaceId]);

  // Plugin Skills 查詢
  const {
    data: pluginSkillsData,
    isLoading: isLoadingPlugins,
  } = useQuery({
    queryKey: ['plugin-skills', workspaceId],
    queryFn: listPluginSkillsFn,
    enabled: !!workspaceId && !!runtimeBaseUrl && collectionType === 'skills',
  });

  // 取得單一檔案
  const getFile = useCallback(async (filePath: string, fileScope?: 'project' | 'user' | 'plugin'): Promise<FileResponse> => {
    const targetScope = fileScope || scope || 'project';
    if (collectionType === 'skills') {
      return claudeCodeApi.getSkill(runtimeBaseUrl, workspaceId, filePath, targetScope);
    } else {
      // Scripts 不支援 plugin scope，如果是 plugin 則使用 project
      const scriptScope = targetScope === 'plugin' ? 'project' : targetScope;
      return claudeCodeApi.getScript(runtimeBaseUrl, workspaceId, filePath, scriptScope);
    }
  }, [runtimeBaseUrl, workspaceId, scope, collectionType]);

  // 建立檔案
  const createMutation = useMutation({
    mutationFn: (payload: FileCreateRequest) => {
      // 確保 payload 包含 scope（如果傳入了 scope，優先使用；否則使用當前的 scope）
      const payloadWithScope = {
        ...payload,
        scope: payload.scope || scope,
      };

      if (collectionType === 'skills') {
        return claudeCodeApi.createSkill(runtimeBaseUrl, workspaceId, payloadWithScope);
      } else {
        return claudeCodeApi.createScript(runtimeBaseUrl, workspaceId, payloadWithScope);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [collectionType, workspaceId] });
    },
  });

  // 更新檔案
  const updateMutation = useMutation({
    mutationFn: ({ filePath, payload, fileScope }: { filePath: string; payload: FileUpdateRequest; fileScope?: 'project' | 'user' | 'plugin' }) => {
      const targetScope = fileScope || scope;
      // Plugin 檔案是唯讀的，不能更新。如果是 plugin scope，則使用 project
      const validScope = targetScope === 'plugin' ? 'project' : targetScope;

      if (collectionType === 'skills') {
        return claudeCodeApi.updateSkill(runtimeBaseUrl, workspaceId, filePath, payload, validScope);
      } else {
        return claudeCodeApi.updateScript(runtimeBaseUrl, workspaceId, filePath, payload, validScope);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [collectionType, workspaceId] });
    },
  });

  // 刪除檔案
  const deleteMutation = useMutation({
    mutationFn: ({ filePath, fileScope, recursive = false }: { filePath: string; fileScope?: 'project' | 'user' | 'plugin'; recursive?: boolean }) => {
      const targetScope = fileScope || scope || 'project';
      // Plugin 檔案是唯讀的，不能刪除。如果是 plugin scope，則使用 project
      const validScope = targetScope === 'plugin' ? 'project' : targetScope;

      if (collectionType === 'skills') {
        return claudeCodeApi.deleteSkill(runtimeBaseUrl, workspaceId, filePath, validScope, recursive);
      } else {
        return claudeCodeApi.deleteScript(runtimeBaseUrl, workspaceId, filePath, validScope, recursive);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [collectionType, workspaceId] });
    },
  });

  // 使用 useMemo 穩定 tree 引用，避免不必要的重新渲染
  const stableTree = useMemo(() => collectionData?.tree || [], [collectionData?.tree]);
  const stableFiles = useMemo(() => collectionData?.files || [], [collectionData?.files]);
  const stablePluginSkills = useMemo(() => pluginSkillsData?.plugins || [], [pluginSkillsData?.plugins]);

  return {
    // 資料
    files: stableFiles,
    tree: stableTree,
    pluginSkills: stablePluginSkills,
    isLoading: isLoading || isLoadingPlugins,
    error,

    // 操作
    getFile,
    createFile: createMutation.mutateAsync,
    updateFile: updateMutation.mutateAsync,
    deleteFile: deleteMutation.mutateAsync,
    refetch,

    // 狀態
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
};

// 輔助函數：將 FileTreeNode 轉換為舊的 FileNode 格式（用於向後相容）
export const convertTreeNodeToFileNode = (node: FileTreeNode): any => {
  return {
    id: node.id,
    name: node.name,
    path: node.path,
    type: node.type,
    children: node.children?.map(convertTreeNodeToFileNode),
    content: undefined, // 內容需要單獨載入
  };
};

// 輔助函數：扁平化檔案樹
export const flattenFileTree = (nodes: FileTreeNode[]): FileTreeNode[] => {
  const result: FileTreeNode[] = [];
  const walk = (node: FileTreeNode) => {
    if (node.type === 'file') {
      result.push(node);
    }
    node.children?.forEach(walk);
  };
  nodes.forEach(walk);
  return result;
};

// 輔助函數：查找檔案節點
export const findFileNode = (nodes: FileTreeNode[], path: string): FileTreeNode | null => {
  for (const node of nodes) {
    if (node.path === path) {
      return node;
    }
    if (node.children) {
      const found = findFileNode(node.children, path);
      if (found) {
        return found;
      }
    }
  }
  return null;
};

