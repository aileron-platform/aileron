import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Check, Copy, Download, RefreshCw, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { createLogger } from '@/shared/services/logger';
import { useFileViewerWorkbench } from './FileViewerWorkbenchContext';

const logger = createLogger('SharedMermaidViewer');
type MermaidApi = typeof import('mermaid').default;

let mermaidPromise: Promise<MermaidApi> | null = null;

const loadMermaid = async (): Promise<MermaidApi> => {
  mermaidPromise ??= import('mermaid').then((module) => module.default);
  return mermaidPromise;
};

const getPointerCoordinate = (value: number): number => (Number.isFinite(value) ? value : 0);

interface SharedMermaidViewerProps {
  content: string;
  fileName: string;
  className?: string;
  i18nBase?: string;
}

export const SharedMermaidViewer: React.FC<SharedMermaidViewerProps> = ({
  content,
  fileName,
  className,
  i18nBase = 'shared.fileViewer.mermaid',
}) => {
  const { t } = useI18n();
  const { registerFormatActions } = useFileViewerWorkbench();
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');
  const [isRendering, setIsRendering] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [copied, setCopied] = useState(false);
  const panStartRef = useRef<{
    pointerId: number;
    clientX: number;
    clientY: number;
    panX: number;
    panY: number;
  } | null>(null);

  useEffect(() => {
    if (!content.trim()) {
      setSvg('');
      setError('');
      return;
    }

    let isMounted = true;

    const renderDiagram = async () => {
      setIsRendering(true);
      setError('');

      try {
        const mermaid = await loadMermaid();
        mermaid.initialize({
          startOnLoad: false,
          theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
          securityLevel: 'loose',
          fontFamily: 'inherit',
          flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' },
          sequence: { useMaxWidth: true, wrap: true },
          gantt: { useMaxWidth: true },
        });
        const id = `shared-mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
        const { svg: renderedSvg } = await mermaid.render(id, content);
        if (isMounted) {
          setSvg(renderedSvg);
          setZoom(1);
          setPan({ x: 0, y: 0 });
        }
      } catch (renderError) {
        logger.error('Mermaid rendering error', { error: renderError });
        if (isMounted) {
          setError(renderError instanceof Error ? renderError.message : 'Unknown error');
          setSvg('');
        }
      } finally {
        if (isMounted) {
          setIsRendering(false);
        }
      }
    };

    void renderDiagram();

    return () => {
      isMounted = false;
    };
  }, [content]);

  const handleZoomIn = useCallback(() => setZoom((current) => Math.min(current + 0.1, 3)), []);
  const handleZoomOut = useCallback(() => {
    setZoom((current) => {
      const nextZoom = Math.max(current - 0.1, 0.3);
      if (nextZoom <= 1) {
        setPan({ x: 0, y: 0 });
      }
      return nextZoom;
    });
  }, []);
  const handleResetZoom = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const handlePanStart = (event: React.PointerEvent<HTMLDivElement>) => {
    if ((event.pointerType === 'mouse' && event.button !== 0) || !svg) return;
    panStartRef.current = {
      pointerId: event.pointerId,
      clientX: getPointerCoordinate(event.clientX),
      clientY: getPointerCoordinate(event.clientY),
      panX: pan.x,
      panY: pan.y,
    };
    setIsPanning(true);
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const handlePanMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const panStart = panStartRef.current;
    if (!panStart || panStart.pointerId !== event.pointerId) return;
    event.preventDefault();
    setPan({
      x: panStart.panX + getPointerCoordinate(event.clientX) - panStart.clientX,
      y: panStart.panY + getPointerCoordinate(event.clientY) - panStart.clientY,
    });
  };

  const handlePanEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    const panStart = panStartRef.current;
    if (!panStart || panStart.pointerId !== event.pointerId) return;
    panStartRef.current = null;
    setIsPanning(false);
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleDownload = useCallback(() => {
    if (!svg) return;
    const blob = new Blob([svg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName.replace(/\.(mmd|mermaid)$/i, '.svg');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [fileName, svg]);

  const handleCopySvg = useCallback(async () => {
    if (!svg) return;
    try {
      await navigator.clipboard.writeText(svg);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (copyError) {
      logger.error('Failed to copy SVG', { error: copyError });
    }
  }, [svg]);

  const toolbarActions = useMemo(() => (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleZoomOut}
        disabled={zoom <= 0.3}
        title={t(`${i18nBase}.zoomOut`)}
        aria-label={t(`${i18nBase}.zoomOut`)}
      >
        <ZoomOut className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleResetZoom}
        title={t(`${i18nBase}.resetZoom`)}
        aria-label={t(`${i18nBase}.resetZoom`)}
      >
        <span className="font-mono text-xs">{Math.round(zoom * 100)}%</span>
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleZoomIn}
        disabled={zoom >= 3}
        title={t(`${i18nBase}.zoomIn`)}
        aria-label={t(`${i18nBase}.zoomIn`)}
      >
        <ZoomIn className="h-4 w-4" />
      </Button>
      <div className="mx-1 h-4 w-px bg-border" />
      <Button
        variant="ghost"
        size="sm"
        onClick={() => void handleCopySvg()}
        disabled={!svg}
        title={t(`${i18nBase}.copySvg`)}
        aria-label={t(`${i18nBase}.copySvg`)}
      >
        {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleDownload}
        disabled={!svg}
        title={t(`${i18nBase}.download`)}
        aria-label={t(`${i18nBase}.download`)}
      >
        <Download className="h-4 w-4" />
      </Button>
    </>
  ), [
    copied,
    handleCopySvg,
    handleDownload,
    handleResetZoom,
    handleZoomIn,
    handleZoomOut,
    i18nBase,
    svg,
    t,
    zoom,
  ]);

  useEffect(() => {
    registerFormatActions(toolbarActions);
    return () => registerFormatActions(null);
  }, [registerFormatActions, toolbarActions]);

  return (
    <div ref={containerRef} className={cn('flex h-full flex-col bg-background', className)}>
      <div className="flex-1 overflow-auto bg-background">
        {error ? (
          <div className="flex h-full items-center justify-center p-8">
            <div className="max-w-2xl text-center">
              <AlertCircle className="mx-auto mb-4 h-12 w-12 text-destructive" />
              <h3 className="mb-2 text-lg font-semibold text-foreground">{t(`${i18nBase}.error.title`)}</h3>
              <p className="mb-4 text-sm text-muted-foreground">{t(`${i18nBase}.error.description`)}</p>
              <pre className="overflow-auto rounded-lg bg-muted p-4 text-left text-xs">{error}</pre>
            </div>
          </div>
        ) : svg ? (
          <div
            data-testid="mermaid-pan-surface"
            className="flex min-h-full cursor-grab touch-none select-none items-center justify-center p-8 active:cursor-grabbing"
            onPointerDown={handlePanStart}
            onPointerMove={handlePanMove}
            onPointerUp={handlePanEnd}
            onPointerCancel={handlePanEnd}
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: 'center',
              transition: isPanning ? 'none' : 'transform 0.2s ease-out',
            }}
          >
            <div dangerouslySetInnerHTML={{ __html: svg }} className="mermaid-diagram" />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <RefreshCw className="mx-auto mb-4 h-12 w-12 opacity-50" />
              <p className="text-sm">
                {isRendering ? t(`${i18nBase}.rendering`) : t(`${i18nBase}.empty`)}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
