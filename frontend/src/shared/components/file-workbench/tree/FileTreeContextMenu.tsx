/**
 * 
 */

import React, { useRef, useEffect } from 'react';
import { FileTreeContextMenuItems, type FileTreeContextMenuAction } from '@/shared/components/file-workbench/primitives/FileTreeContextMenuItems';
import type { ContextMenuState } from '../types';

export interface FileTreeContextMenuProps {
  contextMenu: ContextMenuState | null;
  
  items: FileTreeContextMenuAction[];
  
  onClose: () => void;
  
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


    if (x + menuRect.width > viewportWidth) {
      x = viewportWidth - menuRect.width - 10;
    }


    if (y + menuRect.height > viewportHeight) {
      y = viewportHeight - menuRect.height - 10;
    }


    if (x < 10) {
      x = 10;
    }


    if (y < 10) {
      y = 10;
    }

    setPosition({ x, y });
  }, [contextMenu]);


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

