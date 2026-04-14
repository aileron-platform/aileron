/**
 * 統一的檔案樹右鍵選單組件
 * 
 * 提供標準的右鍵選單容器和自動關閉功能
 */

import React, { useRef, useEffect } from 'react';
import { FileTreeContextMenuItems, type FileTreeContextMenuAction } from '@/shared/components/file-tree/FileTreeContextMenuItems';
import type { ContextMenuState } from '../types';

export interface FileTreeContextMenuProps {
  /** 右鍵選單狀態 */
  contextMenu: ContextMenuState | null;
  
  /** 選單項目 */
  items: FileTreeContextMenuAction[];
  
  /** 關閉選單回調 */
  onClose: () => void;
  
  /** 自定義 className */
  className?: string;
  
  /** z-index */
  zIndex?: number;
}

export const FileTreeContextMenu: React.FC<FileTreeContextMenuProps> = ({
  contextMenu,
  items,
  onClose,
  className = '',
  zIndex = 50,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = React.useState({ x: 0, y: 0 });

  // 計算選單位置，避免超出視窗邊界
  useEffect(() => {
    if (!contextMenu || !menuRef.current) {
      return;
    }

    const menu = menuRef.current;
    const menuRect = menu.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    let x = contextMenu.x;
    let y = contextMenu.y;

    // 檢查右邊界
    if (x + menuRect.width > viewportWidth) {
      x = viewportWidth - menuRect.width - 10; // 10px 邊距
    }

    // 檢查下邊界
    if (y + menuRect.height > viewportHeight) {
      y = viewportHeight - menuRect.height - 10; // 10px 邊距
    }

    // 確保不超出左邊界
    if (x < 10) {
      x = 10;
    }

    // 確保不超出上邊界
    if (y < 10) {
      y = 10;
    }

    setPosition({ x, y });
  }, [contextMenu]);

  // 點擊外部關閉選單
  useEffect(() => {
    if (!contextMenu) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    const handleContextMenu = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('contextmenu', handleContextMenu);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('contextmenu', handleContextMenu);
    };
  }, [contextMenu, onClose]);

  if (!contextMenu) {
    return null;
  }

  return (
    <div
      ref={menuRef}
      className={`fixed bg-background border border-border rounded-md shadow-lg py-1 min-w-40 ${className}`}
      style={{
        left: position.x,
        top: position.y,
        zIndex,
      }}
    >
      <FileTreeContextMenuItems items={items} />
    </div>
  );
};

export default FileTreeContextMenu;

