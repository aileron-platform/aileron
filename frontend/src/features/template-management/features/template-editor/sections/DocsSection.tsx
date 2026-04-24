import React from 'react';
import TemplateAgentsMdWorkflow from '@/features/template-management/components/TemplateAgentsMdWorkflow';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';

interface DocsSectionProps {
  templateId?: string;
  documentation: string;
  agentsMd: string;
  onChange: (next: { documentation?: string; agentsMd?: string }) => void;
}

const DocsSection: React.FC<DocsSectionProps> = ({
  templateId,
  documentation: _documentation,
  agentsMd: initialAgentsMd,
  onChange
}) => {
  const { reloadFromSource } = useTemplateManagementContext();

  return (
    <TemplateAgentsMdWorkflow
      templateId={templateId}
      initialContent={initialAgentsMd}
      onContentChange={(agentsMd) => onChange({ agentsMd })}
      onSaveSuccess={reloadFromSource}
    />
  );
};

export default DocsSection;
