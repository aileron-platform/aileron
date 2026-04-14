import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { cn } from '@/shared/utils/cn';
import { Button } from '@/shared/components/ui/button';
import { ChevronRight, ChevronLeft, FileText } from 'lucide-react';

interface ColumnsLayoutContextValue {
  primaryOpen: boolean;
  togglePrimary: () => void;
  secondaryOpen: boolean;
  toggleSecondary: () => void;
}

const ColumnsLayoutContext = createContext<ColumnsLayoutContextValue | null>(null);

export const useColumnsLayout = (): ColumnsLayoutContextValue => {
  const ctx = useContext(ColumnsLayoutContext);
  if (!ctx) throw new Error('useColumnsLayout must be used within <ColumnsLayout>');
  return ctx;
};

interface ColumnsLayoutProps {
  className?: string;
  children?: React.ReactNode;
  defaultPrimaryOpen?: boolean;
  defaultSecondaryOpen?: boolean;
  // 受控：由外部控制開關（若提供則覆蓋內部狀態）
  primaryOpen?: boolean;
  onPrimaryOpenChange?: (open: boolean) => void;
  secondaryOpen?: boolean;
  onSecondaryOpenChange?: (open: boolean) => void;
}

/**
 * ColumnsLayout
 * - 提供兩/三欄佈局，並集中管理第一欄/第二欄的收折狀態
 * - 子元件：PrimarySidebar、SecondaryPane、Content
 */
export const ColumnsLayout: React.FC<ColumnsLayoutProps> & {
  PrimarySidebar: React.FC<PrimarySidebarProps>;
  SecondaryPane: React.FC<SecondaryPaneProps>;
  Content: React.FC<ContentProps>;
} = ({ className, children, defaultPrimaryOpen = true, defaultSecondaryOpen = true, primaryOpen: controlledPrimaryOpen, onPrimaryOpenChange, secondaryOpen: controlledSecondaryOpen, onSecondaryOpenChange, }) => {
  const [primaryOpenState, setPrimaryOpenState] = useState<boolean>(defaultPrimaryOpen);
  const [secondaryOpenState, setSecondaryOpenState] = useState<boolean>(defaultSecondaryOpen);

  const primaryOpen = controlledPrimaryOpen ?? primaryOpenState;
  const secondaryOpen = controlledSecondaryOpen ?? secondaryOpenState;

  const togglePrimary = useCallback(() => {
    if (onPrimaryOpenChange) onPrimaryOpenChange(!primaryOpen);
    else setPrimaryOpenState(v => !v);
  }, [onPrimaryOpenChange, primaryOpen]);
  const toggleSecondary = useCallback(() => {
    if (onSecondaryOpenChange) onSecondaryOpenChange(!secondaryOpen);
    else setSecondaryOpenState(v => !v);
  }, [onSecondaryOpenChange, secondaryOpen]);

  const value = useMemo<ColumnsLayoutContextValue>(() => ({
    primaryOpen,
    togglePrimary,
    secondaryOpen,
    toggleSecondary,
  }), [primaryOpen, secondaryOpen, togglePrimary, toggleSecondary]);

  return (
    <ColumnsLayoutContext.Provider value={value}>
      <div className={cn('flex h-full overflow-hidden', className)}>{children}</div>
    </ColumnsLayoutContext.Provider>
  );
};

interface PrimarySidebarProps {
  className?: string;
  children?: React.ReactNode;
  width?: number; // px (uncontrolled 初始寬度)
  controlledWidth?: number; // 受控寬度（如提供則覆蓋內部 state）
  onWidthChange?: (w: number) => void; // 受控寬度回呼
  collapsedWidth?: number; // px，收折時的「圖示欄」寬度（預設 64）
  minWidth?: number; // px，拖曳調整的最小寬度
  maxWidth?: number; // px，拖曳調整的最大寬度
}

