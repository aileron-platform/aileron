import React from 'react';
import { type TemplateAgent } from '@/shared/types/templates';
import { AgentViewer } from '@/features/template-management/components/metadata-viewers/AgentViewer';
import { adaptTemplateAgents } from '@/features/template-management/components/metadata-viewers/adapters';

interface AgentsTabContentProps {
  agents: TemplateAgent[];
}

export const AgentsTabContent: React.FC<AgentsTabContentProps> = ({ agents }) => {
  // 適配數據
  const adaptedAgents = React.useMemo(() => adaptTemplateAgents(agents), [agents]);

  return (
    <AgentViewer
      items={adaptedAgents}
      isEditable={false}
    />
  );
};

export default AgentsTabContent;