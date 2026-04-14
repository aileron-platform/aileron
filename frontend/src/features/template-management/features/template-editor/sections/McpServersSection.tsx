import { useState } from 'react';
import { Plus, Server } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import McpServerCard from '../components/McpServerCard';
import { MCPServerDialog } from '@/shared/components/dialogs';
import type { McpServerFormValue } from '../formTypes';
import { useI18n } from '@/shared/hooks/useI18n';
import { useTemplateApi } from '../hooks/useTemplateApi';
import { useParams } from 'react-router-dom';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';

interface McpServersSectionProps {
  servers: McpServerFormValue[];
  onServersChange: (servers: McpServerFormValue[]) => void;
}

const McpServersSection: React.FC<McpServersSectionProps> = ({
  servers,
  onServersChange
}) => {
  const { t } = useI18n();
  const { templateId } = useParams<{ templateId: string }>();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingServer, setEditingServer] = useState<McpServerFormValue | undefined>();
  const { reloadFromSource } = useTemplateManagementContext();
  const { isSaving, saveMcpConfig } = useTemplateApi({
    templateId,
    onSuccess: reloadFromSource // 保存成功後重新載入模板列表
  });

  const handleAdd = () => {
    setEditingServer(undefined);
    setIsDialogOpen(true);
  };

  const handleEdit = (server: McpServerFormValue) => {
    setEditingServer(server);
    setIsDialogOpen(true);
  };

  const handleDelete = async (serverId: string) => {
    const updatedServers = servers.filter(server => server.localId !== serverId);

    // 更新本地狀態
    onServersChange(updatedServers);

    // 立即儲存到後端
    await saveMcpConfig(updatedServers);
  };

  const handleSave = async (serverData: McpServerFormValue) => {
    let updatedServers: McpServerFormValue[];

    if (editingServer) {
      // 編輯現有伺服器
      updatedServers = servers.map(server =>
        server.localId === editingServer.localId ? serverData : server
      );
    } else {
      // 新增伺服器
      updatedServers = [...servers, serverData];
    }

    // 更新本地狀態
    onServersChange(updatedServers);

    // 立即儲存到後端
    await saveMcpConfig(updatedServers);
  };

  return (
    <>
      {servers.length === 0 ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
          <Server className="h-10 w-10 text-muted-foreground" />
          <div className="space-y-1">
            <p className="text-base font-medium text-muted-foreground">
              {t('template.editor.mcp.empty.title')}
            </p>
            <p className="text-sm text-muted-foreground">
              {t('template.editor.mcp.empty.description')}
            </p>
          </div>
          <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>
            <Plus className="mr-1 h-3.5 w-3.5" /> {t('template.editor.mcp.actions.add')}
          </Button>
        </div>
      ) : (
        <div className="space-y-4 p-6">
          {/* 右上角新增按鈕 */}
          <div className="flex justify-end mb-4">
            <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>
              <Plus className="mr-1 h-3.5 w-3.5" /> {t('template.editor.mcp.actions.add')}
            </Button>
          </div>
          {servers.map(server => (
            <McpServerCard
              key={server.localId}
              server={server}
              showActions={true}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <MCPServerDialog
        variant="template"
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onSave={handleSave}
        initialData={editingServer}
      />
    </>
  );
};

export default McpServersSection;

