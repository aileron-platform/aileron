import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Download, Image as ImageIcon, RefreshCw, RotateCw, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { createLogger } from '@/shared/services/logger';
import { useFileViewerWorkbench } from './FileViewerWorkbenchContext';
import type { FileViewerWorkbenchAdapter } from './types';

const logger = createLogger('ImageViewer');

type ImageLoadError = 'unavailable' | 'error' | null;

interface ImageViewerProps {
  filePath: string;
  fileName: string;
  adapter: FileViewerWorkbenchAdapter;
  className?: string;
  i18nBase?: string;
  toolbarOwnerKey?: string;
}

export const ImageViewer: React.FC<ImageViewerProps> = ({
  filePath,
  fileName,
  adapter,
  className,
  i18nBase = 'shared.fileViewer.image',
  toolbarOwnerKey,
}) => {
  const { t, state: i18nState } = useI18n();
  const { registerFormatActions } = useFileViewerWorkbench();
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const currentBlobUrlRef = useRef<string | null>(null);
  const readBlobRef = useRef(adapter.readBlob);
  readBlobRef.current = adapter.readBlob;
  const canReadBlob = Boolean(adapter.readBlob);
  const [imageUrl, setImageUrl] = useState('');
  const [error, setError] = useState<ImageLoadError>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);

  useEffect(() => {
    let isCurrentLoad = true;

    if (currentBlobUrlRef.current) {
      URL.revokeObjectURL(currentBlobUrlRef.current);
      currentBlobUrlRef.current = null;
    }
    setImageUrl('');
    setError(null);

    const loadImage = async () => {
      const readBlob = readBlobRef.current;
      if (!canReadBlob || !readBlob) {
        setError('unavailable');
        setIsLoading(false);
        return;
      }

      setIsLoading(true);

      try {
        const blob = await readBlob(filePath);
        const blobUrl = URL.createObjectURL(blob);
        if (isCurrentLoad) {
          currentBlobUrlRef.current = blobUrl;
          setImageUrl(blobUrl);
          setIsLoading(false);
        } else {
          URL.revokeObjectURL(blobUrl);
        }
      } catch (loadError) {
        logger.error('Failed to load image', { error: loadError });
        if (isCurrentLoad) {
          setError('error');
          setIsLoading(false);
        }
      }
    };

    void loadImage();

    return () => {
      isCurrentLoad = false;
    };
  }, [canReadBlob, filePath]);

  useEffect(() => () => {
    if (currentBlobUrlRef.current) {
      URL.revokeObjectURL(currentBlobUrlRef.current);
      currentBlobUrlRef.current = null;
    }
  }, []);

  const handleImageLoad = () => {
    setIsLoading(false);
    setError(null);
  };

  const handleImageError = (event: React.SyntheticEvent<HTMLImageElement>) => {
    logger.error('Image failed to load', { src: event.currentTarget.src });
    setError('error');
    setIsLoading(false);
  };

  const handleZoomIn = useCallback(() => setZoom((current) => Math.min(current + 0.25, 5)), []);
  const handleZoomOut = useCallback(() => setZoom((current) => Math.max(current - 0.25, 0.25)), []);
  const handleResetZoom = useCallback(() => {
    setZoom(1);
    setRotation(0);
  }, []);
  const handleRotate = useCallback(() => setRotation((current) => (current + 90) % 360), []);

  const handleDownload = useCallback(() => {
    if (!imageUrl) return;
    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [fileName, imageUrl]);

  const toolbarActions = useMemo(() => (
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
  ), [handleDownload, handleResetZoom, handleRotate, handleZoomIn, handleZoomOut, i18nBase, imageUrl, t, zoom]);
  const toolbarActionsRef = useRef(toolbarActions);
  toolbarActionsRef.current = toolbarActions;

  const toolbarRegistrationKey = useMemo(
    () => [
      'image',
      filePath,
      fileName,
      i18nBase,
      i18nState.currentLanguage,
      imageUrl,
      zoom,
      rotation,
    ].join('|'),
    [fileName, filePath, i18nBase, i18nState.currentLanguage, imageUrl, rotation, zoom],
  );
  const resolvedToolbarOwnerKey = toolbarOwnerKey ?? `image:${filePath}`;

  useEffect(() => {
    registerFormatActions(toolbarActionsRef.current, toolbarRegistrationKey, resolvedToolbarOwnerKey);
    return () => registerFormatActions(null, toolbarRegistrationKey, resolvedToolbarOwnerKey);
  }, [registerFormatActions, resolvedToolbarOwnerKey, toolbarRegistrationKey]);

  return (
    <div ref={containerRef} className={cn('flex h-full flex-col bg-muted/10', className)}>
      <div className="flex-1 overflow-auto bg-[radial-gradient(circle_at_1px_1px,_rgb(var(--muted-foreground)_/_0.15)_1px,_transparent_0)] [background-size:20px_20px]">
        {error ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <AlertCircle className="mx-auto mb-4 h-12 w-12 text-destructive opacity-50" />
              <p className="text-sm text-muted-foreground">{t(`${i18nBase}.${error}`)}</p>
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
