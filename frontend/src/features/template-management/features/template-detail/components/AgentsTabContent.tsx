import React from 'react';
import { type TemplateAgent } from '@/shared/types/templates';
import { AgentViewer } from '@/shared/components/template/AgentViewer';
import { adaptTemplateAgents } from '@/shared/components/template/adapters';

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