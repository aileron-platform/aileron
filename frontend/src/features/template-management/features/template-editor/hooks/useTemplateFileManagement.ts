/**
 * 模板檔案管理 Hook
 * 提供完整的檔案系統操作功能
 */

import { useState, useCallback } from 'react';
import { useToast } from '@/shared/components/ui/use-toast';
import * as templateApi from '@/shared/services/templateApi';

export interface FileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  content?: string;
  extension?: string;
  created_at?: string;
  modified_at?: string;
  children?: FileNode[];
}

export const useTemplateFileManagement = (
  templateId: string | undefined,
  onSuccess?: () => void
) => {
  const { toast } = useToast();
  
  const [files, setFiles] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalFiles, setTotalFiles] = useState(0);
  const [totalSize, setTotalSize] = useState(0);
  const [searchResults, setSearchResults] = useState<templateApi.FileSearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // 載入檔案樹
  const loadFiles = useCallback(async (options?: {
    path?: string;
    includeContent?: boolean;
    maxDepth?: number;
  }) => {
    if (!templateId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await templateApi.getTemplateFiles(templateId, {
        path: options?.path,
        include_content: options?.includeContent ?? false,
        max_depth: options?.maxDepth ?? -1,
      });

      if (response.success && response.data) {
        setFiles(response.data);
        setTotalFiles(response.total_files);
        setTotalSize(response.total_size);
      } else {
        throw new Error(response.error || '載入檔案失敗');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '載入檔案失敗';
      setError(errorMessage);
      toast({
        title: t('common.template.errors.loadFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [templateId, toast]);

  // 取得檔案內容
  const getFileContent = useCallback(async (path: string) => {
    if (!templateId) return null;

    try {
      const response = await templateApi.getFileContent(templateId, path);
      if (response.success && response.data) {
        return response.data.content || '';
      }
      throw new Error(response.error || '讀取檔案失敗');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '讀取檔案失敗';
      toast({
        title: '讀取失敗',
        description: errorMessage,
        variant: 'destructive',
      });
      return null;
    }
  }, [templateId, toast]);

  // 建立檔案或目錄
  const createFileOrDirectory = useCallback(async (
    path: string,
    type: 'file' | 'directory',
    content?: string
  ) => {
    if (!templateId) return false;

    try {
      const response = await templateApi.createFileOrDirectory(templateId, {
        path,
        type,
        content,
      });

      if (response.success) {
        toast({
          title: '建立成功',
          description: `${type === 'file' ? '檔案' : '目錄'}「${path}」已建立`,
          variant: 'success',
        });
        await loadFiles();
        return true;
      }
      throw new Error(response.error || t('common.template.errors.createFailed'));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.createFailed');
      toast({
        title: t('common.template.errors.createFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      return false;
    }
  }, [templateId, toast, loadFiles]);

  // 更新檔案內容
  const updateFileContent = useCallback(async (path: string, content: string) => {
    if (!templateId) return false;

    try {
      const response = await templateApi.updateFileContent(templateId, {
        path,
        content,
      });

      if (response.success) {
        toast({
          title: '儲存成功',
          description: `檔案「${path}」已儲存`,
          variant: 'success',
        });
        await loadFiles();
        onSuccess?.(); // 保存成功後重新載入模板列表
        return true;
      }
      throw new Error(response.error || t('common.template.errors.saveFailed'));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.saveFailed');
      toast({
        title: t('common.template.errors.saveFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      return false;
    }
  }, [templateId, toast, loadFiles]);

  // 上傳檔案
  const uploadFiles = useCallback(async (
    files: File[],
    targetPath: string = '',
    overwrite: boolean = false
  ) => {
    if (!templateId) return null;

    try {
      const response = await templateApi.uploadFiles(templateId, files, targetPath, overwrite);

      if (response.success) {
        toast({
          title: '上傳成功',
          description: `成功上傳 ${response.succeeded}/${response.total} 個檔案`,
          variant: 'success',
        });
        await loadFiles();
        return response;
      }

      // 部分成功或全部失敗
      if (response.succeeded > 0) {
        // 收集失敗的檔案錯誤訊息
        const failedFiles = response.uploaded
          .filter(f => !f.success)
          .map(f => `${f.filename}: ${f.error}`)
          .join('\n');

        toast({
          title: '部分上傳成功',
          description: `成功上傳 ${response.succeeded}/${response.total} 個檔案\n\n失敗的檔案:\n${failedFiles}`,
          variant: 'default',
        });
        await loadFiles();
        return response;
      }

      // 全部失敗 - 顯示詳細錯誤
      const failedFiles = response.uploaded
        .filter(f => !f.success)
        .map(f => `${f.filename}: ${f.error}`)
        .join('\n');

      throw new Error(`上傳失敗:\n${failedFiles}`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.uploadFailed');
      toast({
        title: t('common.template.errors.uploadFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      return null;
    }
  }, [templateId, toast, loadFiles]);

  // 重命名檔案
  const renameFile = useCallback(async (oldPath: string, newName: string) => {
    if (!templateId) return false;

    try {
      const response = await templateApi.renameFile(templateId, {
        old_path: oldPath,
        new_name: newName,
      });

      if (response.success) {
        toast({
          title: '重命名成功',
          description: `已重命名為「${newName}」`,
          variant: 'success',
        });
        await loadFiles();
        return true;
      }
      throw new Error(response.error || t('common.template.errors.renameFailed'));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.renameFailed');
      toast({
        title: t('common.template.errors.renameFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      return false;
    }
  }, [templateId, toast, loadFiles]);

  // 移動檔案
  const moveFile = useCallback(async (
    sourcePath: string,
    targetPath: string,
    overwrite: boolean = false
  ) => {
    if (!templateId) return false;

    try {
      const response = await templateApi.moveFile(templateId, {
        source_path: sourcePath,
        target_path: targetPath,
        overwrite,
      });

      if (response.success) {
        toast({
          title: '移動成功',
          description: `已移動到「${targetPath}」`,
          variant: 'success',
        });
        await loadFiles();
        return true;
      }
      throw new Error(response.error || t('common.template.errors.moveFailed'));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.moveFailed');
      toast({
        title: t('common.template.errors.moveFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      return false;
    }
  }, [templateId, toast, loadFiles]);

  // 複製檔案
  const copyFile = useCallback(async (
    sourcePath: string,
    targetPath: string,
    overwrite: boolean = false
  ) => {
    if (!templateId) return false;

    try {
      const response = await templateApi.copyFile(templateId, {
        source_path: sourcePath,
        target_path: targetPath,
        overwrite,
      });

      if (response.success) {
        toast({
          title: '複製成功',
          description: `已複製到「${targetPath}」`,
          variant: 'success',
        });
        await loadFiles();
        return true;
      }
      throw new Error(response.error || t('common.template.errors.copyFailed'));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.copyFailed');
      toast({
        title: t('common.template.errors.copyFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      return false;
    }
  }, [templateId, toast, loadFiles]);

  // 刪除檔案
  const deleteFile = useCallback(async (path: string, recursive: boolean = false) => {
    if (!templateId) return false;

    try {
      const response = await templateApi.deleteFile(templateId, path, recursive);

      if (response.success) {
        toast({
          title: '刪除成功',
          description: `已刪除「${path}」`,
          variant: 'success',
        });
        await loadFiles();
        return true;
      }
      throw new Error(response.error || t('common.template.errors.deleteFailed'));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.deleteFailed');
      toast({
        title: t('common.template.errors.deleteFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      return false;
    }
  }, [templateId, toast, loadFiles]);

  // 批次刪除
  const batchDeleteFiles = useCallback(async (paths: string[], recursive: boolean = false) => {
    if (!templateId) return null;

    try {
      const response = await templateApi.batchDeleteFiles(templateId, {
        paths,
        recursive,
      });

      if (response.success) {
        toast({
          title: '批次刪除成功',
          description: `成功刪除 ${response.succeeded}/${response.total} 個項目`,
          variant: 'success',
        });
        await loadFiles();
        return response;
      }
      
      // 部分成功
      if (response.succeeded > 0) {
        toast({
          title: '部分刪除成功',
          description: `成功刪除 ${response.succeeded}/${response.total} 個項目，${response.failed} 個失敗`,
          variant: 'default',
        });
        await loadFiles();
        return response;
      }
      
      throw new Error(response.message || t('common.template.errors.batchDeleteFailed'));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.batchDeleteFailed');
      toast({
        title: t('common.template.errors.batchDeleteFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      return null;
    }
  }, [templateId, toast, loadFiles]);

  // 搜尋檔案
  const searchFiles = useCallback(async (
    query: string,
    searchContent: boolean = true,
    fileTypes?: string[]
  ) => {
    if (!templateId || !query.trim()) {
      setSearchResults([]);
      return [];
    }

    setSearching(true);
    try {
      const response = await templateApi.searchFiles(templateId, {
        query,
        searchContent,
        fileTypes,
        maxResults: 50,
      });

      setSearchResults(response.results);
      return response.results;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('common.template.errors.searchFailed');
      toast({
        title: t('common.template.errors.searchFailed'),
        description: errorMessage,
        variant: 'destructive',
      });
      setSearchResults([]);
      return [];
    } finally {
      setSearching(false);
    }
  }, [templateId, toast]);

  return {
    // 狀態
    files,
    loading,
    error,
    totalFiles,
    totalSize,
    searchResults,
    searching,

    // 方法
    loadFiles,
    getFileContent,
    createFileOrDirectory,
    updateFileContent,
    uploadFiles,
    renameFile,
    moveFile,
    copyFile,
    deleteFile,
    batchDeleteFiles,
    searchFiles,
  };
};

