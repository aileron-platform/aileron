import React from 'react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { useToast } from '@/shared/components/ui/use-toast';
import { Download, Zap } from 'lucide-react';
import HookCard from '@/features/template-management/components/HookCard';
import type { ClaudeHook } from '@/features/workspace/features/claude-code/types';
import { type TemplateHook } from '@/shared/types/templates';
import { useI18n } from '@/shared/hooks/useI18n';

interface HooksTabContentProps {
  hooks?: TemplateHook[];
}

// 轉換 TemplateHook 到 ClaudeHook (移除 scope)
const convertTemplateHooksToClaudeHooks = (templateHooks: TemplateHook[]): ClaudeHook[] => {
  // 按事件分組
  const hooksByEvent = templateHooks.reduce((acc, hook) => {
    if (!acc[hook.event]) {
      acc[hook.event] = [];
    }
    acc[hook.event].push(hook);
    return acc;
  }, {} as Record<string, TemplateHook[]>);

  // 轉換為 ClaudeHook 格式，移除 scope
  return Object.entries(hooksByEvent).map(([event, eventHooks]) => ({
    id: `event-${event}`,
    eventName: event,
    matchers: eventHooks.map(hook => ({
      matcher: hook.matcher || '*',
      hooks: [{
        type: 'command' as const,
        command: hook.command || hook.script || '',
        timeout: hook.timeout || 30
      }]
    }))
  })) as ClaudeHook[];
};

export const HooksTabContent: React.FC<HooksTabContentProps> = ({ hooks = [] }) => {
  const claudeHooks = convertTemplateHooksToClaudeHooks(hooks);
  const { toast } = useToast();
  const { t } = useI18n();

  const handleDownloadConfig = () => {
    const config = JSON.stringify(claudeHooks, null, 2);
    const blob = new Blob([config], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'hooks-config.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast({
      title: t('template.detail.hooks.toasts.downloadSuccess.title'),
      description: t('template.detail.hooks.toasts.downloadSuccess.description'),
    });
  };

  if (claudeHooks.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-border bg-background flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              <h3 className="font-semibold text-foreground">{t('template.detail.hooks.header.title')}</h3>
            </div>
            <p className="text-sm text-muted-foreground">{t('template.detail.hooks.header.description')}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {t('template.detail.hooks.badge', { count: claudeHooks.length })}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadConfig}
              aria-label={t('template.detail.hooks.actions.download')}
              title={t('template.detail.hooks.actions.download')}
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
              <Zap className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-medium text-foreground mb-2">
              {t('template.detail.hooks.empty.title')}
            </h3>
            <p className="text-muted-foreground">{t('template.detail.hooks.empty.description')}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-border bg-background flex-shrink-0">
        <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
            <h3 className="font-semibold text-foreground">{t('template.detail.hooks.header.title')}</h3>
            </div>
          <p className="text-sm text-muted-foreground">{t('template.detail.hooks.header.description')}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {t('template.detail.hooks.badge', { count: claudeHooks.length })}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadConfig}
            aria-label={t('template.detail.hooks.actions.download')}
            title={t('template.detail.hooks.actions.download')}
          >
            <Download className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <div className="space-y-4">
          {claudeHooks.map((hook, index) => (
            <HookCard key={hook.id || index} hook={hook} mode="view" />
          ))}
        </div>
      </div>
    </div>
  );
};

export default HooksTabContent;

