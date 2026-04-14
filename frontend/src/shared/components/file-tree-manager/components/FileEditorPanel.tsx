/**
 * FileEditorPanel 組件
 * 
 * 右側編輯器面板，包含：
 * - 標籤列
 * - 編輯器區域
 * - 支援多種檔案類型
 */

import React from 'react';
import { X, Save, RotateCcw } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { FileTab } from '../hooks/useFileEditor';
import type { UseFileEditorReturn } from '../hooks/useFileEditor';

export interface FileEditorPanelProps {
  /** 編輯器狀態 */
  editor: UseFileEditorReturn;
  
  /** 內容變更回調 */
  onContentChange?: (path: string, content: string) => void;
  
  /** 儲存回調 */
  onSave?: (path: string, content: string) => void;
  
  /** 自訂編輯器渲染 */
  renderEditor?: (tab: FileTab) => React.ReactNode;
  
  /** 自訂 className */
  className?: string;
}

export const FileEditorPanel: React.FC<FileEditorPanelProps> = ({
  editor,
  onContentChange,
  onSave,
  renderEditor,
  className,
}) => {
  // 處理內容變更
  const handleContentChange = (content: string) => {
    if (editor.activeTab) {
      editor.updateContent(editor.activeTab.path, content);
      if (onContentChange) {
        onContentChange(editor.activeTab.path, content);
      }
    }
  };

  // 處理儲存
  const handleSave = () => {
    if (editor.activeTab) {
      if (onSave) {
        onSave(editor.activeTab.path, editor.activeTab.content);
      }
      editor.saveTab(editor.activeTab.path);
    }
  };

  // 處理還原
  const handleRevert = () => {
    if (editor.activeTab) {
      editor.revertTab(editor.activeTab.path);
    }
  };

  // 預設編輯器渲染
  const defaultRenderEditor = (tab: FileTab) => {
    return (
      <div className="flex flex-col h-full">
        {/* 工具列 */}
        <div className="flex items-center gap-2 p-2 border-b bg-muted/30">
          <button
            onClick={handleSave}
            disabled={!tab.isModified}
            className={cn(
              'flex items-center gap-1 px-3 py-1.5 text-xs rounded transition-colors',
              tab.isModified
                ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                : 'bg-muted text-muted-foreground cursor-not-allowed'
            )}
            title="儲存 (Ctrl+S)"
          >
            <Save className="h-3 w-3" />
            儲存
          </button>
          
          <button
            onClick={handleRevert}
            disabled={!tab.isModified}
            className={cn(
              'flex items-center gap-1 px-3 py-1.5 text-xs rounded transition-colors',
              tab.isModified
                ? 'bg-muted text-foreground hover:bg-muted/80'
                : 'bg-muted text-muted-foreground cursor-not-allowed'
            )}
            title="還原變更"
          >
            <RotateCcw className="h-3 w-3" />
            還原
          </button>
          
          {tab.isModified && (
            <span className="text-xs text-muted-foreground ml-auto">
              未儲存的變更
            </span>
          )}
        </div>

        {/* 編輯器 */}
        <div className="flex-1 overflow-auto">
          <textarea
            value={tab.content}
            onChange={(e) => handleContentChange(e.target.value)}
            className="w-full h-full p-4 font-mono text-sm bg-background border-0 outline-none resize-none"
            placeholder="開始編輯..."
            spellCheck={false}
          />
        </div>
      </div>
    );
  };

  return (
    <div className={cn('flex flex-col h-full bg-background', className)}>
      {/* 標籤列 */}
      {editor.tabs.length > 0 && (
        <div className="flex items-center gap-1 px-2 py-1 border-b bg-muted/20 overflow-x-auto">
          {editor.tabs.map((tab) => (
            <button
              key={tab.path}
              onClick={() => editor.setActiveTab(tab.path)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 text-xs rounded-t transition-colors whitespace-nowrap',
                editor.activeTabPath === tab.path
                  ? 'bg-background text-foreground border-t border-x'
                  : 'bg-muted/50 text-muted-foreground hover:bg-muted'
              )}
            >
              <span className="truncate max-w-[120px]" title={tab.path}>
                {tab.name}
              </span>
              
              {tab.isModified && (
                <span className="w-1.5 h-1.5 rounded-full bg-primary" title="已修改" />
              )}
              
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  editor.closeTab(tab.path);
                }}
                className="ml-1 hover:bg-muted-foreground/20 rounded p-0.5 transition-colors"
                title="關閉"
              >
                <X className="h-3 w-3" />
              </button>
            </button>
          ))}
        </div>
      )}

      {/* 編輯器區域 */}
      <div className="flex-1 overflow-hidden">
        {editor.activeTab ? (
          renderEditor ? (
            renderEditor(editor.activeTab)
          ) : (
            defaultRenderEditor(editor.activeTab)
          )
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            選擇一個檔案開始編輯
          </div>
        )}
      </div>
    </div>
  );
};

