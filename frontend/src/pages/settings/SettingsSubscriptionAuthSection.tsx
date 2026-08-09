import React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { SettingsFlatSection } from '@/shared/components/settings-workflow';
import { useI18n } from '@/shared/hooks/useI18n';

interface SettingsSubscriptionAuthSectionProps {
  /** i18n key prefix for the subscription section, e.g. 'pages.settings.sections.claudeCode.subscription'. */
  i18nPrefix: string;
  isConnected: boolean;
  showAuthCodeInput: boolean;
  isExchangingCode: boolean;
  tempAuthCode: string;
  /** Account/identity lines rendered in the connected state (differs per agent). */
  accountInfo?: React.ReactNode;
  /** Extra content rendered inside the connected card (e.g. the model input). */
  connectedExtra?: React.ReactNode;
  onTempAuthCodeChange: (authCode: string) => void;
  onConnect: () => void;
  onSaveAuthCode: () => void;
  onCancelAuth: () => void;
  onDisconnect: () => void;
}

const StatusHeader: React.FC<{ connected: boolean; label: string }> = ({ connected, label }) => (
  <div className="flex items-center gap-3">
    <span
      className={
        connected
          ? 'inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary dark:bg-primary/15 dark:text-primary-foreground'
          : 'inline-flex items-center gap-1.5 rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-800 dark:bg-red-900 dark:text-red-200'
      }
    >
      <span className={connected ? 'h-2 w-2 rounded-full bg-primary' : 'h-2 w-2 rounded-full bg-red-500'} />
      {label}
    </span>
  </div>
);

export const SettingsSubscriptionAuthSection: React.FC<SettingsSubscriptionAuthSectionProps> = ({
  i18nPrefix,
  isConnected,
  showAuthCodeInput,
  isExchangingCode,
  tempAuthCode,
  accountInfo,
  connectedExtra,
  onTempAuthCodeChange,
  onConnect,
  onSaveAuthCode,
  onCancelAuth,
  onDisconnect,
}) => {
  const { t } = useI18n();
  const title = t(`${i18nPrefix}.title`);
  const connectedLabel = t(`${i18nPrefix}.status.connected`);
  const notConnectedLabel = t(`${i18nPrefix}.status.notConnected`);

  return (
    <SettingsFlatSection
      title={title}
      description={isConnected && !showAuthCodeInput ? t(`${i18nPrefix}.description`) : undefined}
    >
      {isConnected && !showAuthCodeInput && (
        <div className="space-y-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="space-y-2">
              <StatusHeader connected label={connectedLabel} />
              {accountInfo}
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={onDisconnect}
                className="text-muted-foreground hover:text-foreground"
              >
                {t(`${i18nPrefix}.disconnectButton`)}
              </Button>
            </div>
          </div>
          {connectedExtra}
        </div>
      )}

      {!isConnected && !showAuthCodeInput && (
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <StatusHeader connected={false} label={notConnectedLabel} />
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button type="button" onClick={onConnect} className="w-fit">
              {t(`${i18nPrefix}.connectButton`)}
            </Button>
          </div>
        </div>
      )}

      {showAuthCodeInput && (
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 flex-1 space-y-4">
            <StatusHeader connected={false} label={notConnectedLabel} />
            <p className="text-sm text-muted-foreground">{t(`${i18nPrefix}.authCodeHint`)}</p>
            <Input
              placeholder={t(`${i18nPrefix}.authCodePlaceholder`)}
              value={tempAuthCode}
              onChange={(event) => onTempAuthCodeChange(event.target.value)}
              className="font-mono"
              disabled={isExchangingCode}
            />
            {isExchangingCode && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <RefreshCw className="h-4 w-4 animate-spin" />
                <span>{t(`${i18nPrefix}.verifying`)}</span>
              </div>
            )}
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button
              type="button"
              onClick={onSaveAuthCode}
              disabled={isExchangingCode || !tempAuthCode.trim()}
              className="bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              {t(`${i18nPrefix}.saveButton`)}
            </Button>
            <Button type="button" variant="outline" onClick={onCancelAuth} disabled={isExchangingCode}>
              {t(`${i18nPrefix}.cancelButton`)}
            </Button>
          </div>
        </div>
      )}
    </SettingsFlatSection>
  );
};
