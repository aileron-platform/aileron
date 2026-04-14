import React from 'react';
import { type TemplateSubAgent } from '@/shared/types/templates';
import { SubAgentViewer } from '@/shared/components/template/SubAgentViewer';
import { adaptTemplateSubAgents } from '@/shared/components/template/adapters';

interface SubAgentsTabContentProps {
  agents: TemplateSubAgent[];
}

export const SubAgentsTabContent: React.FC<SubAgentsTabContentProps> = ({ agents }) => {
  // 適配數據
  const adaptedAgents = React.useMemo(() => adaptTemplateSubAgents(agents), [agents]);

  return (
    <SubAgentViewer
      items={adaptedAgents}
      isEditable={false}
    />
  );
};

export default SubAgentsTabContent;