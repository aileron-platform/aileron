import React, { useRef } from 'react';
import { Button } from '@/shared/components/ui/button';
import { useToast } from '@/shared/components/ui/use-toast';
import { Download, Server } from 'lucide-react';
import McpServerCard from './McpServerCard';
import type { ClaudeMcpServer } from '@/features/workspace/features/claude-code/types';
import type { TemplateMcpServer } from '@/shared/types/templates';
import { useI18n } from '@/shared/hooks/useI18n';

interface McpTabContentProps {
  mcpServers?: TemplateMcpServer[];
}

// 轉換 TemplateMcpServer 到 ClaudeMcpServer (移除 scope)
const convertTemplateMcpToClaudeMcp = (templateMcpServers: TemplateMcpServer[]): ClaudeMcpServer[] => {
  return templateMcpServers.map(server => ({
    id: server.id,
    name: server.name,
    command: server.command,
    args: server.args,
    url: server.url,
    env: server.env,
    headers: server.headers,
    transport: server.type as 'stdio' | 'sse' | 'http'
  })) as ClaudeMcpServer[];
};

export const McpTabContent: React.FC<McpTabContentProps> = ({ mcpServers = [] }) => {
  const claudeMcpServers = convertTemplateMcpToClaudeMcp(mcpServers);
  const { toast } = useToast();
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement>(null);

  const handleCopyConfig = (server: ClaudeMcpServer) => {
    const serverConfig = {
      [server.name]: {
        transport: server.transport ?? 'stdio',
        ...(server.url ? { url: server.url } : {}),
        ...(server.command ? { command: server.command } : {}),
        ...(server.args && server.args.length > 0 ? { args: server.args } : {}),
        ...(server.env ? { env: server.env } : {}),
      },
    };
    const configText = JSON.stringify(serverConfig, null, 2);
    navigator.clipboard.writeText(configText);
    toast({
      title: t('template.detail.mcp.toasts.copySuccess.title'),
      description: t('template.detail.mcp.toasts.copySuccess.description', { name: server.name }),
    });
  };

  if (claudeMcpServers.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
          <Server className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-medium text-foreground mb-2">
          {t('template.detail.mcp.empty.title')}
        </h3>
        <p className="text-muted-foreground">{t('template.detail.mcp.empty.description')}</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-border bg-background flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Server className="h-5 w-5 text-primary" />
            <h3 className="font-semibold text-foreground">{t('template.detail.mcp.header.title')}</h3>
          </div>
          <p className="text-sm text-muted-foreground">{t('template.detail.mcp.header.description')}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            aria-label={t('template.detail.mcp.actions.download')}
            title={t('template.detail.mcp.actions.download')}
          >
            <Download className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <div className="space-y-4">
          {claudeMcpServers.map((server) => (
            <McpServerCard key={server.id} server={server} onCopyConfig={handleCopyConfig} />
          ))}
        </div>
      </div>
    </div>
  );
};
