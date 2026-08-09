import React from 'react';
import { Bot } from 'lucide-react';
import {
  EnvironmentVariables,
  SettingsFlatRow,
  SettingsSectionDivider,
} from '@/shared/components/settings-workflow';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserSettingsCodex } from '@/shared/types/user';
import { SettingsModelSelectionSection } from './SettingsModelSelectionSection';

interface SettingsCodexTabProps {
  codexSettings: UserSettingsCodex;
  isCodexAuthLoading: boolean;
  onCodexSettingsChange: (settings: UserSettingsCodex) => void;
  onSignIn: () => void;
  onRefreshStatus: () => void;
  onLogout: () => void;
  onCancelLogin: () => void;
}

export const SettingsCodexTab: React.FC<SettingsCodexTabProps> = ({
  codexSettings,
  isCodexAuthLoading,
  onCodexSettingsChange,
  onSignIn,
  onRefreshStatus,
  onLogout,
  onCancelLogin,
}) => {
  const { t } = useI18n();
  const authMethod = codexSettings.authMethod || 'subscription';

  return (
    <div className="space-y-6 p-1">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            {t('pages.settings.tabs.codex')}
          </CardTitle>
          <CardDescription>{t('pages.settings.sections.codex.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <SettingsModelSelectionSection
            value={codexSettings.modelSelection}
            onChange={(modelSelection) => onCodexSettingsChange({ ...codexSettings, modelSelection })}
            i18nPrefix="pages.settings.sections.codex.models"
          />

          <SettingsFlatRow label={t('pages.settings.sections.codex.authMethod.label')}>
            <Select
              value={authMethod}
              onValueChange={(value) =>
                onCodexSettingsChange({ ...codexSettings, authMethod: value as UserSettingsCodex['authMethod'] })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder={t('pages.settings.sections.codex.authMethod.description')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="subscription">{t('pages.settings.sections.codex.authMethod.options.subscription')}</SelectItem>
                <SelectItem value="apikey">{t('pages.settings.sections.codex.authMethod.options.apikey')}</SelectItem>
              </SelectContent>
            </Select>
          </SettingsFlatRow>

          <SettingsSectionDivider />

          {authMethod === 'subscription' && (
            <SettingsFlatRow label={t('pages.settings.sections.codex.login.title')}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                    <span className="h-2 w-2 rounded-full bg-primary" />
                    {t(`pages.settings.sections.codex.login.status.${codexSettings.loginStatus}`)}
                  </span>
                  {codexSettings.account?.email ? (
                    <p className="text-sm text-muted-foreground">
                      {t('pages.settings.sections.codex.login.account')}: <span className="font-mono text-foreground">{codexSettings.account.email}</span>
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {t('pages.settings.sections.codex.login.notConnectedDescription')}
                    </p>
                  )}
                  {codexSettings.authFlow?.verificationUrl && (
                    <div className="space-y-1 text-sm text-muted-foreground">
                      <p>
                        {t('pages.settings.sections.codex.login.deviceCode', {
                          code: codexSettings.authFlow.userCode || '',
                        })}
                      </p>
                      <a
                        href={codexSettings.authFlow.verificationUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex font-medium text-primary underline-offset-4 hover:underline"
                      >
                        {t('pages.settings.sections.codex.login.openVerificationLink')}
                      </a>
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {codexSettings.loginStatus === 'pending' ? (
                    <>
                      <Button variant="outline" onClick={onRefreshStatus} disabled={isCodexAuthLoading}>
                        {t('pages.settings.sections.codex.login.refreshButton')}
                      </Button>
                      <Button variant="outline" onClick={onCancelLogin} disabled={isCodexAuthLoading}>
                        {t('pages.settings.sections.codex.login.cancelButton')}
                      </Button>
                    </>
                  ) : codexSettings.loginStatus === 'connected' ? (
                    <Button variant="outline" onClick={onLogout} disabled={isCodexAuthLoading}>
                      {t('pages.settings.sections.codex.login.disconnectButton')}
                    </Button>
                  ) : (
                    <Button variant="outline" onClick={onSignIn} disabled={isCodexAuthLoading}>
                      {t('pages.settings.sections.codex.login.connectButton')}
                    </Button>
                  )}
                </div>
              </div>
            </SettingsFlatRow>
          )}

          <SettingsFlatRow
            label={t('pages.settings.sections.codex.model.label')}
            description={t('pages.settings.sections.codex.model.help')}
          >
            <Input
              placeholder={t('pages.settings.sections.codex.model.placeholder')}
              value={codexSettings.model || ''}
              onChange={(event) =>
                onCodexSettingsChange({ ...codexSettings, model: event.target.value })
              }
              className="font-mono"
            />
          </SettingsFlatRow>

          {authMethod === 'apikey' && (
            <EnvironmentVariables
              value={codexSettings.environmentVariables || []}
              onChange={(variables) =>
                onCodexSettingsChange({ ...codexSettings, environmentVariables: variables })
              }
              title={t('pages.settings.sections.codex.environmentVariables.title')}
              description={t('pages.settings.sections.codex.environmentVariables.description')}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
};
