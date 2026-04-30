import React, { useEffect, useRef, useState, type ReactNode } from 'react';
import { AlertCircle, Download, Image as ImageIcon, RefreshCw, RotateCw, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { createLogger } from '@/shared/services/logger';
import type { FileViewerWorkbenchAdapter } from './types';

const logger = createLogger('SharedImageViewer');

interface SharedImageViewerProps {
  filePath: string;
  fileName: string;
  adapter: FileViewerWorkbenchAdapter;
  className?: string;
  i18nBase?: string;
  isFocusMode?: boolean;
  renderFocusToolbar?: (params: {
    actions: ReactNode;
    title: string;
    subtitle: string;
    metadata: ReactNode;
  }) => ReactNode;
}

export const SharedImageViewer: React.FC<SharedImageViewerProps> = ({
  filePath,
  fileName,
  adapter,
  className,
  i18nBase = 'shared.fileViewer.image',
  isFocusMode = false,
  renderFocusToolbar,
}) => {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const currentBlobUrlRef = useRef<string | null>(null);
  const [imageUrl, setImageUrl] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadImage = async () => {
      if (!adapter.readBlob) {
        setError(t(`${i18nBase}.unavailable`));
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError('');

      if (currentBlobUrlRef.current) {
        URL.revokeObjectURL(currentBlobUrlRef.current);
        currentBlobUrlRef.current = null;
      }

      try {
        const blob = await adapter.readBlob(filePath);
        const blobUrl = URL.createObjectURL(blob);
        if (isMounted) {
          currentBlobUrlRef.current = blobUrl;
          setImageUrl(blobUrl);
          setIsLoading(false);
        } else {
          URL.revokeObjectURL(blobUrl);
        }
      } catch (loadError) {
        logger.error('Failed to load image', { error: loadError });
        if (isMounted) {
          setError(t(`${i18nBase}.error`));
          setIsLoading(false);
        }
      }
    };

    void loadImage();

    return () => {
      isMounted = false;
    };
  }, [adapter, filePath, i18nBase, t]);

  useEffect(() => () => {
    if (currentBlobUrlRef.current) {
      URL.revokeObjectURL(currentBlobUrlRef.current);
      currentBlobUrlRef.current = null;
    }
  }, []);

  const handleImageLoad = (event: React.SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setImageDimensions({
      width: image.naturalWidth,
      height: image.naturalHeight,
    });
    setIsLoading(false);
    setError('');
  };

  const handleImageError = (event: React.SyntheticEvent<HTMLImageElement>) => {
    logger.error('Image failed to load', { src: event.currentTarget.src });
    setError(t(`${i18nBase}.error`));
    setIsLoading(false);
  };

  const handleZoomIn = () => setZoom((current) => Math.min(current + 0.25, 5));
  const handleZoomOut = () => setZoom((current) => Math.max(current - 0.25, 0.25));
  const handleResetZoom = () => {
    setZoom(1);
    setRotation(0);
  };
  const handleRotate = () => setRotation((current) => (current + 90) % 360);

  const handleDownload = () => {
    if (!imageUrl) return;
    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const toolbarActions = (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleZoomOut}
        disabled={zoom <= 0.25}
        title={t(`${i18nBase}.zoomOut`)}
        aria-label={t(`${i18nBase}.zoomOut`)}
      >
        <ZoomOut className="h-4 w-4" />
      </Button>
      <span className="min-w-[3rem] text-center text-xs text-muted-foreground">
        {Math.round(zoom * 100)}%
      </span>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleZoomIn}
        disabled={zoom >= 5}
        title={t(`${i18nBase}.zoomIn`)}
        aria-label={t(`${i18nBase}.zoomIn`)}
      >
        <ZoomIn className="h-4 w-4" />
      </Button>
      <div className="mx-1 h-4 w-px bg-border" />
      <Button
        variant="ghost"
        size="sm"
        onClick={handleRotate}
        title={t(`${i18nBase}.rotate`)}
        aria-label={t(`${i18nBase}.rotate`)}
      >
        <RotateCw className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleResetZoom}
        title={t(`${i18nBase}.reset`)}
        aria-label={t(`${i18nBase}.reset`)}
      >
        <RefreshCw className="h-4 w-4" />
      </Button>
      <div className="mx-1 h-4 w-px bg-border" />
      <Button
        variant="ghost"
        size="sm"
        onClick={handleDownload}
        disabled={!imageUrl}
        title={t(`${i18nBase}.download`)}
        aria-label={t(`${i18nBase}.download`)}
      >
        <Download className="h-4 w-4" />
      </Button>
    </>
  );

  const metadata = imageDimensions ? <span>{imageDimensions.width} × {imageDimensions.height}</span> : null;

  return (
    <div ref={containerRef} className={cn('flex h-full flex-col bg-muted/10', className)}>
      {isFocusMode && renderFocusToolbar ? (
        renderFocusToolbar({
          actions: toolbarActions,
          title: fileName,
          subtitle: filePath,
          metadata,
        })
      ) : (
        <div className="flex items-center justify-between border-b border-border bg-background/95 px-4 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex items-center gap-2">
            <ImageIcon className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">{fileName}</span>
            {imageDimensions && (
              <span className="text-xs text-muted-foreground">{imageDimensions.width} × {imageDimensions.height}</span>
            )}
          </div>
          <div className="flex items-center gap-1">{toolbarActions}</div>
        </div>
      )}

      <div className="flex-1 overflow-auto bg-[radial-gradient(circle_at_1px_1px,_rgb(var(--muted-foreground)_/_0.15)_1px,_transparent_0)] [background-size:20px_20px]">
        {error ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <AlertCircle className="mx-auto mb-4 h-12 w-12 text-destructive opacity-50" />
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <RefreshCw className="mx-auto mb-4 h-12 w-12 animate-spin opacity-50" />
              <p className="text-sm text-muted-foreground">{t(`${i18nBase}.loading`)}</p>
            </div>
          </div>
        ) : imageUrl ? (
          <div className="flex h-full items-center justify-center p-4">
            <img
              ref={imageRef}
              src={imageUrl}
              alt={fileName}
              onLoad={handleImageLoad}
              onError={handleImageError}
              className="max-h-full max-w-full object-contain transition-transform duration-200"
              style={{
                transform: `scale(${zoom}) rotate(${rotation}deg)`,
                transformOrigin: 'center center',
              }}
            />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="flex items-center text-sm">
              <ImageIcon className="mr-2 h-4 w-4" />
              {t(`${i18nBase}.empty`)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
