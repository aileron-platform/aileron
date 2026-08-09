import React from 'react';
import { EnvironmentVariables } from '@/shared/components/settings-workflow';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserSettingsOpenCode } from '@/shared/types/user';
import { SettingsModelSelectionSection } from './SettingsModelSelectionSection';

interface SettingsOpenCodeTabProps {
  opencodeSettings: UserSettingsOpenCode;
  onOpenCodeSettingsChange: (settings: UserSettingsOpenCode) => void;
}

export const SettingsOpenCodeTab: React.FC<SettingsOpenCodeTabProps> = ({
  opencodeSettings,
  onOpenCodeSettingsChange,
}) => {
  const { t } = useI18n();

  return (
    <div className="space-y-6 p-1">
      <Card>
        <CardHeader>
          <CardTitle>{t('pages.settings.tabs.opencode')}</CardTitle>
          <CardDescription>{t('pages.settings.sections.opencode.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <SettingsModelSelectionSection
            value={opencodeSettings.modelSelection}
            onChange={(modelSelection) => onOpenCodeSettingsChange({ ...opencodeSettings, modelSelection })}
            i18nPrefix="pages.settings.sections.opencode.models"
          />
          <EnvironmentVariables
            value={opencodeSettings.environmentVariables || []}
            onChange={(environmentVariables) =>
              onOpenCodeSettingsChange({ ...opencodeSettings, environmentVariables })
            }
            title={t('pages.settings.sections.opencode.environmentVariables.title')}
            description={t('pages.settings.sections.opencode.environmentVariables.description')}
          />
        </CardContent>
      </Card>
    </div>
  );
};
