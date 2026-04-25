/**
 * 圖片檢視器組件
 * 提供圖片的預覽和互動功能
 */

import React, { useState, useRef, useEffect } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('ImageViewer');
import {
  ZoomIn,
  ZoomOut,
  Download,
  RefreshCw,
  AlertCircle,
  RotateCw,
  Image as ImageIcon
} from 'lucide-react';
import { ApiClient } from '@/shared/api/apiClient';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { FileFocusToolbar } from './FileFocusToolbar';

interface ImageViewerProps {
  filePath: string;
  fileName: string;
  className?: string;
  isFocusMode?: boolean;
  onExitFocusMode?: () => void;
}

export const ImageViewer: React.FC<ImageViewerProps> = ({
  filePath,
  fileName,
  className,
  isFocusMode = false,
  onExitFocusMode,
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const [imageUrl, setImageUrl] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);

  // 保存當前的 blob URL，用於清理
  const currentBlobUrlRef = useRef<string | null>(null);

  logger.debug('Render', { imageUrl, error, isLoading, filePath });

  // 載入圖片
  useEffect(() => {
    if (!workspaceRuntime.runtimeBaseUrl || !filePath) {
      setError('無法載入圖片：缺少必要參數');
      setIsLoading(false);
      return;
    }

    let isMounted = true;

    setIsLoading(true);
    setError('');

    // 釋放舊的 blob URL
    if (currentBlobUrlRef.current) {
      logger.debug('Revoking old blob URL', { url: currentBlobUrlRef.current });
      URL.revokeObjectURL(currentBlobUrlRef.current);
      currentBlobUrlRef.current = null;
    }

    // 使用 ApiClient.getBlob 獲取圖片，自動帶上認證 token
    const loadImage = async () => {
      try {
        const apiClient = new ApiClient({ baseUrl: workspaceRuntime.runtimeBaseUrl });
        const path = `/api/v1/files/content?path=${encodeURIComponent(filePath)}&raw=true`;

        logger.debug('Fetching image via ApiClient', { path });
        const blob = await apiClient.getBlob(path);
        logger.debug('Blob created', { type: blob.type, size: blob.size });

        const blobUrl = URL.createObjectURL(blob);
        logger.debug('Blob URL created', { blobUrl });

        if (isMounted) {
          currentBlobUrlRef.current = blobUrl;
          setImageUrl(blobUrl);
          setIsLoading(false);
        } else {
          // 如果組件已卸載，立即釋放 blob URL
          URL.revokeObjectURL(blobUrl);
        }
      } catch (err) {
        logger.error('Failed to load image', { error: err });
        if (isMounted) {
          setError('無法載入圖片');
          setIsLoading(false);
        }
      }
    };

    loadImage();

    // 清理函數：標記為已卸載
    return () => {
      isMounted = false;
    };
  }, [filePath, workspaceRuntime.runtimeBaseUrl]);

  // 組件卸載時釋放 blob URL
  useEffect(() => {
    return () => {
      if (currentBlobUrlRef.current) {
        logger.debug('Component unmounting, revoking blob URL', { url: currentBlobUrlRef.current });
        URL.revokeObjectURL(currentBlobUrlRef.current);
        currentBlobUrlRef.current = null;
      }
    };
  }, []);

  // 處理圖片載入成功
  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    logger.debug('Image loaded successfully', {
      width: img.naturalWidth,
      height: img.naturalHeight,
      src: img.src
    });
    setImageDimensions({
      width: img.naturalWidth,
      height: img.naturalHeight
    });
    setIsLoading(false);
    setError('');
  };

  // 處理圖片載入失敗
  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    logger.error('Image failed to load', {
      src: e.currentTarget.src,
      error: e
    });
    setError('無法載入圖片');
    setIsLoading(false);
  };

  // 縮放控制
  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.25, 5));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.25, 0.25));
  };

  const handleResetZoom = () => {
    setZoom(1);
    setRotation(0);
  };

  // 旋轉控制
  const handleRotate = () => {
    setRotation(prev => (prev + 90) % 360);
  };

  // 下載圖片
  const handleDownload = () => {
    if (!imageUrl) return;

    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 格式化檔案大小
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const toolbarActions = (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleZoomOut}
        disabled={zoom <= 0.25}
        title={t('workspace.fileManagement.image.zoomOut')}
      >
        <ZoomOut className="h-4 w-4" />
      </Button>

      <span className="text-xs text-muted-foreground min-w-[3rem] text-center">
        {Math.round(zoom * 100)}%
      </span>

      <Button
        variant="ghost"
        size="sm"
        onClick={handleZoomIn}
        disabled={zoom >= 5}
        title={t('workspace.fileManagement.image.zoomIn')}
      >
        <ZoomIn className="h-4 w-4" />
      </Button>

      <div className="w-px h-4 bg-border mx-1" />

      <Button
        variant="ghost"
        size="sm"
        onClick={handleRotate}
        title={t('workspace.fileManagement.image.rotate')}
      >
        <RotateCw className="h-4 w-4" />
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={handleResetZoom}
        title={t('workspace.fileManagement.image.reset')}
      >
        <RefreshCw className="h-4 w-4" />
      </Button>

      <div className="w-px h-4 bg-border mx-1" />

      <Button
        variant="ghost"
        size="sm"
        onClick={handleDownload}
        title={t('workspace.fileManagement.image.download')}
      >
        <Download className="h-4 w-4" />
      </Button>
    </>
  );

  return (
    <div 
      ref={containerRef}
      className={cn(
        "h-full flex flex-col bg-muted/10",
        className
      )}
    >
      {/* 工具列 */}
      {isFocusMode && onExitFocusMode ? (
        <FileFocusToolbar
          icon={<ImageIcon className="h-4 w-4" />}
          title={fileName}
          subtitle={filePath}
          metadata={imageDimensions ? <span>{imageDimensions.width} × {imageDimensions.height}</span> : null}
          actions={toolbarActions}
          exitLabel={t('workspace.fileManagement.focus.exit')}
          onExit={onExitFocusMode}
        />
      ) : (
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-2">
          <ImageIcon className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">{fileName}</span>
          {imageDimensions && (
            <span className="text-xs text-muted-foreground">
              {imageDimensions.width} × {imageDimensions.height}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {toolbarActions}
        </div>
      </div>
      )}

      {/* 圖片顯示區域 */}
      <div className="flex-1 overflow-auto bg-[radial-gradient(circle_at_1px_1px,_rgb(var(--muted-foreground)_/_0.15)_1px,_transparent_0)] [background-size:20px_20px]">
        {error ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 text-destructive opacity-50" />
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <RefreshCw className="w-12 h-12 mx-auto mb-4 opacity-50 animate-spin" />
              <p className="text-sm text-muted-foreground">
                {t('workspace.fileManagement.image.loading')}
              </p>
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center p-4">
            <img
              ref={imageRef}
              src={imageUrl}
              alt={fileName}
              onLoad={handleImageLoad}
              onError={handleImageError}
              className="max-w-full max-h-full object-contain transition-transform duration-200"
              style={{
                transform: `scale(${zoom}) rotate(${rotation}deg)`,
                transformOrigin: 'center center'
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};
