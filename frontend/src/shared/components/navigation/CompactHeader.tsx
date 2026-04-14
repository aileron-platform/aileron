/**
 * CompactHeader - 精簡版 Header (全螢幕模式)
 * 在全螢幕模式下顯示的精簡導航列
 */

import React from 'react';
import { Button } from '../ui/button';
import { Minimize, User, Folder, Clock, FileText } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/shared/components/ui/avatar';
import { ModuleType } from '../../../app/providers/NavigationProvider';
import { useI18n } from '@/app/providers/I18nProvider';
import { cn } from '@/shared/utils/cn';

interface CompactHeaderProps {
  currentModule: ModuleType;
  workspaceName?: string | null;
  onExitFullscreen: () => void;
}

export const CompactHeader: React.FC<CompactHeaderProps> = ({
  currentModule,
  workspaceName,
  onExitFullscreen,
}) => {
  const { t } = useI18n();

  const getModuleLabel = (module: ModuleType): string => {
    const moduleLabels: Partial<Record<ModuleType, string>> = {
      workspace: t('navigation.compactHeader.modules.workspace'),
      automation: t('navigation.compactHeader.modules.automation'),
      template: t('navigation.compactHeader.modules.template'),
    };
    return moduleLabels[module] || module;
  };

  const getModuleIcon = (module: ModuleType) => {
    const iconClass = "h-3 w-3";
    switch (module) {
      case 'workspace':
        return <Folder className={iconClass} />;
      case 'automation':
        return <Clock className={iconClass} />;
      case 'template':
        return <FileText className={iconClass} />;
      default:
        return null;
    }
  };

  return (
    <header className="h-10 border-b border-border/50 bg-gradient-to-r from-card to-card/95 backdrop-blur-md px-4 flex items-center justify-between shadow-sm">
      {/* 左側：Logo + 專案標題 */}
      <div className="flex items-center gap-2">
        <img src="/logo.png" alt="Aileron" className="h-4 w-4" />
        <span className="text-sm font-semibold bg-gradient-to-r from-primary to-gray-700 bg-clip-text text-transparent">
          {t('navigation.brand.title')}
        </span>
      </div>

      {/* 中間：功能區標籤 + 工作區名稱 */}
      <div className="flex items-center gap-2">
        <span className="px-2 py-0.5 text-xs font-medium rounded-md bg-primary/10 text-primary flex items-center gap-1">
          {getModuleIcon(currentModule)}
          {getModuleLabel(currentModule)}
        </span>

        {currentModule === 'workspace' && workspaceName && (
          <>
            <span className="text-xs text-muted-foreground">
              {t('navigation.compactHeader.separator')}
            </span>
            <span
              className={cn(
                "text-xs text-foreground font-medium truncate max-w-[200px]"
              )}
              title={workspaceName}
            >
              {workspaceName}
            </span>
          </>
        )}
      </div>

      {/* 右側：退出全螢幕按鈕 + User */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 hover:bg-muted text-muted-foreground hover:text-foreground"
          onClick={onExitFullscreen}
          title={t('navigation.compactHeader.exitFullscreen')}
        >
          <Minimize className="h-3.5 w-3.5" />
        </Button>

        <Avatar className="h-6 w-6">
          <AvatarFallback className="bg-gradient-to-br from-primary to-primary/80 text-primary-foreground text-xs">
            <User className="h-3 w-3" />
          </AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
};

export default CompactHeader;
