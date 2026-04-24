import React, { useMemo, useState } from 'react';
import { Download, Plus, Server } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { MCPServerDialog } from '@/shared/components/dialogs';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { SettingsWorkflowActionButton, SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import type { McpServerFormValue } from '@/features/template-management/features/template-editor/formTypes';
import TemplateMcpServerCard from '@/features/template-management/components/TemplateMcpServerCard';
import { useTemplateApi } from '@/features/template-management/features/template-editor/hooks/useTemplateApi';

interface TemplateMcpSettingsWorkflowProps {
  templateId?: string;
  servers: McpServerFormValue[];
  onServersChange?: (servers: McpServerFormValue[]) => void;
  editable?: boolean;
  onSaveSuccess?: () => void;
}

export const TemplateMcpSettingsWorkflow: React.FC<TemplateMcpSettingsWorkflowProps> = ({
  templateId,
  servers,
  onServersChange,
  editable = false,
  onSaveSuccess,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { saveMcpConfig } = useTemplateApi({ templateId });
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingServer, setEditingServer] = useState<McpServerFormValue | undefined>();
  const handlePersist = async (nextServers: McpServerFormValue[]) => {
    if (templateId) {
      const saved = await saveMcpConfig(nextServers);
      if (!saved) return;
    }
    onServersChange?.(nextServers);
    onSaveSuccess?.();
  };

  const handleAdd = () => {
    if (!editable) return;
    setEditingServer(undefined);
    setIsDialogOpen(true);
  };

  const handleEdit = (server: McpServerFormValue) => {
    if (!editable) return;
    setEditingServer(server);
    setIsDialogOpen(true);
  };

  const handleDelete = async (serverId: string) => {
    if (!editable) return;
    const nextServers = servers.filter((server) => server.localId !== serverId);
    await handlePersist(nextServers);
  };

  const handleSave = async (serverData: McpServerFormValue) => {
    const nextServers = editingServer
      ? servers.map((server) => (server.localId === editingServer.localId ? serverData : server))
      : [...servers, serverData];
    await handlePersist(nextServers);
  };

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(servers, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement('a');
    anchor.href = url;
    anchor.download = t('template.detail.mcp.downloadFileName');
    window.document.body.appendChild(anchor);
    anchor.click();
    window.document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
    toast({
      title: t('template.detail.mcp.toasts.downloadSuccess.title'),
      description: t('template.detail.mcp.toasts.downloadSuccess.description'),
    });
  };

  const headerActions = useMemo(() => (
    <div className="flex items-center gap-2">
      {!editable ? (
        <SettingsWorkflowActionButton variant="outline" onClick={handleDownload}>
          <Download className="mr-1 h-3.5 w-3.5" />
          {t('template.detail.mcp.actions.download')}
        </SettingsWorkflowActionButton>
      ) : null}
      {editable ? (
        <SettingsWorkflowActionButton onClick={handleAdd}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          {t('template.editor.mcp.actions.add')}
        </SettingsWorkflowActionButton>
      ) : null}
    </div>
  ), [editable, t]);

  return (
    <>
      <SettingsWorkflowShell
        title={editable ? t('template.editor.tabs.mcp') : t('template.detail.mcp.header.title')}
        icon={Server}
        headerActions={headerActions}
        summary={<SettingsWorkflowCountBadge label={t('template.detail.mcp.badge', { count: servers.length })} />}
        singleHeader
        hasItems={servers.length > 0}
        emptyIcon={<Server className="h-6 w-6 text-muted-foreground" />}
        emptyTitle={editable ? t('template.editor.mcp.empty.title') : t('template.detail.mcp.empty.title')}
        emptyDescription={editable ? t('template.editor.mcp.empty.description') : t('template.detail.mcp.empty.description')}
        emptyActions={editable ? (
          <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            {t('template.editor.mcp.actions.add')}
          </Button>
        ) : undefined}
        contentClassName="space-y-4 p-4"
      >
        {servers.map((server) => (
          <TemplateMcpServerCard
            key={server.localId}
            server={server}
            showActions={editable}
            onEdit={editable ? handleEdit : undefined}
            onDelete={editable ? handleDelete : undefined}
          />
        ))}
      </SettingsWorkflowShell>

      {editable ? (
        <MCPServerDialog
          variant="template"
          open={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          onSave={handleSave}
          initialData={editingServer}
        />
      ) : null}
    </>
  );
};

export default TemplateMcpSettingsWorkflow;
