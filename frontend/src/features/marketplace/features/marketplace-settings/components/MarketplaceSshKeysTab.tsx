import React from 'react';
import { KeyRound, Save } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserSettingsSSH } from '@/shared/types/user';

interface MarketplaceSshKeysTabProps {
  sshKeys: UserSettingsSSH;
  showPrivateKey: boolean;
  onSshKeysChange: (value: UserSettingsSSH) => void;
  onShowPrivateKeyChange: (value: boolean) => void;
  onGenerateSshKey: () => void;
  onSaveSshKeys: () => void;
  onCopy: (value: string | null) => void;
}

export const MarketplaceSshKeysTab: React.FC<MarketplaceSshKeysTabProps> = ({
  sshKeys,
  showPrivateKey,
  onSshKeysChange,
  onShowPrivateKeyChange,
  onGenerateSshKey,
  onSaveSshKeys,
  onCopy,
}) => {
  const { t } = useI18n();

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="h-5 w-5" />
            {t('pages.settings.sections.ssh.title')}
          </CardTitle>
          <CardDescription>
            {t('pages.settings.sections.ssh.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="marketplaceUserPrivateKey">{t('pages.settings.sections.ssh.privateKey.label')}</Label>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => onShowPrivateKeyChange(!showPrivateKey)}>
                  {showPrivateKey
                    ? t('pages.settings.sections.ssh.privateKey.actions.hide')
                    : t('pages.settings.sections.ssh.privateKey.actions.show')}
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => onCopy(sshKeys.privateKey)}>
                  {t('pages.settings.sections.ssh.privateKey.actions.copy')}
                </Button>
              </div>
            </div>
            <Textarea
              id="marketplaceUserPrivateKey"
              placeholder={t('pages.settings.sections.ssh.privateKey.placeholder')}
              value={showPrivateKey ? (sshKeys.privateKey || '') : '••••••••••••'}
              onChange={event => onSshKeysChange({ ...sshKeys, privateKey: event.target.value })}
              className="font-mono text-sm"
              disabled={!showPrivateKey}
              rows={8}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="marketplaceUserPublicKey">{t('pages.settings.sections.ssh.publicKey.label')}</Label>
              <Button type="button" variant="outline" size="sm" onClick={() => onCopy(sshKeys.publicKey)}>
                {t('pages.settings.sections.ssh.publicKey.copy')}
              </Button>
            </div>
            <Textarea
              id="marketplaceUserPublicKey"
              placeholder={t('pages.settings.sections.ssh.publicKey.placeholder')}
              value={sshKeys.publicKey || ''}
              onChange={event => onSshKeysChange({ ...sshKeys, publicKey: event.target.value })}
              className="font-mono text-sm"
              rows={4}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onGenerateSshKey}>
              {t('pages.settings.sections.ssh.generate')}
            </Button>
            <Button onClick={onSaveSshKeys}>
              <Save className="mr-2 h-4 w-4" />
              {t('pages.settings.actions.save')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
