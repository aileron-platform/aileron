/**
 * ComingSoonPlaceholder - placeholder for unsupported agent capabilities.
 */

import React from 'react';
import { Construction } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { getAgentToolConfig } from '../utils';
import type { AgentToolType } from '../types';

export interface ComingSoonPlaceholderProps {
  feature: string;
  cliType: AgentToolType;
}

const ComingSoonPlaceholder: React.FC<ComingSoonPlaceholderProps> = ({ feature, cliType }) => {
  const { t } = useI18n();
  const config = getAgentToolConfig(cliType);
  const toolName = t(config.navigationLabelKey, { defaultValue: cliType });

  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={feature}
        icon={Construction}
      />
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
        <Construction className="h-12 w-12 text-muted-foreground/50" />
        <div className="space-y-2">
          <h3 className="text-lg font-medium text-foreground">
            {t('workspace.agentSettings.common.comingSoon.title', {
              defaultValue: 'Coming soon',
            })}
          </h3>
          <p className="text-sm text-muted-foreground max-w-md">
            {t('workspace.agentSettings.common.comingSoon.description', {
              defaultValue: `${feature} will be available for ${toolName} soon.`,
              feature,
              toolName,
            })}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ComingSoonPlaceholder;
