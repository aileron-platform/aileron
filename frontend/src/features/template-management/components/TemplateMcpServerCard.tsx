import React from 'react';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import type { McpServerFormValue } from '@/features/template-management/features/template-editor/formTypes';
import McpServerCard from '@/features/template-management/components/McpServerCard';

interface TemplateMcpServerCardProps {
  server: McpServerFormValue;
  showActions?: boolean;
  onEdit?: (server: McpServerFormValue) => void;
  onDelete?: (serverId: string) => void;
}

const TemplateMcpServerCard: React.FC<TemplateMcpServerCardProps> = ({
  server,
  showActions = false,
  onEdit,
  onDelete,
}) => {
  const { toast } = useToast();
  const { t } = useI18n();

  const handleCopyConfig = (serverData: McpServerFormValue) => {
    const serverType = serverData.type ?? serverData.transport ?? 'stdio';
    const config: Record<string, unknown> = {
      [serverData.name]: {
        type: serverType,
      },
    };

    if (serverData.url) {
      (config[serverData.name] as Record<string, unknown>).url = serverData.url;
    }
    if (serverData.command) {
      (config[serverData.name] as Record<string, unknown>).command = serverData.command;
    }

    const argsFromText = serverData.argsText
      ?.split('\n')
      .map((item) => item.trim())
      .filter(Boolean);
    const args = serverData.args && serverData.args.length > 0 ? serverData.args : argsFromText;
    if (args && args.length > 0) {
      (config[serverData.name] as Record<string, unknown>).args = args;
    }

    const envFromText = serverData.envText
      ?.split('\n')
      .map((item) => item.trim())
      .filter((line) => line.includes('='))
      .map((line) => {
        const [key, ...rest] = line.split('=');
        return [key.trim(), rest.join('=').trim()];
      });
    const envEntries = serverData.env ? Object.entries(serverData.env) : envFromText;
    if (envEntries && envEntries.length > 0) {
      (config[serverData.name] as Record<string, unknown>).env = Object.fromEntries(envEntries);
    }

    const headersFromText = serverData.headersText
      ?.split('\n')
      .map((item) => item.trim())
      .filter((line) => line.includes(':'))
      .map((line) => {
        const [key, ...rest] = line.split(':');
        return [key.trim(), rest.join(':').trim()];
      });
    if (headersFromText && headersFromText.length > 0) {
      (config[serverData.name] as Record<string, unknown>).headers = Object.fromEntries(headersFromText);
    }

    navigator.clipboard.writeText(JSON.stringify(config, null, 2));
    toast({
      title: t('template.detail.mcp.toasts.copySuccess.title'),
      description: t('template.detail.mcp.toasts.copySuccess.description', { name: serverData.name }),
    });
  };

  return (
    <McpServerCard<McpServerFormValue>
      server={server}
      mode="edit"
      onCopyConfig={handleCopyConfig}
      onEdit={showActions ? onEdit : undefined}
      onDelete={showActions ? onDelete : undefined}
    />
  );
};

export default TemplateMcpServerCard;
