import React from 'react';
import { Shield } from 'lucide-react';
import {
  EnvironmentVariables,
  SettingsFlatField,
  SettingsFlatRow,
  SettingsSectionDivider,
} from '@/shared/components/settings-workflow';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserSettingsClaudeCode } from '@/shared/types/user';
import { SettingsModelSelectionSection } from './SettingsModelSelectionSection';
import { SettingsSubscriptionAuthSection } from './SettingsSubscriptionAuthSection';

interface SettingsClaudeCodeTabProps {
  claudeCodeSettings: UserSettingsClaudeCode;
  fallbackAccountEmail: string | null | undefined;
  showAuthCodeInput: boolean;
  isExchangingCode: boolean;
  tempAuthCode: string;
  onClaudeCodeSettingsChange: (settings: UserSettingsClaudeCode) => void;
  onTempAuthCodeChange: (authCode: string) => void;
  onConnect: () => void;
  onSaveAuthCode: () => void;
  onCancelAuth: () => void;
  onDisconnect: () => void;
}

export const SettingsClaudeCodeTab: React.FC<SettingsClaudeCodeTabProps> = ({
  claudeCodeSettings,
  fallbackAccountEmail,
  showAuthCodeInput,
  isExchangingCode,
  tempAuthCode,
  onClaudeCodeSettingsChange,
  onTempAuthCodeChange,
  onConnect,
  onSaveAuthCode,
  onCancelAuth,
  onDisconnect,
}) => {
  const { t } = useI18n();
  const authMethod = claudeCodeSettings.authMethod || 'subscription';
  const accountEmail = claudeCodeSettings.oauthAccount?.emailAddress
    || fallbackAccountEmail
    || t('pages.settings.sections.claudeCode.subscription.accountUnavailable');

  return (
    <div className="space-y-6 p-1">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            {t('pages.settings.sections.claudeCode.title')}
          </CardTitle>
          <CardDescription>{t('pages.settings.sections.claudeCode.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <SettingsModelSelectionSection
            value={claudeCodeSettings.modelSelection}
            onChange={(modelSelection) => onClaudeCodeSettingsChange({ ...claudeCodeSettings, modelSelection })}
            i18nPrefix="pages.settings.sections.claudeCode.models"
          />

          <SettingsFlatRow label={t('pages.settings.sections.claudeCode.authMethod.label')}>
            <Select
              value={authMethod}
              onValueChange={(value) =>
                onClaudeCodeSettingsChange({ ...claudeCodeSettings, authMethod: value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder={t('pages.settings.sections.claudeCode.authMethod.description')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="subscription">{t('pages.settings.sections.claudeCode.authMethod.options.subscription')}</SelectItem>
                <SelectItem value="apikey">{t('pages.settings.sections.claudeCode.authMethod.options.apikey')}</SelectItem>
              </SelectContent>
            </Select>
          </SettingsFlatRow>

          <SettingsSectionDivider />

          {authMethod === 'subscription' && (
            <SettingsSubscriptionAuthSection
              i18nPrefix="pages.settings.sections.claudeCode.subscription"
              isConnected={!!claudeCodeSettings.subscriptionAccessToken}
              showAuthCodeInput={showAuthCodeInput}
              isExchangingCode={isExchangingCode}
              tempAuthCode={tempAuthCode}
              accountInfo={(
                <p className="text-sm text-muted-foreground">
                  {t('pages.settings.sections.claudeCode.subscription.account')}: <span className="font-mono text-foreground">
                    {accountEmail}
                    {claudeCodeSettings.oauthAccount?.displayName && (
                      <span className="ml-2 font-sans text-muted-foreground">({claudeCodeSettings.oauthAccount.displayName})</span>
                    )}
                  </span>
                </p>
              )}
              connectedExtra={(
                <SettingsFlatField
                  label={t('pages.settings.sections.claudeCode.apikey.modelLabel')}
                  description={t('pages.settings.sections.claudeCode.apikey.modelHelp')}
                >
                  <Input
                    placeholder={t('pages.settings.sections.claudeCode.apikey.modelPlaceholder')}
                    value={claudeCodeSettings.model || ''}
                    onChange={(event) =>
                      onClaudeCodeSettingsChange({ ...claudeCodeSettings, model: event.target.value })
                    }
                    className="font-mono"
                  />
                </SettingsFlatField>
              )}
              onTempAuthCodeChange={onTempAuthCodeChange}
              onConnect={onConnect}
              onSaveAuthCode={onSaveAuthCode}
              onCancelAuth={onCancelAuth}
              onDisconnect={onDisconnect}
            />
          )}

          {authMethod === 'apikey' && (
            <div className="space-y-4">
              <SettingsFlatRow label={t('pages.settings.sections.claudeCode.apikey.providerLabel')}>
                <Select
                  value={claudeCodeSettings.apiProvider || ''}
                  onValueChange={(value) =>
                    onClaudeCodeSettingsChange({ ...claudeCodeSettings, apiProvider: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('pages.settings.sections.claudeCode.apikey.providerPlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="anthropic">{t('pages.settings.sections.claudeCode.apikey.providerOptions.anthropic')}</SelectItem>
                    <SelectItem value="aws-bedrock">{t('pages.settings.sections.claudeCode.apikey.providerOptions.awsBedrock')}</SelectItem>
                    <SelectItem value="google-vertex-ai">{t('pages.settings.sections.claudeCode.apikey.providerOptions.googleVertexAi')}</SelectItem>
                    <SelectItem value="other">{t('pages.settings.sections.claudeCode.apikey.providerOptions.other')}</SelectItem>
                  </SelectContent>
                </Select>
              </SettingsFlatRow>

              <SettingsFlatRow
                label={t('pages.settings.sections.claudeCode.apikey.modelLabel')}
                description={t('pages.settings.sections.claudeCode.apikey.modelHelp')}
              >
                <Input
                  placeholder={t('pages.settings.sections.claudeCode.apikey.modelPlaceholder')}
                  value={claudeCodeSettings.model || ''}
                  onChange={(event) =>
                    onClaudeCodeSettingsChange({ ...claudeCodeSettings, model: event.target.value })
                  }
                  className="font-mono"
                />
              </SettingsFlatRow>

              <EnvironmentVariables
                value={claudeCodeSettings.environmentVariables || []}
                onChange={(variables) =>
                  onClaudeCodeSettingsChange({ ...claudeCodeSettings, environmentVariables: variables })
                }
              />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
