import TemplateMcpSettingsWorkflow from '@/features/template-management/components/TemplateMcpSettingsWorkflow';
import type { McpServerFormValue } from '../formTypes';
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
  const { templateId } = useParams<{ templateId: string }>();
  const { reloadFromSource } = useTemplateManagementContext();

  return (
    <TemplateMcpSettingsWorkflow
      templateId={templateId}
      servers={servers}
      onServersChange={onServersChange}
      editable
      onSaveSuccess={reloadFromSource}
    />
  );
};

export default McpServersSection;
