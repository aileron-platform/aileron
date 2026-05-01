import React from 'react';

export const KNOWLEDGE_BASE_COLLAPSED_COLUMN_WIDTH = 64;
export const KNOWLEDGE_BASE_DEFAULT_COLUMN_WIDTH = 256;
export const KNOWLEDGE_BASE_PREVIEW_COLUMN_WIDTH = 400;
export const KNOWLEDGE_BASE_MIN_COLUMN_WIDTH = 220;
export const KNOWLEDGE_BASE_MAX_COLUMN_WIDTH = 600;

interface UseResizableSidebarOptions {
  initialWidth?: number;
  initialCollapsed?: boolean;
  minWidth?: number;
  maxWidth?: number;
  resizeFrom?: 'left' | 'right';
  onWidthChange?: (width: number) => void;
}

interface UseResizableSidebarResult {
  width: number;
  collapsed: boolean;
  isResizing: boolean;
  setWidth: (width: number) => void;
  setCollapsed: (collapsed: boolean) => void;
  startResize: (event: React.MouseEvent) => void;
}

export const useResizableSidebar = (
  options: UseResizableSidebarOptions = {},
): UseResizableSidebarResult => {
  const {
    initialWidth = KNOWLEDGE_BASE_DEFAULT_COLUMN_WIDTH,
    initialCollapsed = false,
    minWidth = KNOWLEDGE_BASE_MIN_COLUMN_WIDTH,
    maxWidth = KNOWLEDGE_BASE_MAX_COLUMN_WIDTH,
    resizeFrom = 'right',
    onWidthChange,
  } = options;
  const sign = resizeFrom === 'left' ? -1 : 1;

  const [width, setWidth] = React.useState(initialWidth);
  const [collapsed, setCollapsed] = React.useState(initialCollapsed);
  const [isResizing, setIsResizing] = React.useState(false);
  const dragStateRef = React.useRef<{ startX: number; startWidth: number } | null>(null);
  const onWidthChangeRef = React.useRef(onWidthChange);
  onWidthChangeRef.current = onWidthChange;

  const startResize = React.useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    dragStateRef.current = { startX: event.clientX, startWidth: width };
    document.body.classList.add('select-none', 'cursor-col-resize');
    setIsResizing(true);
  }, [width]);

  React.useEffect(() => {
    if (!isResizing) {
      return;
    }

    const handleMouseMove = (event: MouseEvent) => {
      const dragState = dragStateRef.current;
      if (!dragState) {
        return;
      }

      const delta = event.clientX - dragState.startX;
      const nextWidth = Math.min(Math.max(dragState.startWidth + sign * delta, minWidth), maxWidth);
      setWidth(nextWidth);
      onWidthChangeRef.current?.(nextWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      dragStateRef.current = null;
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      dragStateRef.current = null;
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };
  }, [isResizing, maxWidth, minWidth, sign]);

  return {
    width,
    collapsed,
    isResizing,
    setWidth,
    setCollapsed,
    startResize,
  };
};

interface ResizableSidebarHandleProps {
  side?: 'left' | 'right';
  isResizing: boolean;
  onResizeStart: (event: React.MouseEvent) => void;
}

export const ResizableSidebarHandle: React.FC<ResizableSidebarHandleProps> = ({
  side = 'right',
  isResizing,
  onResizeStart,
}) => {
  const positionClass = side === 'right' ? 'right-0' : 'left-0';
  const baseClass = `absolute ${positionClass} top-0 h-full w-1 cursor-col-resize transition-colors`;
  const stateClass = isResizing ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20';
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      className={`${baseClass} ${stateClass}`}
      onMouseDown={onResizeStart}
    />
  );
};
