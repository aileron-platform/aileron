import React from 'react';
import TemplateClaudeMdWorkflow from '@/features/template-management/components/TemplateClaudeMdWorkflow';

interface ClaudeMdTabContentProps {
  templateId?: string;
  claudeMd?: string | null;
  onEdit?: () => void;
}

export const ClaudeMdTabContent: React.FC<ClaudeMdTabContentProps> = ({
  templateId,
  claudeMd: initialClaudeMd,
  onEdit: _onEdit,
}) => {
  return (
    <TemplateClaudeMdWorkflow
      templateId={templateId}
      initialContent={initialClaudeMd}
    />
  );
};

export default ClaudeMdTabContent;
