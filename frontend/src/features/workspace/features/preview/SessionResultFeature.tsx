/**
 * SessionResultFeature - 對話結果預覽功能
 *
 * 提供 Markdown 格式的對話結果預覽
 */

import React, { useState } from 'react';
import { Maximize2, Minimize2, FileText } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { UsageStats } from './UsageStats';

export const SessionResultFeature: React.FC = () => {
  const { t } = useI18n();
  const { preview } = useWorkspace();
  const [isFullscreen, setIsFullscreen] = useState(false);

  const previewMarkdown = preview.markdownContent;
  const rawContent = preview.rawContent;
  const hasContent = previewMarkdown.trim().length > 0;

  return (
    <div
      className={cn(
        'flex h-full flex-col bg-background',
        isFullscreen && 'fixed inset-0 z-50 bg-background'
      )}
    >
      <FeatureHeader
        title={t('workspace.preview.sessionResult.title')}
        icon={FileText}
        actions={
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setIsFullscreen((prev) => !prev)}
            title={
              isFullscreen
                ? t('workspace.preview.header.actions.fullscreen.exit')
                : t('workspace.preview.header.actions.fullscreen.enter')
            }
          >
            {isFullscreen ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </Button>
        }
      />

      <div className="flex-1 overflow-hidden">
        {hasContent ? (
          <ScrollArea className="h-full w-full">
            <div className="overflow-x-auto">
              {/* 使用統計信息 */}
              <UsageStats rawContent={rawContent} />
              {/* 預覽內容 */}
              <div className="p-4">
                {preview.renderMarkdown(previewMarkdown)}
              </div>
            </div>
          </ScrollArea>
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <div className="text-sm">
                {t('workspace.preview.sessionResult.emptyMessage')}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SessionResultFeature;

