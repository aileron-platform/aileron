import React, { useCallback, useEffect, useRef, useState } from 'react';
import { cn } from '@/shared/utils/cn';

interface VersionControlResizablePanelsProps {
  top: React.ReactNode;
  bottom: React.ReactNode;
  initialTopPercent?: number;
  minPercent?: number;
  maxPercent?: number;
  className?: string;
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export const VersionControlResizablePanels: React.FC<VersionControlResizablePanelsProps> = ({
  top,
  bottom,
  initialTopPercent = 50,
  minPercent = 20,
  maxPercent = 80,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [topPercent, setTopPercent] = useState(initialTopPercent);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ y: 0, topPercent: initialTopPercent });

  const handleMouseDown = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(true);
    dragStartRef.current = { y: event.clientY, topPercent };
  }, [topPercent]);

  useEffect(() => {
    if (!isDragging) {
      return;
    }

    const handleMouseMove = (event: MouseEvent) => {
      if (!containerRef.current) {
        return;
      }
      const containerRect = containerRef.current.getBoundingClientRect();
      const deltaY = event.clientY - dragStartRef.current.y;
      const deltaPercent = (deltaY / containerRect.height) * 100;
      setTopPercent(clamp(dragStartRef.current.topPercent + deltaPercent, minPercent, maxPercent));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, maxPercent, minPercent]);

  return (
    <div ref={containerRef} className={cn('flex min-h-0 flex-1 flex-col file-panels-container', className)}>
      <div className="min-h-0 overflow-hidden" style={{ height: `${topPercent}%` }}>
        {top}
      </div>
      <div
        className={cn(
          'h-1 flex-shrink-0 cursor-row-resize bg-border transition-colors hover:bg-primary/50',
          isDragging && 'bg-primary',
        )}
        onMouseDown={handleMouseDown}
      />
      <div className="min-h-0 overflow-hidden" style={{ height: `${100 - topPercent}%` }}>
        {bottom}
      </div>
    </div>
  );
};
