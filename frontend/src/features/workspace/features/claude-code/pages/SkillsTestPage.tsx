import React, { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useFileCollection } from '../hooks/useFileCollection';
import { Loader2, FileText, Folder, Plus, Trash2, Edit } from 'lucide-react';
import { useToast } from '@/shared/components/ui/use-toast';
import { Textarea } from '@/shared/components/ui/textarea';
import { Input } from '@/shared/components/ui/input';

export const SkillsTestPage: React.FC = () => {
  const { toast } = useToast();
  const {
    files,
    tree,
    isLoading,
    getFile,
    createFile,
    updateFile,
    deleteFile,
    isCreating,
    isUpdating,
    isDeleting,
  } = useFileCollection({ collectionType: 'skills' });

  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  // 新建檔案表單
  const [newFileName, setNewFileName] = useState('');
  const [newFileContent, setNewFileContent] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);

  const handleLoadFile = async (filePath: string) => {
    setIsLoadingFile(true);
    try {
      const response = await getFile(filePath);
      setFileContent(response.file.content);
      setSelectedFilePath(filePath);
      setIsEditing(false);
    } catch (error: any) {
      toast({
        title: '載入失敗',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setIsLoadingFile(false);
    }
  };

  const handleCreateFile = async () => {
    if (!newFileName) {
      toast({
        title: '檔案名稱不能為空',
        variant: 'destructive',
      });
      return;
    }

    try {
      await createFile({
        fileName: newFileName,
        content: newFileContent,
        namespace: null,
      });
      toast({
        title: '建立成功',
        description: `檔案 ${newFileName} 已建立`,
      });
      setNewFileName('');
      setNewFileContent('');
      setShowCreateForm(false);
    } catch (error: any) {
      toast({
        title: '建立失敗',
        description: error.message,
        variant: 'destructive',
      });
    }
  };

  const handleUpdateFile = async () => {
    if (!selectedFilePath) return;

    try {
      await updateFile({
        filePath: selectedFilePath,
        payload: { content: fileContent },
      });
      toast({
        title: '更新成功',
        description: `檔案已更新`,
      });
      setIsEditing(false);
    } catch (error: any) {
      toast({
        title: '更新失敗',
        description: error.message,
        variant: 'destructive',
      });
    }
  };

  const handleDeleteFile = async (filePath: string) => {
    if (!confirm(`確定要刪除 ${filePath} 嗎？`)) return;

    try {
      await deleteFile(filePath);
      toast({
        title: '刪除成功',
        description: `檔案 ${filePath} 已刪除`,
      });
      if (selectedFilePath === filePath) {
        setSelectedFilePath(null);
        setFileContent('');
      }
    } catch (error: any) {
      toast({
        title: '刪除失敗',
        description: error.message,
        variant: 'destructive',
      });
    }
  };

  const renderTree = (nodes: any[]) => {
    return nodes.map((node) => (
      <div key={node.id} className="ml-4">
        {node.type === 'directory' ? (
          <div className="flex items-center gap-2 py-1">
            <Folder className="h-4 w-4 text-blue-500" />
            <span className="font-medium">{node.name}</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 py-1 hover:bg-accent rounded px-2">
            <FileText className="h-4 w-4 text-gray-500" />
            <button
              onClick={() => handleLoadFile(node.path)}
              className="flex-1 text-left hover:underline"
            >
              {node.name}
            </button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleDeleteFile(node.path)}
              disabled={isDeleting}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        )}
        {node.children && renderTree(node.children)}
      </div>
    ));
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Skills API 測試頁面</CardTitle>
          <CardDescription>測試 Skills 的 CRUD 操作</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              共 {files.length} 個檔案
            </div>
            <Button onClick={() => setShowCreateForm(!showCreateForm)} size="sm">
              <Plus className="h-4 w-4 mr-2" />
              新建檔案
            </Button>
          </div>

          {showCreateForm && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">新建檔案</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium">檔案名稱</label>
                  <Input
                    value={newFileName}
                    onChange={(e) => setNewFileName(e.target.value)}
                    placeholder="example.md"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">檔案內容</label>
                  <Textarea
                    value={newFileContent}
                    onChange={(e) => setNewFileContent(e.target.value)}
                    placeholder="# 檔案內容"
                    rows={5}
                  />
                </div>
                <div className="flex gap-2">
                  <Button onClick={handleCreateFile} disabled={isCreating}>
                    {isCreating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    建立
                  </Button>
                  <Button variant="outline" onClick={() => setShowCreateForm(false)}>
                    取消
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">檔案樹</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : tree.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-8">
                沒有檔案
              </div>
            ) : (
              <div>{renderTree(tree)}</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">檔案內容</CardTitle>
            {selectedFilePath && (
              <CardDescription>{selectedFilePath}</CardDescription>
            )}
          </CardHeader>
          <CardContent>
            {isLoadingFile ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : !selectedFilePath ? (
              <div className="text-sm text-muted-foreground text-center py-8">
                請選擇一個檔案
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex gap-2">
                  {!isEditing ? (
                    <Button size="sm" onClick={() => setIsEditing(true)}>
                      <Edit className="h-4 w-4 mr-2" />
                      編輯
                    </Button>
                  ) : (
                    <>
                      <Button size="sm" onClick={handleUpdateFile} disabled={isUpdating}>
                        {isUpdating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                        儲存
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setIsEditing(false)}
                      >
                        取消
                      </Button>
                    </>
                  )}
                </div>
                <Textarea
                  value={fileContent}
                  onChange={(e) => setFileContent(e.target.value)}
                  disabled={!isEditing}
                  rows={15}
                  className="font-mono text-sm"
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

