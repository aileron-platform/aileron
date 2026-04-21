import React from 'react';
import TemplateClaudeMdWorkflow from '@/features/template-management/components/TemplateClaudeMdWorkflow';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';

interface DocsSectionProps {
  templateId?: string;
  documentation: string;
  claudeMd: string;
  onChange: (next: { documentation?: string; claudeMd?: string }) => void;
}

const DocsSection: React.FC<DocsSectionProps> = ({
  templateId,
  documentation: _documentation,
  claudeMd: initialClaudeMd,
  onChange
}) => {
  const { reloadFromSource } = useTemplateManagementContext();

  return (
    <TemplateClaudeMdWorkflow
      templateId={templateId}
      initialContent={initialClaudeMd}
      onContentChange={(claudeMd) => onChange({ claudeMd })}
      onSaveSuccess={reloadFromSource}
    />
  );
};

export default DocsSection;
