import React from 'react';
import TemplateAgentsMdWorkflow from '@/features/template-management/components/TemplateAgentsMdWorkflow';

interface AgentsMdTabContentProps {
  templateId?: string;
  agentsMd?: string | null;
  onEdit?: () => void;
}

export const AgentsMdTabContent: React.FC<AgentsMdTabContentProps> = ({
  templateId,
  agentsMd: initialAgentsMd,
  onEdit: _onEdit,
}) => {
  return (
    <TemplateAgentsMdWorkflow
      templateId={templateId}
      initialContent={initialAgentsMd}
    />
  );
};

export default AgentsMdTabContent;
