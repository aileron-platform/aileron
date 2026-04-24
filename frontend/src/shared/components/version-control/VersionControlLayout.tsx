import React, { useCallback, useEffect, useState } from 'react';
import { cn } from '@/shared/utils/cn';

interface VersionControlLayoutProps {
  modeRail: React.ReactNode;
  sidebar: React.ReactNode;
  main: React.ReactNode;
  className?: string;
}

type DragTarget = 'modeRail' | 'sidebar' | null;

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export const VersionControlLayout: React.FC<VersionControlLayoutProps> = ({
  modeRail,
  sidebar,
  main,
  className,
}) => {
  const [modeRailWidth, setModeRailWidth] = useState(192);
  const [sidebarWidth, setSidebarWidth] = useState(320);
  const [dragTarget, setDragTarget] = useState<DragTarget>(null);
  const [dragStart, setDragStart] = useState({ x: 0, width: 0 });

  const handleMouseDown = useCallback((
    event: React.MouseEvent<HTMLDivElement>,
    target: Exclude<DragTarget, null>,
    currentWidth: number,
  ) => {
    event.preventDefault();
    setDragTarget(target);
    setDragStart({ x: event.clientX, width: currentWidth });
  }, []);

  useEffect(() => {
    if (!dragTarget) {
      return;
    }

    const handleMouseMove = (event: MouseEvent) => {
      const delta = event.clientX - dragStart.x;
      if (dragTarget === 'modeRail') {
        setModeRailWidth(clamp(dragStart.width + delta, 144, 280));
      } else {
        setSidebarWidth(clamp(dragStart.width + delta, 250, 600));
      }
    };

    const handleMouseUp = () => {
      setDragTarget(null);
    };

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragStart.width, dragStart.x, dragTarget]);

  return (
    <div
      data-testid="version-control-layout"
      className={cn('flex h-full min-h-0 overflow-hidden bg-background', className)}
    >
      <div
        data-testid="version-control-mode-rail"
        className="relative min-h-0 shrink-0 border-r border-border"
        style={{ width: modeRailWidth }}
      >
        {modeRail}
        <div
          className={cn(
            'absolute right-0 top-0 h-full w-1 cursor-col-resize transition-colors',
            dragTarget === 'modeRail' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
          )}
          onMouseDown={(event) => handleMouseDown(event, 'modeRail', modeRailWidth)}
        />
      </div>
      <div
        data-testid="version-control-sidebar"
        className="relative min-h-0 shrink-0 border-r border-border"
        style={{ width: sidebarWidth }}
      >
        {sidebar}
        <div
          className={cn(
            'absolute right-0 top-0 h-full w-1 cursor-col-resize transition-colors',
            dragTarget === 'sidebar' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
          )}
          onMouseDown={(event) => handleMouseDown(event, 'sidebar', sidebarWidth)}
        />
      </div>
      <div data-testid="version-control-main" className="min-h-0 min-w-0 flex-1">
        {main}
      </div>
    </div>
  );
};

export default VersionControlLayout;