const PrimarySidebarImpl: React.FC<PrimarySidebarProps> = ({ className, children, width = 320, controlledWidth, onWidthChange, collapsedWidth = 64, minWidth = 200, maxWidth = 640 }) => {
  const { primaryOpen, togglePrimary } = useColumnsLayout();
  const [wState, setWState] = useState<number>(width);
  const [dragging, setDragging] = useState<boolean>(false);
  const current = controlledWidth ?? wState;
  const w = primaryOpen ? current : collapsedWidth;

  const onDrag = (e: React.MouseEvent) => {
    if (!primaryOpen) return;
    setDragging(true);
    const startX = e.clientX;
    const startW = current;
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - startX;
      const next = Math.max(minWidth, Math.min(maxWidth, startW - dx));
      if (onWidthChange) onWidthChange(next); else setWState(next);
    };
    const onUp = () => {
      setDragging(false);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  return (
    <div
      className={cn('h-full shrink-0 transition-[width] duration-200 overflow-hidden relative select-none', className)}
      style={{ width: w }}
      data-collapsed={!primaryOpen}
    >
      {primaryOpen ? (
        <>
          {children}
          {/* Resizer Handle (Primary|next) */}
          <div
            className={cn(
              'absolute right-0 top-0 h-full w-1 cursor-col-resize z-10 transition-colors',
              dragging ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20'
            )}
            onMouseDown={onDrag}
            role="separator"
            aria-orientation="vertical"
            aria-label="調整欄寬"
          />
        </>
      ) : (
        <div className="h-full flex flex-col items-center">
          <div className="h-10 w-full flex items-center justify-center border-b border-border">
            <Button variant="ghost" size="icon" onClick={togglePrimary} aria-label="展開左欄">
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex-1 w-full flex items-start justify-center pt-3">
            <FileText className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
      )}
    </div>
  );
};

interface SecondaryPaneProps {
  className?: string;
  children?: React.ReactNode;
  width?: number; // px (uncontrolled 初始寬度)
  controlledWidth?: number; // 受控寬度
  onWidthChange?: (w: number) => void; // 受控寬度回呼
  scrollable?: boolean; // 預設 true，提供獨立捲軸
  collapsedWidth?: number; // px，收折時的「圖示欄」寬度（預設 64）
  minWidth?: number; // px
  maxWidth?: number; // px
}

const SecondaryPaneImpl: React.FC<SecondaryPaneProps> = ({ className, children, width = 360, controlledWidth, onWidthChange, scrollable = true, collapsedWidth = 64, minWidth = 250, maxWidth = 680 }) => {
  const { secondaryOpen, toggleSecondary } = useColumnsLayout();
  const [wState, setWState] = useState<number>(width);
  const [dragging, setDragging] = useState<boolean>(false);
  const current = controlledWidth ?? wState;
  const w = secondaryOpen ? current : collapsedWidth;

  const onDrag = (e: React.MouseEvent) => {
    if (!secondaryOpen) return;
    setDragging(true);
    const startX = e.clientX;
    const startW = current;
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - startX;
      const next = Math.max(minWidth, Math.min(maxWidth, startW - dx));
      if (onWidthChange) onWidthChange(next); else setWState(next);
    };
    const onUp = () => {
      setDragging(false);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  return (
    <div
      className={cn('h-full shrink-0 transition-[width] duration-200 min-h-0 relative select-none', scrollable && 'overflow-y-auto', className)}
      style={{ width: w }}
      data-collapsed={!secondaryOpen}
    >
      {secondaryOpen ? (
        <>
          {children}
          {/* Resizer Handle (Secondary|next) */}
          <div
            className={cn(
              'absolute right-0 top-0 h-full w-1 cursor-col-resize z-10 transition-colors',
              dragging ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20'
            )}
            onMouseDown={onDrag}
            role="separator"
            aria-orientation="vertical"
            aria-label="調整欄寬"
          />
        </>
      ) : (
        <div className="h-full flex flex-col items-center">
          <div className="h-10 w-full flex items-center justify-center border-b border-border">
            <Button variant="ghost" size="icon" onClick={toggleSecondary} aria-label="展開中欄">
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex-1 w-full flex items-start justify-center pt-3">
            <FileText className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
      )}
    </div>
  );
};

interface ContentProps {
  className?: string;
  children?: React.ReactNode;
  scrollable?: boolean; // 預設 true，提供獨立捲軸
}

const ContentImpl: React.FC<ContentProps> = ({ className, children, scrollable = true }) => {
  return (
    <div className={cn('flex-1 min-h-0 flex flex-col', scrollable && 'overflow-y-auto', className)}>
      {children}
    </div>
  );
};

ColumnsLayout.PrimarySidebar = PrimarySidebarImpl;
ColumnsLayout.SecondaryPane = SecondaryPaneImpl;
ColumnsLayout.Content = ContentImpl;

export default ColumnsLayout;
