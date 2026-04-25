/**
 * Mermaid 圖表預覽組件
 * 提供 Mermaid 圖表的渲染和互動功能
 */

import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import {
  ZoomIn,
  ZoomOut,
  Download,
  RefreshCw,
  AlertCircle,
  Copy,
  Check
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { createLogger } from '@/shared/services/logger';
import { FileFocusToolbar } from './FileFocusToolbar';

const logger = createLogger('MermaidViewer');

interface MermaidViewerProps {
  content: string;
  fileName: string;
  className?: string;
  isFocusMode?: boolean;
  onExitFocusMode?: () => void;
}

export const MermaidViewer: React.FC<MermaidViewerProps> = ({
  content,
  fileName,
  className,
  isFocusMode = false,
  onExitFocusMode,
}) => {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [isRendering, setIsRendering] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [copied, setCopied] = useState(false);

  // 初始化 Mermaid
  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
      securityLevel: 'loose',
      fontFamily: 'inherit',
      flowchart: {
        useMaxWidth: true,
        htmlLabels: true,
        curve: 'basis'
      },
      sequence: {
        useMaxWidth: true,
        wrap: true
      },
      gantt: {
        useMaxWidth: true
      }
    });
  }, []);

  // 渲染 Mermaid 圖表
  useEffect(() => {
    if (!content.trim()) {
      setSvg('');
      setError('');
      return;
    }

    const renderDiagram = async () => {
      setIsRendering(true);
      setError('');

      try {
        // 生成唯一 ID
        const id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        
        // 渲染圖表
        const { svg: renderedSvg } = await mermaid.render(id, content);
        setSvg(renderedSvg);
      } catch (err) {
        logger.error('Mermaid rendering error', { error: err });
        setError(err instanceof Error ? err.message : 'Unknown error');
        setSvg('');
      } finally {
        setIsRendering(false);
      }
    };

    renderDiagram();
  }, [content]);

  // 縮放控制
  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.1, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.1, 0.3));
  };

  const handleResetZoom = () => {
    setZoom(1);
  };

  // 下載 SVG
  const handleDownload = () => {
    if (!svg) return;

    const blob = new Blob([svg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName.replace(/\.(mmd|mermaid)$/, '.svg');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // 複製 SVG
  const handleCopySvg = async () => {
    if (!svg) return;

    try {
      await navigator.clipboard.writeText(svg);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      logger.error('Failed to copy SVG', { error: err });
    }
  };

  const toolbarActions = (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleZoomOut}
        disabled={zoom <= 0.3}
        title={t('workspace.fileManagement.mermaid.zoomOut')}
      >
        <ZoomOut className="w-4 h-4" />
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={handleResetZoom}
        title={t('workspace.fileManagement.mermaid.resetZoom')}
      >
        <span className="text-xs font-mono">{Math.round(zoom * 100)}%</span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={handleZoomIn}
        disabled={zoom >= 3}
        title={t('workspace.fileManagement.mermaid.zoomIn')}
      >
        <ZoomIn className="w-4 h-4" />
      </Button>

      <div className="w-px h-4 bg-border mx-1" />

      <Button
        variant="ghost"
        size="sm"
        onClick={handleCopySvg}
        disabled={!svg}
        title={t('workspace.fileManagement.mermaid.copySvg')}
      >
        {copied ? (
          <Check className="w-4 h-4 text-green-500" />
        ) : (
          <Copy className="w-4 h-4" />
        )}
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={handleDownload}
        disabled={!svg}
        title={t('workspace.fileManagement.mermaid.download')}
      >
        <Download className="w-4 h-4" />
      </Button>
    </>
  );

  return (
    <div
      ref={containerRef}
      className={cn(
        "h-full flex flex-col bg-background",
        className
      )}
    >
      {/* 工具列 */}
      {isFocusMode && onExitFocusMode ? (
        <FileFocusToolbar
          title={fileName}
          subtitle={t('workspace.fileManagement.mermaid.title')}
          actions={toolbarActions}
          exitLabel={t('workspace.fileManagement.focus.exit')}
          onExit={onExitFocusMode}
        />
      ) : (
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">
            {t('workspace.fileManagement.mermaid.title')}
          </span>
          {isRendering && (
            <RefreshCw className="w-4 h-4 animate-spin text-muted-foreground" />
          )}
        </div>

        <div className="flex items-center gap-1">
          {toolbarActions}
        </div>
      </div>
      )}

      {/* 圖表顯示區域 */}
      <div className="flex-1 overflow-auto bg-background">
        {error ? (
          <div className="h-full flex items-center justify-center p-8">
            <div className="max-w-2xl text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 text-destructive" />
              <h3 className="text-lg font-semibold mb-2 text-foreground">
                {t('workspace.fileManagement.mermaid.error.title')}
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t('workspace.fileManagement.mermaid.error.description')}
              </p>
              <pre className="text-xs text-left bg-muted p-4 rounded-lg overflow-auto">
                {error}
              </pre>
            </div>
          </div>
        ) : svg ? (
          <div 
            className="flex items-center justify-center min-h-full p-8"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'center',
              transition: 'transform 0.2s ease-out'
            }}
          >
            <div 
              dangerouslySetInnerHTML={{ __html: svg }}
              className="mermaid-diagram"
            />
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <RefreshCw className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-sm">
                {isRendering 
                  ? t('workspace.fileManagement.mermaid.rendering')
                  : t('workspace.fileManagement.mermaid.empty')
                }
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
