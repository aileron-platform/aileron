/**
 * ComingSoonPlaceholder - placeholder for unsupported agent capabilities.
 */

import React from 'react';
import { Construction } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { getAgentToolConfig } from '../model/agentSettingsModel';
import type { AgentSettingsToolId } from '../model/capabilities';
import { getAgentSubViewLabelKey } from '../agentSubViewLabelModel';

export interface ComingSoonPlaceholderProps {
  feature: string;
  toolId: AgentSettingsToolId;
}

const ComingSoonPlaceholder: React.FC<ComingSoonPlaceholderProps> = ({ feature, toolId }) => {
  const { t } = useI18n();
  const config = getAgentToolConfig(toolId);
  const toolName = t(config.navigationLabelKey);
  const featureLabel = t(getAgentSubViewLabelKey(feature));

  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={featureLabel}
        icon={Construction}
      />
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
        <Construction className="h-12 w-12 text-muted-foreground/50" />
        <div className="space-y-2">
          <h3 className="text-lg font-medium text-foreground">
            {t('workspace.agentSettings.common.comingSoon.title')}
          </h3>
          <p className="text-sm text-muted-foreground max-w-md">
            {t('workspace.agentSettings.common.comingSoon.description', {
              feature: featureLabel,
              toolName,
            })}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ComingSoonPlaceholder;
